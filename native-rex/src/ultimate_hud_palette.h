#pragma once

#include <atomic>
#include <cstdint>

namespace ben10::ultimate_hud {
inline std::atomic<bool> active{false};
inline thread_local uint32_t texture_key = 0;

// The circular HUD's foreground bind supplies the original asset key.
// Scope it to that bind so other draws using the same texture stay original.
class ForegroundBind {
 public:
  explicit ForegroundBind(uint32_t key) : previous_(texture_key) { texture_key = key; }
  ~ForegroundBind() { texture_key = previous_; }

 private:
  uint32_t previous_;
};

constexpr uint32_t Recolor(uint32_t fetch, uint32_t key) {
  constexpr uint32_t rgb_mask = 0x1ff << 1;
  constexpr uint32_t zero = 4;
  const uint32_t red = (fetch >> 1) & 7;
  const uint32_t green = (fetch >> 4) & 7;
  if (key == 0x8baf8b68)  // Orange health arc.
    return (fetch & ~rgb_mask) | (red << 1) | (zero << 4) | (zero << 7);
  if (key == 0x747d478c)  // Cyan energy arc.
    return (fetch & ~rgb_mask) | (green << 1) | (green << 4) | (zero << 7);
  return fetch;
}

inline uint32_t FetchWord(uint32_t fetch) {
  return texture_key && active.load(std::memory_order_relaxed) ? Recolor(fetch, texture_key) : fetch;
}
}
