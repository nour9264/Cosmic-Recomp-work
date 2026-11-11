#include "music_session.h"

#include <rex/audio/downmix.h>
#include <rex/logging.h>

#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Graphics.Imaging.h>
#include <winrt/Windows.Media.Control.h>
#include <winrt/Windows.Storage.Streams.h>

#include <algorithm>
#include <chrono>
#include <mutex>
#include <thread>

namespace ben10::music {
namespace {
using namespace winrt::Windows::Media::Control;
using winrt::Windows::Storage::Streams::IRandomAccessStreamReference;
using Clock = std::chrono::steady_clock;

std::mutex state_mutex;
Snapshot snapshot;
Settings settings;
std::filesystem::path settings_path;
std::vector<uint8_t> artwork;  // Guarded by state_mutex.
std::atomic<int> pending_command{0};
std::atomic<bool> overlay_open{false};
std::atomic<bool> running{false};
std::thread worker;

std::string Narrow(const winrt::hstring& text) { return winrt::to_string(text); }

std::string AppName(std::string id) {
  // AUMIDs look like "Spotify.exe" or "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify".
  if (const auto bang = id.rfind('!'); bang != std::string::npos) id = id.substr(bang + 1);
  if (id.size() > 4 && _stricmp(id.c_str() + id.size() - 4, ".exe") == 0) id.resize(id.size() - 4);
  return id;
}

Status Convert(GlobalSystemMediaTransportControlsSessionPlaybackStatus status) {
  switch (status) {
    case GlobalSystemMediaTransportControlsSessionPlaybackStatus::Playing: return Status::playing;
    case GlobalSystemMediaTransportControlsSessionPlaybackStatus::Paused: return Status::paused;
    case GlobalSystemMediaTransportControlsSessionPlaybackStatus::Stopped:
    case GlobalSystemMediaTransportControlsSessionPlaybackStatus::Closed: return Status::stopped;
    default: return Status::none;
  }
}

// A session counts as playing only when it reports Playing; an open idle app does not.
GlobalSystemMediaTransportControlsSession Choose(const GlobalSystemMediaTransportControlsSessionManager& manager) {
  for (const auto& session : manager.GetSessions())
    if (session.GetPlaybackInfo().PlaybackStatus() ==
        GlobalSystemMediaTransportControlsSessionPlaybackStatus::Playing) return session;
  return manager.GetCurrentSession();
}

Snapshot Read(const GlobalSystemMediaTransportControlsSession& session, IRandomAccessStreamReference& thumbnail) {
  Snapshot result;
  thumbnail = nullptr;
  if (!session) return result;
  const auto info = session.GetPlaybackInfo();
  result.status = Convert(info.PlaybackStatus());
  const auto controls = info.Controls();
  result.can_previous = controls.IsPreviousEnabled();
  result.can_next = controls.IsNextEnabled();
  result.can_toggle = controls.IsPlayPauseToggleEnabled() || controls.IsPlayEnabled() || controls.IsPauseEnabled();
  result.app = AppName(Narrow(session.SourceAppUserModelId()));
  try {
    const auto properties = session.TryGetMediaPropertiesAsync().get();
    if (properties) {
      result.title = Narrow(properties.Title());
      result.artist = Narrow(properties.Artist());
      thumbnail = properties.Thumbnail();
    }
  } catch (...) {}
  try {
    const auto timeline = session.GetTimelineProperties();
    const double end = std::chrono::duration<double>(timeline.EndTime() - timeline.StartTime()).count();
    double position = std::chrono::duration<double>(timeline.Position() - timeline.StartTime()).count();
    // Players update the timeline occasionally; extrapolate while playing.
    if (result.status == Status::playing)
      position += std::chrono::duration<double>(winrt::clock::now() - timeline.LastUpdatedTime()).count();
    if (end > 0) {
      result.duration = end;
      result.position = std::clamp(position, 0.0, end);
    }
  } catch (...) {}
  return result;
}

// Album art: decoded once per track to a center-cropped square.
std::vector<uint8_t> Decode(const IRandomAccessStreamReference& thumbnail) {
  using namespace winrt::Windows::Graphics::Imaging;
  const auto stream = thumbnail.OpenReadAsync().get();
  const auto decoder = BitmapDecoder::CreateAsync(stream).get();
  const uint32_t width = decoder.OrientedPixelWidth(), height = decoder.OrientedPixelHeight();
  if (!width || !height) return {};
  const double scale = double(kArtworkSize) / std::min(width, height);
  const uint32_t scaled_width = std::max(kArtworkSize, uint32_t(width * scale + 0.5));
  const uint32_t scaled_height = std::max(kArtworkSize, uint32_t(height * scale + 0.5));
  BitmapTransform transform;
  transform.ScaledWidth(scaled_width);
  transform.ScaledHeight(scaled_height);
  transform.InterpolationMode(BitmapInterpolationMode::Fant);
  transform.Bounds({(scaled_width - kArtworkSize) / 2, (scaled_height - kArtworkSize) / 2, kArtworkSize, kArtworkSize});
  const auto data = decoder.GetPixelDataAsync(BitmapPixelFormat::Rgba8, BitmapAlphaMode::Straight, transform,
                                              ExifOrientationMode::RespectExifOrientation,
                                              ColorManagementMode::ColorManageToSRgb).get();
  const auto pixels = data.DetachPixelData();
  if (pixels.size() != kArtworkSize * kArtworkSize * 4) return {};
  return {pixels.begin(), pixels.end()};
}

void Execute(const GlobalSystemMediaTransportControlsSession& session, int command) {
  if (!session) return;
  switch (Command(command)) {
    case Command::previous: session.TrySkipPreviousAsync().get(); break;
    case Command::toggle: session.TryTogglePlayPauseAsync().get(); break;
    case Command::next: session.TrySkipNextAsync().get(); break;
  }
}

void Run() {
  winrt::init_apartment(winrt::apartment_type::multi_threaded);
  GlobalSystemMediaTransportControlsSessionManager manager{nullptr};
  GlobalSystemMediaTransportControlsSession session{nullptr};
  Clock::time_point next_poll{}, playing_since{}, quiet_since{};
  float gain = 1.0f;
  Status logged_status = Status::none;
  std::string logged_title;
  // Players often publish the thumbnail a moment after the title, so retry a few polls.
  std::string art_key;
  int art_attempts = 0;
  uint32_t art_id = 0;
  bool has_art = false;
  auto last = Clock::now();
  while (running.load()) {
    const auto now = Clock::now();
    const float seconds = std::chrono::duration<float>(now - last).count();
    last = now;
    Settings current;
    {
      std::lock_guard lock(state_mutex);
      current = settings;
    }
    const bool watch = current.integration;
    Snapshot fresh;
    IRandomAccessStreamReference thumbnail{nullptr};
    bool refreshed = false;
    const int command = pending_command.exchange(0);
    if (watch && (now >= next_poll || command)) {
      next_poll = now + std::chrono::milliseconds(500);
      try {
        if (!manager) manager = GlobalSystemMediaTransportControlsSessionManager::RequestAsync().get();
        session = Choose(manager);
        if (command) {
          Execute(session, command);
          session = Choose(manager);
        }
        fresh = Read(session, thumbnail);
      } catch (...) {
        manager = nullptr;  // Recreated on the next poll.
        session = nullptr;
        fresh = Snapshot{};
      }
      refreshed = true;
    } else if (!watch) {
      session = nullptr;
      refreshed = true;
    }
    if (refreshed) {
      const std::string key = fresh.app + '|' + fresh.title + '|' + fresh.artist;
      if (key != art_key) {
        art_key = key;
        art_attempts = 0;
        if (has_art) {
          has_art = false;
          std::lock_guard lock(state_mutex);
          artwork.clear();
        }
      }
      if (!has_art && thumbnail && art_attempts < 6) {
        ++art_attempts;
        std::vector<uint8_t> pixels;
        try { pixels = Decode(thumbnail); } catch (...) {}
        if (!pixels.empty()) {
          has_art = true;
          ++art_id;
          std::lock_guard lock(state_mutex);
          artwork = std::move(pixels);
        }
      }
      if (has_art) fresh.artwork = art_id;
      if (fresh.status != logged_status || fresh.title != logged_title) {
        REXLOG_INFO("Music: {} {} - {} ({})", fresh.app.empty() ? "no session" : fresh.app,
                    int(fresh.status), fresh.title, fresh.artist);
        logged_status = fresh.status;
        logged_title = fresh.title;
      }
      std::lock_guard lock(state_mutex);
      snapshot = fresh;
    }

    // Ducking: only after playback is steady, and restore only after it has
    // stayed quiet, so track changes do not make the game audio bounce.
    Status status;
    {
      std::lock_guard lock(state_mutex);
      status = snapshot.status;
    }
    const bool playing = watch && status == Status::playing;
    if (playing) {
      if (playing_since == Clock::time_point{}) playing_since = now;
      quiet_since = {};
    } else {
      if (quiet_since == Clock::time_point{}) quiet_since = now;
      playing_since = {};
    }
    static bool ducked = false;
    if (playing && now - playing_since > std::chrono::milliseconds(300)) ducked = true;
    if (!playing && now - quiet_since > std::chrono::milliseconds(1500)) ducked = false;
    const float target = ducked ? (100 - current.priority) / 100.0f : 1.0f;
    const float step = seconds / 0.6f;  // Full fade in about 0.6 s.
    const float next = gain + std::clamp(target - gain, -step, step);
    if (next != gain) {
      gain = next;
      rex::audio::SetOutputGain(gain);
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }
  rex::audio::SetOutputGain(1.0f);
  winrt::uninit_apartment();
}
}

void Start(const std::filesystem::path& settings_file) {
  if (running.exchange(true)) return;
  settings_path = settings_file;
  {
    std::lock_guard lock(state_mutex);
    settings = ReadSettings(settings_file);
  }
  worker = std::thread(Run);
}

void Stop() {
  if (!running.exchange(false)) return;
  if (worker.joinable()) worker.join();
}

Snapshot Current() {
  std::lock_guard lock(state_mutex);
  return snapshot;
}

bool Artwork(std::vector<uint8_t>& rgba) {
  std::lock_guard lock(state_mutex);
  if (artwork.empty()) return false;
  rgba = artwork;
  return true;
}

void Request(Command command) { pending_command.store(int(command)); }

Settings CurrentSettings() {
  std::lock_guard lock(state_mutex);
  return settings;
}

void UpdateSettings(const Settings& updated) {
  {
    std::lock_guard lock(state_mutex);
    settings = updated;
  }
  if (!settings_path.empty() && !SaveSettings(settings_path, updated))
    REXLOG_ERROR("Music: could not save {}", settings_path.string());
}

void SetOverlayOpen(bool open) { overlay_open.store(open); }
}
