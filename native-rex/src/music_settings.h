#pragma once
// Smart Music Integration preferences, in user/pc-sound.ini (key=value, like
// the other pc-*.ini files). Read by the game, the in-game Sound page and the
// launcher's Sound tab.
#include <windows.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace ben10::music {
struct Settings {
  // Media detection, the overlay shortcut and ducking all follow this switch.
  bool integration = true;
  // How far game audio drops while external music plays: the ducked game
  // volume is 100 - priority percent. 0 leaves the game audio alone.
  int priority = 70;
};

inline Settings ReadSettings(const std::filesystem::path& file) {
  Settings settings;
  std::ifstream input(file);
  bool has_priority = false;
  for (std::string line; std::getline(input, line);) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    const auto split = line.find('=');
    if (split == std::string::npos) continue;
    const auto key = line.substr(0, split), value = line.substr(split + 1);
    if (key == "music_integration") settings.integration = value != "off";
    try {
      if (key == "music_priority") { settings.priority = std::clamp(std::stoi(value), 0, 100); has_priority = true; }
      // Earlier test builds stored the ducked game volume instead.
      if (key == "music_ducking_level" && !has_priority) settings.priority = 100 - std::clamp(std::stoi(value), 0, 100);
    } catch (...) {}
  }
  return settings;
}

inline bool SaveSettings(const std::filesystem::path& file, const Settings& settings) {
  auto temporary = file;
  temporary += L".tmp";
  {
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    output << "music_integration=" << (settings.integration ? "on" : "off") << "\r\n"
           << "music_priority=" << std::clamp(settings.priority, 0, 100) << "\r\n";
    output.close();
    if (!output) return false;
  }
  return MoveFileExW(temporary.c_str(), file.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != FALSE;
}
}
