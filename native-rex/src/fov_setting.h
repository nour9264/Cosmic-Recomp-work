#pragma once
// Field of View preference, shared by the launcher and the game. Stored in
// user/pc-gameplay.ini as fov=<degrees added to the game's own FOV>; 0 (the
// default) keeps the original camera exactly.
#include <windows.h>
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace ben10::fov {
inline constexpr int kMin = -20, kMax = 30;

inline int Clamp(int offset) { return std::clamp(offset, kMin, kMax); }

// "Original", or a signed number of degrees.
inline std::string Label(int offset) {
  if (!offset) return "Original";
  return (offset > 0 ? "+" : "") + std::to_string(offset) + "\xC2\xB0";
}

inline int Read(const std::filesystem::path& file) {
  std::ifstream input(file);
  int offset = 0;
  for (std::string line; std::getline(input, line);) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.rfind("fov=", 0) == 0) {
      try { offset = std::stoi(line.substr(4)); } catch (...) { offset = 0; }
    }
  }
  return Clamp(offset);
}

// Rewrites only the fov line; every other preference is kept as it was.
inline bool Save(const std::filesystem::path& file, int offset) {
  std::vector<std::string> lines;
  {
    std::ifstream input(file);
    for (std::string line; std::getline(input, line);) {
      if (!line.empty() && line.back() == '\r') line.pop_back();
      if (line.rfind("fov=", 0) != 0) lines.push_back(line);
    }
  }
  lines.push_back("fov=" + std::to_string(Clamp(offset)));
  auto temporary = file;
  temporary += L".fov.tmp";
  {
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    for (const auto& line : lines) output << line << "\r\n";  // The game writes CRLF.
    output.close();
    if (!output) return false;
  }
  return MoveFileExW(temporary.c_str(), file.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != FALSE;
}
}
