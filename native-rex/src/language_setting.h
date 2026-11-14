#pragma once

// The interface/subtitle language chosen in the launcher or the in-game Video menu. Stored as the
// `language` key of user/pc-video.ini, one of kCodes; English when unset.
#include <atomic>
#include <cstring>
#include <string>

namespace ben10::language {
inline constexpr int kCount = 10;
inline constexpr const char* kCodes[kCount] = {"en", "ar", "de", "fr", "es", "it", "pt", "tr", "ru", "ja"};
inline std::atomic<int> current{0};
// Set when the language changed, until the title menu has been rebuilt with the new text.
inline std::atomic<bool> menus_dirty{false};
// True while the game's text is being rewritten for a language change.
inline std::atomic<bool> swapping{false};

inline int IndexOf(const std::string& code) {
    for (int i = 0; i < kCount; ++i)
        if (code == kCodes[i]) return i;
    return 0;
}
inline const char* Code() { return kCodes[current.load()]; }
}  // namespace ben10::language
