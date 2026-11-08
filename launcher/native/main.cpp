// Cosmic-specific launcher using Dear ImGui, SDL and the recomp-ui image loader.
#include <windows.h>
#include <SDL3/SDL.h>
#include <SDL3/SDL_opengl.h>
#include "imgui.h"
#include "backends/imgui_impl_sdl3.h"
#include "backends/imgui_impl_opengl3.h"
#include "common/launcher_gl.h"
#include <filesystem>
#include <fstream>
#include <string>
#include <algorithm>
#include <vector>
#include <charconv>
#include "../cosmic_window_icon.h"

namespace fs = std::filesystem;
static fs::path root;
static std::string read(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(file), {});
}
static fs::path installation() {
    std::string chosen = read(root / "installation-path.txt");
    while (!chosen.empty() && (chosen.back() == '\r' || chosen.back() == '\n')) chosen.pop_back();
    return chosen.empty() ? root / "installation" : fs::u8path(chosen);
}
static bool ready() {
    auto folder = installation();
    return fs::exists(folder / "installed.txt") && fs::exists(folder / "game/default.xex") && fs::exists(root / "runtime/ben10.exe");
}
static PROCESS_INFORMATION worker{};
static bool game = false;
static std::string status = "Select your own ISO in Settings to get started.";
static bool spawn(const wchar_t* action) {
    auto bridge = root / "CosmicBridge.exe";
    auto fourArmsBridge = root / "CosmicFourArmsBridge.exe";
    if (std::wstring(action) == L"play" && fs::exists(installation()/"four-arms") && fs::exists(fourArmsBridge))
        bridge = fourArmsBridge;
    std::wstring command = L"\"" + bridge.wstring() + L"\" " + action;
    if(std::wstring(action)==L"play")command+=L" --parent "+std::to_wstring(GetCurrentProcessId());
    STARTUPINFOW startup{}; startup.cb = sizeof(startup);
    if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, 0, nullptr, root.c_str(), &startup, &worker)) {
        status = "Could not start CosmicBridge.exe. Extract the complete package."; return false;
    }
    CloseHandle(worker.hThread); worker.hThread = nullptr;
    game = std::wstring(action) == L"play"; return true;
}
static bool action_button(const char* label, float width, bool primary = false) {
    if (primary) {
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(.63f,.94f,.23f,1));
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(.75f,1,.36f,1));
        ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(.51f,.80f,.17f,1));
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(.07f,.12f,.04f,1));
    }
    bool clicked = ImGui::Button(label, ImVec2(width, primary ? 62.f : 43.f));
    if (primary) {
        const ImVec2 lo = ImGui::GetItemRectMin(), hi = ImGui::GetItemRectMax();
        const float x = (lo.x+hi.x-ImGui::CalcTextSize(label).x)*.5f-19;
        const float y = (lo.y+hi.y)*.5f;
        ImGui::GetWindowDrawList()->AddTriangleFilled(ImVec2(x,y-7), ImVec2(x,y+7),
            ImVec2(x+11,y), ImGui::GetColorU32(ImGuiCol_Text));
    }
    if (primary) ImGui::PopStyleColor(4);
    return clicked;
}

static void draw_artwork(ImDrawList* draw, ImTextureID texture, int width, int height,
                         ImVec2 origin, ImVec2 size, int opacity) {
    const float source = float(width) / height, target = size.x / size.y;
    ImVec2 uv0(0,0), uv1(1,1);
    if (source > target) { uv0.x = (1-target/source)*.5f; uv1.x = 1-uv0.x; }
    else { uv0.y = (1-source/target)*.5f; uv1.y = 1-uv0.y; }
    draw->AddImage(texture, origin, ImVec2(origin.x+size.x,origin.y+size.y), uv0, uv1,
                   IM_COL32(255,255,255,opacity));
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR args, int) {
    wchar_t module[32768]; GetModuleFileNameW(nullptr, module, 32768);
    root = fs::path(module).parent_path();
    bool smoke = std::wstring(args).find(L"--smoke-test") != std::wstring::npos;
    // A process-scoped mutex protects preferences and import status from races.
    std::wstring mutexName = L"Local\\CosmicRecompNative-" + std::to_wstring(std::hash<std::wstring>{}(root.wstring()));
    HANDLE instance = CreateMutexW(nullptr, TRUE, mutexName.c_str());
    if (!instance || GetLastError() == ERROR_ALREADY_EXISTS) { if (instance) CloseHandle(instance); return 0; }
    fs::current_path(root);
    fs::create_directories(root/"temp");
    SetEnvironmentVariableW(L"TEMP",(root/"temp").c_str());
    SetEnvironmentVariableW(L"TMP",(root/"temp").c_str());
    // Always show the launcher. Legacy direct-start preferences are ignored.
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_GAMEPAD)) { MessageBoxA(nullptr, SDL_GetError(), "Cosmic Recomp", MB_ICONERROR); CloseHandle(instance); return 1; }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3); SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_Window* window = SDL_CreateWindow("Cosmic Recomp", 1100, 840, SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY | (smoke ? SDL_WINDOW_HIDDEN : 0));
    if (window) {
        auto properties = SDL_GetWindowProperties(window);
        SetCosmicWindowIcon(static_cast<HWND>(SDL_GetPointerProperty(properties, SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr)));
    }
    if (!window) { MessageBoxA(nullptr, SDL_GetError(), "Cosmic Recomp", MB_ICONERROR); SDL_Quit(); CloseHandle(instance); return 1; }
    SDL_SetWindowMinimumSize(window, 680, 520);
    SDL_Rect usable{};
    if(SDL_GetDisplayUsableBounds(SDL_GetDisplayForWindow(window),&usable))
        SDL_SetWindowSize(window,std::min(1100,std::max(680,usable.w-60)),std::min(840,std::max(520,usable.h-60)));
    SDL_GLContext context = SDL_GL_CreateContext(window);
    if (!context) { MessageBoxA(nullptr, SDL_GetError(), "Cosmic Recomp", MB_ICONERROR); SDL_DestroyWindow(window); SDL_Quit(); CloseHandle(instance); return 1; }
    SDL_GL_MakeCurrent(window, context); SDL_GL_SetSwapInterval(1);
    ImGui::CreateContext(); auto& io = ImGui::GetIO();
    io.IniFilename = nullptr; io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
    // Load the OS font read-only; all writable state remains beside the launcher.
    wchar_t windows[MAX_PATH]; GetWindowsDirectoryW(windows, MAX_PATH);
    fs::path font = fs::path(windows) / "Fonts/segoeui.ttf";
    io.Fonts->AddFontFromFileTTF(font.u8string().c_str(), 19);
    fs::path bold = fs::path(windows) / "Fonts/segoeuib.ttf";
    ImFont* heading = io.Fonts->AddFontFromFileTTF(bold.u8string().c_str(), 76);
    ImFont* compactHeading = io.Fonts->AddFontFromFileTTF(bold.u8string().c_str(), 55);
    ImFont* subtitle = io.Fonts->AddFontFromFileTTF(bold.u8string().c_str(), 38);
    ImFont* primaryLabel = io.Fonts->AddFontFromFileTTF(bold.u8string().c_str(), 26);
    ImGui::StyleColorsDark(); auto& style = ImGui::GetStyle();
    style.WindowRounding = 0; style.ChildRounding = 14; style.FrameRounding = 8;
    style.TabRounding = 7; style.FramePadding = ImVec2(14, 9);
    style.ItemSpacing = ImVec2(12, 11); style.WindowPadding = ImVec2(19, 16);
    style.Colors[ImGuiCol_Text] = ImVec4(.94f,.97f,.92f,1);
    style.Colors[ImGuiCol_TextDisabled] = ImVec4(.56f,.65f,.57f,1);
    style.Colors[ImGuiCol_ChildBg] = ImVec4(.025f,.061f,.037f,.88f);
    style.Colors[ImGuiCol_PopupBg] = ImVec4(.055f,.10f,.08f,1);
    style.Colors[ImGuiCol_Border] = ImVec4(.27f,.40f,.28f,.6f);
    style.Colors[ImGuiCol_FrameBg] = ImVec4(.09f,.15f,.12f,1);
    style.Colors[ImGuiCol_FrameBgHovered] = ImVec4(.14f,.24f,.17f,1);
    style.Colors[ImGuiCol_FrameBgActive] = ImVec4(.19f,.30f,.19f,1);
    style.Colors[ImGuiCol_Button] = ImVec4(.12f,.20f,.15f,1);
    style.Colors[ImGuiCol_ButtonHovered] = ImVec4(.20f,.31f,.20f,1);
    style.Colors[ImGuiCol_ButtonActive] = ImVec4(.27f,.38f,.20f,1);
    style.Colors[ImGuiCol_Header] = ImVec4(.22f,.34f,.15f,1);
    style.Colors[ImGuiCol_HeaderHovered] = ImVec4(.30f,.45f,.19f,1);
    style.Colors[ImGuiCol_HeaderActive] = ImVec4(.36f,.53f,.20f,1);
    style.Colors[ImGuiCol_Tab] = ImVec4(.10f,.17f,.12f,1);
    style.Colors[ImGuiCol_TabHovered] = ImVec4(.26f,.39f,.16f,1);
    style.Colors[ImGuiCol_TabSelected] = ImVec4(.21f,.31f,.15f,1);
    style.Colors[ImGuiCol_CheckMark] = ImVec4(.70f,.98f,.31f,1);
    style.Colors[ImGuiCol_NavCursor] = ImVec4(.70f,.98f,.31f,1);
    style.Colors[ImGuiCol_PlotHistogram] = ImVec4(.63f,.94f,.23f,1);
    ImGui_ImplSDL3_InitForOpenGL(window, context); ImGui_ImplOpenGL3_Init("#version 130");
    auto artwork = launcher_texture_load("assets/launcher/background.jpg");
    auto background = artwork.id ? LauncherAnimation{} : launcher_animation_load_gif("assets/launcher/background.gif");
    bool quit = false, settings = std::wstring(args).find(L"--settings") != std::wstring::npos; int frames = 0;
    int resolution = 0, rate = 0, displayMode=0;bool performanceOverlay=true;
    bool skipIntro = read(installation()/"user/skip-intro.txt") == "on";
    {
        std::ifstream file(installation()/"user/pc-video.ini"); std::string line;
        while(std::getline(file,line)) {
            if(!line.empty() && line.back()=='\r')line.pop_back();
            if(line=="resolution=1080p")resolution=1;
            if(line=="resolution=1440p")resolution=2;
            if(line=="resolution=4k")resolution=3;
            if(line=="frame_limit=60")rate=1;
            if(line=="frame_limit=unlimited")rate=2;
            if(line=="performance_overlay=off")performanceOverlay=false;
            if(line=="performance_overlay=on")performanceOverlay=true;
            if(line=="display_mode=borderless")displayMode=1;
            if(line=="display_mode=exclusive")displayMode=2;
        }
    }
    Uint64 nextStatusRead=0;
    if(ready())status="Ready to play.";
    while (!quit) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            ImGui_ImplSDL3_ProcessEvent(&event);
            if ((event.type == SDL_EVENT_QUIT || event.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED) && !worker.hProcess) quit = true;
            if (event.type == SDL_EVENT_KEY_DOWN && event.key.key == SDLK_ESCAPE) settings = false;
        }
        if (worker.hProcess && SDL_GetTicks()>=nextStatusRead) {
            nextStatusRead=SDL_GetTicks()+250;
            DWORD code;
            if (GetExitCodeProcess(worker.hProcess, &code) && code != STILL_ACTIVE) {
                CloseHandle(worker.hProcess); worker = {}; game = false;
                SDL_ShowWindow(window); SDL_RaiseWindow(window);
            }
            auto update = read(root / "launcher-status.txt"); if (!update.empty()) status = update;
        }
        if (game) { SDL_Delay(50); continue; } // No UI rendering/animation cost during gameplay.
        ImGui_ImplOpenGL3_NewFrame(); ImGui_ImplSDL3_NewFrame(); ImGui::NewFrame();
        auto* viewport = ImGui::GetMainViewport(); ImVec2 size = viewport->Size;
        auto* draw = ImGui::GetBackgroundDrawList();
        const float margin = size.x < 800 ? 32.f : 56.f;
        const float artStart = size.x * (settings ? .28f : .22f);
        const float footer = size.y - (settings ? 77 : 46);
        const ImVec4 accent(.71f,.97f,.34f,1), muted(.67f,.76f,.69f,1);
        const bool installed = ready();
        draw->AddRectFilledMultiColor(ImVec2(0,0), size, IM_COL32(8,21,16,255),
            IM_COL32(22,48,26,255), IM_COL32(9,23,17,255), IM_COL32(5,14,12,255));
        const ImVec2 artOrigin(artStart, 0), artSize(size.x-artStart, size.y);
        if (artwork.id)
            draw_artwork(draw, (ImTextureID)(intptr_t)artwork.id, artwork.w, artwork.h,
                         artOrigin, artSize, settings ? 111 : 223);
        if (background.id) {
            launcher_animation_update(&background, SDL_GetTicks());
            draw_artwork(draw, (ImTextureID)(intptr_t)background.id, background.w, background.h,
                         artOrigin, artSize, settings ? 65 : 135);
        }
        draw->AddRectFilled(ImVec2(0,0), ImVec2(artStart,size.y), IM_COL32(8,21,16,255));
        draw->AddRectFilledMultiColor(artOrigin, ImVec2(size.x*.65f,size.y),
            IM_COL32(8,21,16,255), IM_COL32(8,21,16,0), IM_COL32(8,21,16,0), IM_COL32(8,21,16,255));
        draw->AddRectFilledMultiColor(ImVec2(0,size.y-160), size,
            IM_COL32(5,14,12,0), IM_COL32(5,14,12,0), IM_COL32(5,14,12,217), IM_COL32(5,14,12,217));
        draw->AddLine(ImVec2(0,0), ImVec2(size.x,0), IM_COL32(117,180,43,210));
        if (settings) {
            draw->AddRectFilled(ImVec2(0,footer), size, IM_COL32(6,16,13,242));
            draw->AddLine(ImVec2(0,footer), ImVec2(size.x,footer), IM_COL32(66,98,64,190));
        }
        ImGui::SetNextWindowPos(ImVec2(0,0)); ImGui::SetNextWindowSize(size);
        ImGui::Begin("Cosmic", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoBackground |
            ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoScrollbar);
        const float menuWidth = settings ? std::min(700.f,size.x-margin*2) : std::min(366.f,size.x*.50f);
        const bool compact = size.y < 660 || size.x < 820;
        const float titleTop = settings ? 33.f : std::clamp((footer-425.f)*.47f, 22.f, 132.f);
        ImGui::SetCursorPos(ImVec2(margin,titleTop));
        ImGui::TextColored(accent, "%s", settings ? "COSMIC RECOMP  /  CONTROL PANEL" : "BEN 10  /  ULTIMATE ALIEN");
        const ImVec2 rule = ImGui::GetCursorScreenPos();
        ImGui::GetWindowDrawList()->AddRectFilled(ImVec2(margin,rule.y), ImVec2(margin+66,rule.y+3),
            ImGui::ColorConvertFloat4ToU32(accent), 1.5f);
        ImGui::Dummy(ImVec2(1,3));
        ImGui::SetCursorPosX(margin);
        ImGui::PushFont(settings ? subtitle : compact ? compactHeading : heading);
        ImGui::TextUnformatted(settings ? "Launcher settings" : "COSMIC\nRECOMP");
        ImGui::PopFont();
        if (!settings) {
            ImGui::SetCursorPosX(margin);
            ImGui::TextColored(muted, "Cosmic Destruction for Windows");
        }
        const float menuTop = ImGui::GetCursorPosY() + (settings ? 7.f : 15.f);
        ImGui::SetCursorPos(ImVec2(margin,menuTop));
        if (!settings) {
            const ImVec2 indicator = ImGui::GetCursorScreenPos();
            ImGui::GetWindowDrawList()->AddCircleFilled(ImVec2(indicator.x+5,indicator.y+ImGui::GetTextLineHeight()*.5f),
                4.5f, installed ? IM_COL32(161,244,49,255) : IM_COL32(225,184,83,255));
            ImGui::SetCursorPosX(margin+19);
            ImGui::TextColored(muted, "%s", installed ? "Ready to play" : "Setup required");
            ImGui::SetCursorPosX(margin);
            ImGui::BeginDisabled(worker.hProcess != nullptr);
            ImGui::PushFont(primaryLabel);
            const bool play = action_button("Play", menuWidth, true);
            ImGui::PopFont();
            ImGui::SetItemDefaultFocus();
            if (play) {
                if (!installed) { settings = true; status = "Select and validate your own ISO to get started."; }
                else if (spawn(L"play")) {
                    // The independent bridge owns the game's lifetime and lock.
                    // Destroy this frontend completely rather than keeping a hidden renderer.
                    CloseHandle(worker.hProcess); worker = {}; game = false; quit = true;
                }
            }
            ImGui::SetCursorPosX(margin);
            const float secondaryWidth = (menuWidth-style.ItemSpacing.x)*.5f;
            ImGui::PushStyleVar(ImGuiStyleVar_FrameBorderSize, 1.f);
            if (action_button("Settings", secondaryWidth)) settings = true;
            ImGui::SameLine();
            if (action_button("Quit", secondaryWidth)) quit = true;
            ImGui::PopStyleVar();
            ImGui::EndDisabled();
        } else {
            ImGui::BeginChild("menu", ImVec2(menuWidth, footer-menuTop-18), ImGuiChildFlags_Borders);
            ImGui::BeginDisabled(worker.hProcess != nullptr);
            if (ImGui::Button("Back")) settings=false;
            ImGui::Spacing();
            if (ImGui::BeginTabBar("Settings tabs")) {
                if (ImGui::BeginTabItem("Setup")) {
                    ImGui::Spacing();
                    ImGui::SeparatorText("Game files");
                    if (ImGui::Button("Select ISO")) spawn(L"select-iso");
                    ImGui::BeginDisabled(installed || !fs::exists(root/"selected-iso.txt"));
                    ImGui::SameLine(); if(ImGui::Button("Prepare game"))spawn(L"import");
                    ImGui::EndDisabled();
                    ImGui::TextWrapped("Select ISO, wait for validation, then prepare your game. Original game files stay on this computer.");
                    if (fs::exists(root/"CosmicFourArmsBridge.exe") &&
                        fs::exists(root/"four-arms-importer/prepare_four_arms_import.py")) {
                        ImGui::SeparatorText("Optional PS3 content");
                        ImGui::BeginDisabled(!installed || fs::exists(installation()/"four-arms"));
                        if (ImGui::Button("Import Four Arms")) spawn(L"import-four-arms");
                        ImGui::EndDisabled();
                        ImGui::TextWrapped("Select your extracted European PS3_GAME folder (BLES01110).");
                    }
                    ImGui::SeparatorText("Startup");
                    if (ImGui::Checkbox("Skip intro logos", &skipIntro)) {
                        auto path = installation()/"user/skip-intro.txt";
                        std::error_code error;
                        fs::create_directories(path.parent_path(), error);
                        auto temporary = path; temporary += L".tmp";
                        bool saved = false;
                        if (!error) {
                            std::ofstream file(temporary, std::ios::trunc);
                            file << (skipIntro ? "on" : "off");
                            file.close();
                            saved = bool(file) && MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
                        }
                        if (!saved) skipIntro = !skipIntro;
                        status = saved ? "Startup setting saved." : "Could not save startup setting.";
                    }
                    ImGui::EndTabItem();
                }
                if (ImGui::BeginTabItem("Video")) {
                    ImGui::Spacing();
                    ImGui::TextUnformatted("Output resolution");
                    ImGui::SetNextItemWidth(-1);
                    ImGui::Combo("##resolution",&resolution,"1280 x 720 (native)\0" "1920 x 1080\0" "2560 x 1440\0" "3840 x 2160\0");
                    ImGui::TextUnformatted("Frame limit");
                    ImGui::SetNextItemWidth(-1);
                    ImGui::Combo("##frame-limit",&rate,"30 FPS\0" "60 FPS\0" "Unlimited\0");
                    ImGui::TextUnformatted("Window mode");
                    ImGui::SetNextItemWidth(-1);
                    ImGui::Combo("##display-mode",&displayMode,"Windowed\0" "Borderless fullscreen\0" "Exclusive fullscreen\0");
                    ImGui::Checkbox("Show FPS and frame time",&performanceOverlay);
                    ImGui::TextWrapped("Applies when the game starts. 60 FPS is a limit, not a performance guarantee.");
                    if(ImGui::Button("Save video settings")) {
                        const char* resolutions[]={"720p","1080p","1440p","4k"};
                        auto path=installation()/"user/pc-video.ini";
                        std::error_code error; fs::create_directories(path.parent_path(),error);
                        bool saved=false;
                        if(!error) {
                            auto temporary=path;temporary+=L".launcher.tmp";
                            {std::ofstream file(temporary,std::ios::binary|std::ios::trunc);
                             file<<"resolution="<<resolutions[resolution]<<"\nframe_limit="<<(rate==2?"unlimited":rate==1?"60":"30")<<"\n";
                             file<<"performance_overlay="<<(performanceOverlay?"on":"off")<<"\n";
                             file<<"display_mode="<<(displayMode==2?"exclusive":displayMode==1?"borderless":"windowed")<<"\n";
                             file.flush();saved=bool(file);}
                            if(saved)saved=MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
                        }
                        status=saved?"Video settings saved.":"Could not save video settings. Check folder permissions.";
                    }
                    ImGui::EndTabItem();
                }
                if (ImGui::BeginTabItem("Patches & saves")) {
                    ImGui::Spacing();
                    ImGui::SeparatorText("Translation");
                    ImGui::BeginDisabled(!installed);
                    if(ImGui::Button("Add translation patch"))spawn(L"patch");
                    ImGui::EndDisabled();
                    ImGui::TextWrapped("Select the patch's global/scripts/xbx_us.txt file. Patches are supplied separately by their authors.");
                    ImGui::SeparatorText("Save data");
                    ImGui::TextWrapped("Save folder: %s",(installation()/"user").u8string().c_str());
                    ImGui::TextWrapped("Keep this folder when updating. To reset saves, close the game and rename user to user-backup.");
                    if(ImGui::Button("Open saves"))spawn(L"saves");
                    ImGui::EndTabItem();
                }
                ImGui::EndTabBar();
            }
            ImGui::EndDisabled();
            ImGui::EndChild();
        }
        ImGui::SetCursorPos(ImVec2(margin,footer+9));
        if (!settings) {
            if (status.rfind("Could not start",0)==0)
                ImGui::TextColored(muted, "%s", status.c_str());
            else
                ImGui::TextColored(muted, "FAN-MADE PC PORT");
        } else {
            ImGui::TextColored(accent, "%s", worker.hProcess ? "WORKING" : installed ? "GAME READY" : "SETUP REQUIRED");
            ImGui::SetCursorPosX(margin);
            if (status.rfind("Preparing: ",0)==0) {
                int percent=0;
                std::from_chars(status.data()+11,status.data()+status.size(),percent);
                ImGui::ProgressBar(std::clamp(percent,0,100)/100.f,ImVec2(size.x-margin*2,26),status.c_str());
            } else {
                ImGui::PushTextWrapPos(size.x-margin);
                ImGui::TextColored(muted, "%s", status.c_str());
                ImGui::PopTextWrapPos();
            }
        }
        ImGui::End(); ImGui::Render();
        int width, height; SDL_GetWindowSizeInPixels(window, &width, &height);
        glViewport(0,0,width,height); glClearColor(.02f,.05f,.04f,1); glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if (smoke && ++frames == 3) {
            std::vector<unsigned char> pixels(size_t(width)*height*4); glReadPixels(0,0,width,height,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
            std::vector<unsigned char> flipped(pixels.size());
            for (int y=0;y<height;y++) std::copy_n(pixels.data()+size_t(height-1-y)*width*4,size_t(width)*4,flipped.data()+size_t(y)*width*4);
            SDL_Surface* surface = SDL_CreateSurfaceFrom(width,height,SDL_PIXELFORMAT_RGBA32,flipped.data(),width*4);
            if (surface) { SDL_SaveBMP(surface,"launcher-preview.bmp"); SDL_DestroySurface(surface); } quit = true;
        }
        SDL_GL_SwapWindow(window); SDL_Delay(8);
    }
    launcher_texture_free(&artwork); launcher_animation_free(&background);
    ImGui_ImplOpenGL3_Shutdown(); ImGui_ImplSDL3_Shutdown(); ImGui::DestroyContext();
    SDL_GL_DestroyContext(context); SDL_DestroyWindow(window); SDL_Quit(); ReleaseMutex(instance); CloseHandle(instance); return 0;
}
