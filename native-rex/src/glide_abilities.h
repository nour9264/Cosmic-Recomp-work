#pragma once

// Double jump and glide for imported aliens that carry Big Chill's glide
// settings (Jetray); Goop takes only the double jump speed, so only the double jump. The controller's ability mask (profile +448) is what lets a
// jump press in the air reach the jump code (bit 0x4) and lets the jump button
// held start the glide (bit 0x2000, tested by sub_8212D028 and sub_8212CF00).
// An imported alien's mask is Four Arms' (0x11003), so the bits are added here.

#include <cstdint>
#include <cstring>
#include <intrin.h>

namespace ben10::glide_abilities {
constexpr uint32_t kDoubleJump = 0x4, kGlide = 0x2000;

inline bool Valid(uint32_t guest) { return guest >= 0x10000 && guest < 0xe0000000u; }

inline uint32_t Load(const uint8_t* base, uint32_t guest) {
    uint32_t value;
    std::memcpy(&value, base + guest, 4);
    return _byteswap_ulong(value);
}

inline float LoadFloat(const uint8_t* base, uint32_t guest) {
    const uint32_t bits = Load(base, guest);
    float value;
    std::memcpy(&value, &bits, 4);
    return value;
}

// sub_8212DAB0 (player controller update), once per frame: `controller` holds
// the profile at +0 and the character at +4. A movement record with Big Chill's
// glide block (0x10c = 2.0) and double jump speed (+68 >= 5.7) marks a glider;
// one with only the double jump speed (Goop) gets the double jump alone.
inline void Grant(uint32_t controller, uint8_t* base) {
    const uint32_t profile = Load(base, controller);
    if (!Valid(profile)) return;
    const uint32_t mask = Load(base, profile + 448);
    if ((mask & (kDoubleJump | kGlide)) == (kDoubleJump | kGlide)) return;
    const uint32_t character = Load(base, controller + 4);
    if (!Valid(character)) return;
    const uint32_t person = Load(base, character + 24);
    if (!Valid(person) || LoadFloat(base, person + 68) < 5.7f) return;
    const uint32_t wanted = kDoubleJump | (LoadFloat(base, person + 0x10c) == 2.0f ? kGlide : 0);
    if ((mask & wanted) == wanted) return;
    const uint32_t granted = _byteswap_ulong(mask | wanted);
    std::memcpy(base + profile + 448, &granted, 4);
}
}  // namespace ben10::glide_abilities
