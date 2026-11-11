#pragma once
// Smart Music Integration: Windows media sessions (Spotify and other players
// that publish to the system media controls) and game audio ducking. All
// WinRT work runs on one background thread (music_session.cpp); this header
// only exposes snapshots and requests, so the game thread never blocks.
#include "music_settings.h"
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace ben10::music {
enum class Status { none, stopped, paused, playing };

struct Snapshot {
  Status status = Status::none;
  std::string app, title, artist;
  double position = 0, duration = 0;  // Seconds; duration 0 when unknown.
  bool can_previous = false, can_toggle = false, can_next = false;
  uint32_t artwork = 0;  // Changes whenever new album art is ready; 0 when none.
};

constexpr uint32_t kArtworkSize = 128;  // Square RGBA8, center-cropped.

enum class Command { previous = 1, toggle, next };

void Start(const std::filesystem::path& settings_file);
void Stop();
Snapshot Current();
void Request(Command command);
bool Artwork(std::vector<uint8_t>& rgba);  // kArtworkSize^2 * 4 bytes; false when none.
Settings CurrentSettings();
void UpdateSettings(const Settings& settings);  // Saves and applies.
void SetOverlayOpen(bool open);  // Detection also runs while the overlay is open.
}

namespace ben10::music_overlay {
// Set by the controller shortcut (View / Share, Ben10FilterGameInput);
// consumed by the overlay on the UI side.
inline std::atomic<bool> toggle_request{false};
// Set when the overlay closes; View must be released before it can reopen it.
inline std::atomic<bool> view_latch{false};
}
