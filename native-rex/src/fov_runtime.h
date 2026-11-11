#pragma once
// Applies the Field of View preference to the gameplay camera. sub_82166B08
// uploads the engine's matrices as vertex shader constants (sub_8247AF40).
// Around each upload (Scope), the gameplay projection in the source is
// recognised by its exact layout, rescaled for the upload, then restored, so
// the engine's own matrix is unchanged and nothing accumulates.
#include "fov_setting.h"
#include <rex/logging.h>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <stdlib.h>

namespace ben10::fov {
inline std::atomic<int> offset{0};  // Degrees added to the game's vertical FOV.

inline uint32_t LoadBits(const uint8_t* base, uint32_t address) {
  uint32_t bits;
  std::memcpy(&bits, base + address, 4);
  return _byteswap_ulong(bits);
}
inline float LoadFloat(const uint8_t* base, uint32_t address) {
  const uint32_t bits = LoadBits(base, address);
  float value;
  std::memcpy(&value, &bits, 4);
  return value;
}
inline void StoreBits(uint8_t* base, uint32_t address, uint32_t bits) {
  bits = _byteswap_ulong(bits);
  std::memcpy(base + address, &bits, 4);
}
inline void StoreFloat(uint8_t* base, uint32_t address, float value) {
  uint32_t bits;
  std::memcpy(&bits, &value, 4);
  StoreBits(base, address, bits);
}

// Gameplay projection (measured): row-major perspective, 16:9, near 0.2 and
// far 4000, i.e. m10 = far / (near - far) and m14 = near * far / (near - far).
inline bool GameplayProjection(const float* m) {
  for (int i : {1, 2, 3, 4, 6, 7, 8, 9, 12, 13, 15})
    if (m[i] != 0.0f) return false;
  return m[0] > 0.1f && m[5] > 0.1f && std::fabs(m[0] / m[5] - 0.5625f) < 0.002f &&
         std::fabs(m[11] + 1.0f) < 1e-4f && std::fabs(m[10] + 1.00005f) < 2e-5f &&
         std::fabs(m[14] + 0.20001f) < 2e-4f;
}

class Scope {
 public:
  Scope(uint8_t* base, uint32_t source, uint32_t vectors) : base_(base) {
    const int degrees = offset.load(std::memory_order_relaxed);
    if (!degrees || !source || vectors < 4 || vectors > 256) return;
    for (uint32_t first = 0; first + 4 <= vectors && count_ < 4; ++first) {
      const uint32_t at = source + first * 16;
      float m[16];
      for (int i = 0; i < 16; ++i) m[i] = LoadFloat(base, at + i * 4);
      if (!GameplayProjection(m)) continue;
      constexpr double kRadians = 3.14159265358979 / 180;
      const double vertical = 2 * std::atan(1.0 / m[5]);
      const double wanted = std::clamp(vertical + degrees * kRadians, 20 * kRadians, 120 * kRadians);
      const double y_scale = 1.0 / std::tan(wanted / 2);
      patches_[count_++] = {at, LoadBits(base, at), LoadBits(base, at + 20)};
      StoreFloat(base, at, float(m[0] * y_scale / m[5]));
      StoreFloat(base, at + 20, float(y_scale));
      static std::atomic<bool> logged{false};
      if (!logged.exchange(true))
        REXLOG_INFO("FOV applied: gameplay vertical FOV {:.2f} -> {:.2f} degrees", vertical / kRadians, wanted / kRadians);
      first += 3;
    }
  }
  ~Scope() {
    for (int i = 0; i < count_; ++i) {
      StoreBits(base_, patches_[i].address, patches_[i].x_scale);
      StoreBits(base_, patches_[i].address + 20, patches_[i].y_scale);
    }
  }
  Scope(const Scope&) = delete;
  Scope& operator=(const Scope&) = delete;

 private:
  struct Patch { uint32_t address, x_scale, y_scale; };
  uint8_t* base_;
  Patch patches_[4]{};
  int count_ = 0;
};
}
