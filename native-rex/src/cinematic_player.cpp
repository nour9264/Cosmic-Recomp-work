#include "cinematic_player.h"

#include <windows.h>
#include <audiopolicy.h>
#include <mmdeviceapi.h>
#include <d3dcompiler.h>
#include <mfapi.h>
#include <mfmediaengine.h>
#include <wincodec.h>
#include <wrl/client.h>
#include <rex/input/input_system.h>
#include <rex/ui/d3d12/d3d12_presenter.h>
#include <rex/ui/ui_drawer.h>

#include <algorithm>
#include <array>
#include <utility>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <memory>

#include <algorithm>
#include <mutex>
#include <string>
#include <fstream>
#include <vector>

namespace ben10::cinematic_player {
namespace {
using Microsoft::WRL::ComPtr;
using rex::ui::d3d12::D3D12Presenter;
using rex::ui::d3d12::D3D12UIDrawContext;
using Clock = std::chrono::steady_clock;
enum class State { idle, opening, playing, ended, skipped, fallback };
constexpr UINT width = 1920, height = 1080, pitch = width * 4;
constexpr auto format = DXGI_FORMAT_B8G8R8A8_UNORM;
std::atomic<State> state{State::idle};
std::atomic<uint32_t> active_movie{0};
std::atomic<uint64_t> submitted_frames{0};
std::atomic<uint64_t> playback_ms{0};
std::atomic<bool> available{false};
rex::input::InputSystem* input = nullptr;
HWND game_window = nullptr;
Clock::time_point deadline;
bool skip_ready = false;
std::mutex playback_mutex;
std::filesystem::path enhanced_root, selected_path;
uint64_t generation = 0;
thread_local std::string source_path;
struct SubtitleCue { uint64_t start, end; std::string text; };
std::vector<SubtitleCue> subtitles;
bool subtitle_displayed = false;

void Log(const char* message, HRESULT hr = S_OK) {
    std::fprintf(stderr, "[cinematic-pc] %s (0x%08lx)\n", message, static_cast<unsigned long>(hr));
    std::fflush(stderr);
}

void Fail(HRESULT hr) {
    auto expected = State::opening;
    if (!state.compare_exchange_strong(expected, State::fallback)) {
        expected = State::playing;
        state.compare_exchange_strong(expected, State::skipped);
    }
    Log("in-game playback failed", hr);
}

class Events final : public IMFMediaEngineNotify {
public:
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid != IID_IUnknown && iid != __uuidof(IMFMediaEngineNotify)) return E_NOINTERFACE;
        *out = static_cast<IMFMediaEngineNotify*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++references_; }
    ULONG STDMETHODCALLTYPE Release() override {
        const auto count = --references_;
        if (!count) delete this;
        return count;
    }
    HRESULT STDMETHODCALLTYPE EventNotify(DWORD event, DWORD_PTR, DWORD second) override {
        if (event == MF_MEDIA_ENGINE_EVENT_ERROR)
            error.store(second ? static_cast<HRESULT>(second) : E_FAIL);
        if (event == MF_MEDIA_ENGINE_EVENT_ENDED) ended.store(true);
        return S_OK;
    }
    std::atomic<HRESULT> error{S_OK};
    std::atomic<bool> ended{false};
private:
    std::atomic<ULONG> references_{1};
};

class MovieDrawer final : public rex::ui::UIDrawer {
public:
    explicit MovieDrawer(D3D12Presenter& presenter) : presenter_(presenter) {}
    bool Initialize();
    void Draw(rex::ui::UIDrawContext& context) override;
    void Stop() {
        if (samples_.draws) ReportCadence(Clock::now());
        if (engine_) engine_->Shutdown();
        engine_.Reset();
        game_volume_.Reset();
        events_.Reset();
        has_frame_ = false;
    }
    void Drain() {
        if (!submitted_frames.load()) return;
        auto* device = presenter_.provider().GetDevice();
        ComPtr<ID3D12Fence> fence;
        if (FAILED(device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&fence)))) return;
        HANDLE event = CreateEventW(nullptr, FALSE, FALSE, nullptr);
        if (!event) return;
        if (SUCCEEDED(fence->SetEventOnCompletion(1, event)) &&
            SUCCEEDED(presenter_.provider().GetDirectQueue()->Signal(fence.Get(), 1)))
            WaitForSingleObject(event, 3000);
        CloseHandle(event);
    }
private:
    HRESULT Open();
    void SyncGameVolume();
    HRESULT Upload(D3D12UIDrawContext& context);
    void ReportCadence(Clock::time_point now);
    struct Cadence {
        unsigned draws = 0, not_ready = 0, slots_busy = 0, no_frame = 0, uploaded = 0;
        double longest_draw_gap_ms = 0, transfer_ms = 0, max_transfer_ms = 0;
    } samples_;
    Clock::time_point cadence_start_{}, last_draw_{};
    uint64_t cadence_media_start_ = 0;
    struct Slot { ComPtr<ID3D12Resource> buffer; UINT64 submission = 0; };
    D3D12Presenter& presenter_;
    uint64_t opened_generation_ = 0;
    ComPtr<IWICBitmap> bitmap_;
    ComPtr<IMFMediaEngine> engine_;
    ComPtr<ISimpleAudioVolume> game_volume_;
    Clock::time_point next_volume_sync_{};
    ComPtr<Events> events_;
    ComPtr<ID3D12RootSignature> root_;
    ComPtr<ID3D12PipelineState> pipeline_;
    ComPtr<ID3D12DescriptorHeap> views_;
    ComPtr<ID3D12Resource> texture_;
    std::array<Slot,3> uploads_;
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint_{};
    bool has_frame_ = false;
};
std::unique_ptr<MovieDrawer> drawer;

bool MovieDrawer::Initialize() {
    auto* device = presenter_.provider().GetDevice();
    ComPtr<IWICImagingFactory> factory;
    if (FAILED(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER,
                                IID_PPV_ARGS(&factory))) ||
        FAILED(factory->CreateBitmap(width, height, GUID_WICPixelFormat32bppBGRA,
                                     WICBitmapCacheOnLoad, &bitmap_))) return false;

    D3D12_DESCRIPTOR_RANGE range{D3D12_DESCRIPTOR_RANGE_TYPE_SRV, 1, 0, 0, 0};
    D3D12_ROOT_PARAMETER parameter{};
    parameter.ParameterType = D3D12_ROOT_PARAMETER_TYPE_DESCRIPTOR_TABLE;
    parameter.DescriptorTable = {1, &range};
    parameter.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    D3D12_STATIC_SAMPLER_DESC sampler{};
    sampler.Filter = D3D12_FILTER_MIN_MAG_LINEAR_MIP_POINT;
    sampler.AddressU = sampler.AddressV = sampler.AddressW = D3D12_TEXTURE_ADDRESS_MODE_CLAMP;
    sampler.ComparisonFunc = D3D12_COMPARISON_FUNC_ALWAYS;
    sampler.MaxAnisotropy = 1;
    sampler.MaxLOD = D3D12_FLOAT32_MAX;
    sampler.ShaderVisibility = D3D12_SHADER_VISIBILITY_PIXEL;
    D3D12_ROOT_SIGNATURE_DESC signature{1, &parameter, 1, &sampler, D3D12_ROOT_SIGNATURE_FLAG_NONE};
    ComPtr<ID3DBlob> serialized;
    if (FAILED(D3D12SerializeRootSignature(&signature, D3D_ROOT_SIGNATURE_VERSION_1,
                                          &serialized, nullptr)) ||
        FAILED(device->CreateRootSignature(0, serialized->GetBufferPointer(),
               serialized->GetBufferSize(), IID_PPV_ARGS(&root_)))) return false;
    constexpr char shader[] = R"(
        Texture2D video : register(t0);
        SamplerState linearSampler : register(s0);
        struct Vertex { float4 position : SV_Position; float2 uv : TEXCOORD0; };
        Vertex VS(uint id : SV_VertexID) {
            Vertex o;
            o.uv = float2((id << 1) & 2, id & 2);
            o.position = float4(o.uv * float2(2, -2) + float2(-1, 1), 0, 1);
            return o;
        }
        float4 PS(Vertex i) : SV_Target { return float4(video.Sample(linearSampler, i.uv).rgb, 1); }
    )";
    ComPtr<ID3DBlob> vs, ps;
    if (FAILED(D3DCompile(shader, sizeof(shader)-1, nullptr, nullptr, nullptr, "VS", "vs_5_0",
                         0, 0, &vs, nullptr)) ||
        FAILED(D3DCompile(shader, sizeof(shader)-1, nullptr, nullptr, nullptr, "PS", "ps_5_0",
                         0, 0, &ps, nullptr))) return false;
    D3D12_GRAPHICS_PIPELINE_STATE_DESC pso{};
    pso.pRootSignature = root_.Get();
    pso.VS = {vs->GetBufferPointer(), vs->GetBufferSize()};
    pso.PS = {ps->GetBufferPointer(), ps->GetBufferSize()};
    pso.BlendState.RenderTarget[0] = {FALSE,FALSE,D3D12_BLEND_ONE,D3D12_BLEND_ZERO,
        D3D12_BLEND_OP_ADD,D3D12_BLEND_ONE,D3D12_BLEND_ZERO,D3D12_BLEND_OP_ADD,
        D3D12_LOGIC_OP_NOOP,D3D12_COLOR_WRITE_ENABLE_ALL};
    pso.RasterizerState.FillMode = D3D12_FILL_MODE_SOLID;
    pso.RasterizerState.CullMode = D3D12_CULL_MODE_NONE;
    pso.RasterizerState.DepthClipEnable = TRUE;
    pso.DepthStencilState.DepthFunc = D3D12_COMPARISON_FUNC_ALWAYS;
    pso.DepthStencilState.FrontFace = pso.DepthStencilState.BackFace =
        {D3D12_STENCIL_OP_KEEP,D3D12_STENCIL_OP_KEEP,D3D12_STENCIL_OP_KEEP,D3D12_COMPARISON_FUNC_ALWAYS};
    pso.SampleMask = UINT_MAX;
    pso.PrimitiveTopologyType = D3D12_PRIMITIVE_TOPOLOGY_TYPE_TRIANGLE;
    pso.NumRenderTargets = 1;
    pso.RTVFormats[0] = D3D12Presenter::kSwapChainFormat;
    pso.SampleDesc.Count = 1;
    if (FAILED(device->CreateGraphicsPipelineState(&pso, IID_PPV_ARGS(&pipeline_)))) return false;

    D3D12_DESCRIPTOR_HEAP_DESC heap{D3D12_DESCRIPTOR_HEAP_TYPE_CBV_SRV_UAV, 1,
                                    D3D12_DESCRIPTOR_HEAP_FLAG_SHADER_VISIBLE, 0};
    if (FAILED(device->CreateDescriptorHeap(&heap, IID_PPV_ARGS(&views_)))) return false;
    const D3D12_HEAP_PROPERTIES gpu{D3D12_HEAP_TYPE_DEFAULT}, cpu{D3D12_HEAP_TYPE_UPLOAD};
    D3D12_RESOURCE_DESC texture{D3D12_RESOURCE_DIMENSION_TEXTURE2D, 0, width, height, 1, 1,
                                format, {1,0}, D3D12_TEXTURE_LAYOUT_UNKNOWN};
    if (FAILED(device->CreateCommittedResource(&gpu, D3D12_HEAP_FLAG_NONE, &texture,
        D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE, nullptr, IID_PPV_ARGS(&texture_)))) return false;
    device->CreateShaderResourceView(texture_.Get(), nullptr, views_->GetCPUDescriptorHandleForHeapStart());
    UINT64 size = 0;
    device->GetCopyableFootprints(&texture, 0, 1, 0, &footprint_, nullptr, nullptr, &size);
    D3D12_RESOURCE_DESC buffer{D3D12_RESOURCE_DIMENSION_BUFFER, 0, size, 1, 1, 1,
                               DXGI_FORMAT_UNKNOWN, {1,0}, D3D12_TEXTURE_LAYOUT_ROW_MAJOR};
    for (auto& slot : uploads_) {
        if (FAILED(device->CreateCommittedResource(&cpu, D3D12_HEAP_FLAG_NONE, &buffer,
            D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(&slot.buffer)))) return false;
    }
    return true;
}

HRESULT MovieDrawer::Open() {
    // SDL WASAPI opens the process-default session on the console endpoint.
    ComPtr<IMMDeviceEnumerator> devices;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                  IID_PPV_ARGS(&devices));
    ComPtr<IMMDevice> device;
    if (SUCCEEDED(hr)) hr = devices->GetDefaultAudioEndpoint(eRender, eConsole, &device);
    ComPtr<IAudioSessionManager> sessions;
    if (SUCCEEDED(hr)) hr = device->Activate(__uuidof(IAudioSessionManager), CLSCTX_INPROC_SERVER,
                                            nullptr, reinterpret_cast<void**>(sessions.GetAddressOf()));
    if (SUCCEEDED(hr)) hr = sessions->GetSimpleAudioVolume(nullptr, 0, &game_volume_);
    if (FAILED(hr)) return hr;

    ComPtr<IMFMediaEngineClassFactory> factory;
    hr = CoCreateInstance(CLSID_MFMediaEngineClassFactory, nullptr, CLSCTX_INPROC_SERVER,
                          IID_PPV_ARGS(&factory));
    ComPtr<IMFAttributes> attributes;
    if (SUCCEEDED(hr)) hr = MFCreateAttributes(&attributes, 3);
    events_.Attach(new Events);
    if (SUCCEEDED(hr)) hr = attributes->SetUnknown(MF_MEDIA_ENGINE_CALLBACK, events_.Get());
    if (SUCCEEDED(hr)) hr = attributes->SetUINT32(MF_MEDIA_ENGINE_VIDEO_OUTPUT_FORMAT, format);
    if (SUCCEEDED(hr)) hr = attributes->SetUINT32(MF_MEDIA_ENGINE_AUDIO_ENDPOINT_ROLE, eConsole);
    if (SUCCEEDED(hr)) hr = factory->CreateInstance(0, attributes.Get(), &engine_);
    if (FAILED(hr)) return hr;
    const BSTR path = SysAllocString(selected_path.c_str());
    if (!path) return E_OUTOFMEMORY;
    hr = engine_->SetSource(path);
    SysFreeString(path);
    if (SUCCEEDED(hr)) hr = engine_->SetMuted(TRUE);
    if (SUCCEEDED(hr)) {
        SyncGameVolume();
        next_volume_sync_ = Clock::now() + std::chrono::milliseconds(50);
    }
    return SUCCEEDED(hr) ? engine_->Play() : hr;
}

void MovieDrawer::SyncGameVolume() {
    float level = 0;
    BOOL muted = TRUE;
    if (FAILED(game_volume_->GetMasterVolume(&level)) || FAILED(game_volume_->GetMute(&muted))) {
        engine_->SetMuted(TRUE);
        return;
    }
    if (engine_->GetVolume() != level && FAILED(engine_->SetVolume(level))) muted = TRUE;
    if (engine_->GetMuted() != muted) engine_->SetMuted(muted);
}

HRESULT MovieDrawer::Upload(D3D12UIDrawContext& context) {
    Slot* free_slot = nullptr;
    for (auto& slot : uploads_) {
        if (slot.submission <= context.submission_index_completed()) { free_slot = &slot; break; }
    }
    if (!free_slot) { ++samples_.slots_busy; return S_FALSE; }
    LONGLONG timestamp{};
    HRESULT hr = engine_->OnVideoStreamTick(&timestamp);
    if (hr != S_OK) {
        if (hr == S_FALSE) ++samples_.no_frame;
        return hr;
    }
    const auto transfer_start = Clock::now();
    const RECT rect{0,0,width,height};
    const MFARGB black{0,0,0,255};
    hr = engine_->TransferVideoFrame(bitmap_.Get(), nullptr, &rect, &black);
    if (FAILED(hr)) return hr;
    const D3D12_RANGE no_read{};
    void* data = nullptr;
    hr = free_slot->buffer->Map(0, &no_read, &data);
    if (FAILED(hr)) return hr;
    const UINT stride = footprint_.Footprint.RowPitch;
    hr = bitmap_->CopyPixels(nullptr, stride, stride * height,
                            static_cast<BYTE*>(data) + footprint_.Offset);
    free_slot->buffer->Unmap(0, nullptr);
    if (FAILED(hr)) return hr;
    auto* commands = context.command_list();
    D3D12_RESOURCE_BARRIER barrier{};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition = {texture_.Get(), D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES,
        D3D12_RESOURCE_STATE_PIXEL_SHADER_RESOURCE,D3D12_RESOURCE_STATE_COPY_DEST};
    commands->ResourceBarrier(1, &barrier);
    D3D12_TEXTURE_COPY_LOCATION source{}, destination{};
    source.pResource = free_slot->buffer.Get();
    source.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    source.PlacedFootprint = footprint_;
    destination.pResource = texture_.Get();
    destination.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    commands->CopyTextureRegion(&destination, 0, 0, 0, &source, nullptr);
    std::swap(barrier.Transition.StateBefore, barrier.Transition.StateAfter);
    commands->ResourceBarrier(1, &barrier);
    free_slot->submission = context.submission_index_current();
    const auto transfer = std::chrono::duration<double, std::milli>(Clock::now() - transfer_start).count();
    ++samples_.uploaded;
    samples_.transfer_ms += transfer;
    samples_.max_transfer_ms = std::max(samples_.max_transfer_ms, transfer);
    submitted_frames.fetch_add(1);
    has_frame_ = true;
    return S_OK;
}

void MovieDrawer::ReportCadence(Clock::time_point now) {
    const auto seconds = std::chrono::duration<double>(now - cadence_start_).count();
    const auto media = playback_ms.load();
    const auto advanced = media >= cadence_media_start_ ? media - cadence_media_start_ : 0;
    std::fprintf(stderr,
        "[cinematic-pc] cadence %.2fs media=%llums draws=%u frames=%u "
        "not-ready=%u no-frame=%u slots-busy=%u max-draw-gap=%.1fms transfer-avg/max=%.1f/%.1fms\n",
        seconds, static_cast<unsigned long long>(advanced), samples_.draws, samples_.uploaded,
        samples_.not_ready, samples_.no_frame, samples_.slots_busy, samples_.longest_draw_gap_ms,
        samples_.uploaded ? samples_.transfer_ms / samples_.uploaded : 0, samples_.max_transfer_ms);
    std::fflush(stderr);
    samples_ = {};
    cadence_start_ = now;
    cadence_media_start_ = media;
}

void MovieDrawer::Draw(rex::ui::UIDrawContext& base) {
    std::lock_guard lock(playback_mutex);
    if (engine_ && opened_generation_ != generation) Stop();
    const auto current = state.load();
    if (current != State::opening && current != State::playing) {
        if (engine_) Stop();
        return;
    }
    if (!engine_) {
        opened_generation_ = generation;
        cadence_start_ = last_draw_ = Clock::now();
        cadence_media_start_ = 0;
        const HRESULT hr = Open();
        if (FAILED(hr)) { Fail(hr); Stop(); }
        return;
    }
    if (const HRESULT hr = events_->error.load(); FAILED(hr)) { Fail(hr); Stop(); return; }
    if (events_->ended.load()) {
        auto expected = State::playing;
        if (state.compare_exchange_strong(expected, State::ended)) Log("enhanced cinematic ended");
        else Fail(E_FAIL);
        Stop();
        return;
    }
    auto& context = static_cast<D3D12UIDrawContext&>(base);
    const auto now = Clock::now();
    if (now >= next_volume_sync_) {
        SyncGameVolume();
        next_volume_sync_ = now + std::chrono::milliseconds(50);
    }
    ++samples_.draws;
    samples_.longest_draw_gap_ms = std::max(samples_.longest_draw_gap_ms,
        std::chrono::duration<double, std::milli>(now - last_draw_).count());
    last_draw_ = now;
    if (engine_->GetReadyState() >= MF_MEDIA_ENGINE_READY_HAVE_CURRENT_DATA) {
        const HRESULT hr = Upload(context);
        if (FAILED(hr)) { Fail(hr); Stop(); return; }
    } else ++samples_.not_ready;
    const double seconds = engine_->GetCurrentTime();
    if (seconds >= 0 && seconds < 3600) playback_ms.store(static_cast<uint64_t>(seconds * 1000));
    if (now - cadence_start_ >= std::chrono::seconds(5)) ReportCadence(now);
    if (!has_frame_) return;
    auto expected = State::opening;
    if (state.compare_exchange_strong(expected, State::playing)) Log("enhanced cinematic composited");
    if (state.load() != State::playing) return;

    auto* commands = context.command_list();
    const float w = static_cast<float>(context.render_target_width());
    const float h = static_cast<float>(context.render_target_height());
    const float scale = (std::min)(w/width, h/height);
    const D3D12_VIEWPORT viewport{(w-width*scale)/2, (h-height*scale)/2,
                                  width*scale, height*scale, 0, 1};
    const D3D12_RECT scissor{0,0,static_cast<LONG>(w),static_cast<LONG>(h)};
    commands->RSSetViewports(1, &viewport);
    commands->RSSetScissorRects(1, &scissor);
    ID3D12DescriptorHeap* heap = views_.Get();
    commands->SetDescriptorHeaps(1, &heap);
    commands->SetGraphicsRootSignature(root_.Get());
    commands->SetGraphicsRootDescriptorTable(0, views_->GetGPUDescriptorHandleForHeapStart());
    commands->SetPipelineState(pipeline_.Get());
    commands->IASetPrimitiveTopology(D3D_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    commands->DrawInstanced(3, 1, 0, 0);
}
}

void Attach(void* window, void* host_input, void* host_presenter, const std::filesystem::path& directory) {
    auto* presenter = static_cast<D3D12Presenter*>(host_presenter);
    if (!window || !presenter || !std::filesystem::is_directory(directory)) return;
    const HRESULT hr = MFStartup(MF_VERSION);
    if (FAILED(hr)) { Log("Media Foundation unavailable, using original", hr); return; }
    auto candidate = std::make_unique<MovieDrawer>(*presenter);
    if (!candidate->Initialize()) { Log("video surface unavailable, using original"); MFShutdown(); return; }
    enhanced_root = directory;
    input = static_cast<rex::input::InputSystem*>(host_input);
    game_window = static_cast<HWND>(window);
    drawer = std::move(candidate);
    presenter->AddUIDrawerFromUIThread(drawer.get(), 63);
    available.store(true);
}

void Detach(void* host_presenter) {
    available.store(false);
    active_movie.store(0);
    state.store(State::idle);
    if (drawer) {
        if (host_presenter)
            static_cast<D3D12Presenter*>(host_presenter)->RemoveUIDrawerFromUIThread(drawer.get());
        drawer->Stop();
        drawer->Drain();
        drawer.reset();
        MFShutdown();
    }
}

bool Playing() { return state.load() == State::playing; }
uint64_t PlaybackMilliseconds() { return playback_ms.load(); }
uint64_t SubmittedFrames() { return submitted_frames.load(); }

void ResetSource() { source_path.clear(); }

void CaptureSource(const char* path) {
    if (!available.load()) return;
    source_path.assign(path);
}

void Begin(uint32_t caller, uint32_t movie) {
    if (!available.load() || !movie ||
        (caller != 0x82156EE8 && caller != 0x82156F20 &&
         caller != 0x8215831C && caller != 0x821C0C00)) return;
    std::lock_guard lock(playback_mutex);
    if (!available.load() || state.load() != State::idle) return;

    std::replace(source_path.begin(), source_path.end(), '\\', '/');
    for (char& c : source_path)
        if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    const auto fmv = source_path.find("fmv/");
    if (fmv == std::string::npos || (fmv && source_path[fmv - 1] != '/' &&
                                    source_path[fmv - 1] != ':')) return;
    const std::string clip = source_path.substr(fmv + 4);
    const auto separator = clip.find('/');
    if (!clip.starts_with("l_") || separator == std::string::npos ||
        clip.find('/', separator + 1) != std::string::npos || !clip.ends_with(".wmv") ||
        clip.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_/.", 0) != std::string::npos ||
        clip.find("..") != std::string::npos) return;

    auto candidate = enhanced_root / clip;
    std::error_code error;
    // Prefer a decoder-friendly copy when present. Existing WMV packs still work.
    candidate.replace_extension(".mp4");
    if (!std::filesystem::is_regular_file(candidate, error))
        candidate.replace_extension(".wmv");
    if (!std::filesystem::is_regular_file(candidate, error)) {
        std::fprintf(stderr, "[cinematic-pc] original: %s (enhanced copy missing)\n", clip.c_str());
        return;
    }

    selected_path = candidate;
    subtitles.clear();
    subtitle_displayed = false;
    auto subtitle_path = candidate;
    subtitle_path.replace_extension(".subtitles.tsv");
    std::ifstream file(subtitle_path);
    SubtitleCue cue{};
    while (subtitles.size() < 256 && file >> cue.start >> cue.end) {
        if (file.get() != '\t' || !std::getline(file, cue.text) ||
            cue.start >= cue.end || cue.text.empty() ||
            (!subtitles.empty() && cue.start < subtitles.back().end)) {
            subtitles.clear();
            break;
        }
        subtitles.push_back(cue);
    }
    ++generation;
    const auto selected_clip = candidate.lexically_relative(enhanced_root).generic_string();
    std::fprintf(stderr, "[cinematic-pc] opening: %s\n", selected_clip.c_str());
    active_movie.store(movie);
    skip_ready = false;
    playback_ms.store(0);
    deadline = Clock::now() + std::chrono::seconds(5);
    state.store(State::opening);
}

bool Update(uint32_t movie) {
    if (!movie || active_movie.load() != movie) return false;
    auto current = state.load();
    if (current == State::opening && Clock::now() >= deadline) {
        if (state.compare_exchange_strong(current, State::fallback))
            Log("enhanced cinematic timed out, using original");
        current = state.load();
    }
    if (current == State::playing) {
        rex::input::X_INPUT_STATE controller{};
        const bool connected = input && input->GetState(0, &controller) == 0;
        constexpr uint16_t skip_buttons = rex::input::X_INPUT_GAMEPAD_START |
                                          rex::input::X_INPUT_GAMEPAD_BACK;
        const bool pressed = GetForegroundWindow() == game_window &&
            ((connected && (controller.gamepad.buttons & skip_buttons)) ||
             ((GetAsyncKeyState(VK_ESCAPE) | GetAsyncKeyState(VK_RETURN)) & 0x8000));
        if (!pressed) skip_ready = true;
        if (pressed && skip_ready && state.compare_exchange_strong(current, State::skipped))
            Log("enhanced cinematic skipped");
    }
    return current != State::idle && current != State::fallback;
}

bool Ready(uint32_t movie, uint32_t& result) {
    if (!movie || active_movie.load() != movie) return false;
    const auto current = state.load();
    if (current == State::idle || current == State::fallback) return false;
    result = current == State::playing;
    return true;
}

std::string CurrentSubtitle() {
    std::lock_guard lock(playback_mutex);
    if (!Playing()) return {};
    const auto time = playback_ms.load();
    for (const auto& cue : subtitles) {
        if (time < cue.start) break;
        if (time >= cue.end) continue;
        if (!subtitle_displayed) {
            subtitle_displayed = true;
            Log("displaying original cinematic subtitles on the enhanced video clock");
        }
        return cue.text;
    }
    return {};
}

bool Result(uint32_t movie, uint32_t& result) {
    if (!movie || active_movie.load() != movie) return false;
    switch (state.load()) {
    case State::opening:
    case State::playing: result = 0; return true;
    case State::ended: result = 1; return true;
    case State::skipped: result = 2; return true;
    default: return false;
    }
}

void Close(uint32_t movie) {
    std::lock_guard lock(playback_mutex);
    if (!movie || active_movie.load() != movie) return;
    std::fprintf(stderr, "[cinematic-pc] original subtitle cues: %zu\n", subtitles.size());
    std::fflush(stderr);
    active_movie.store(0);
    state.store(State::idle);
}
}
