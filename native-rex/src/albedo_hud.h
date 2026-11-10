#pragma once

#include <atomic>
#include <cstdint>

namespace ben10::albedo_hud {
inline std::atomic<bool> enabled{false};
inline thread_local uint32_t texture_key = 0;

constexpr bool IsHudTexture(uint32_t key) {
  switch (key) {
    // Ultimatrix center, alien selection sectors, and ability meter.
    case 0xa3ebddb4: case 0x6b0b52c4: case 0xd1705932:
    case 0x49d1887f: case 0xdf6d36ea:
    // Gameplay hint and notification frame.
    case 0xb6533e88: case 0xc0506422: case 0xba606b94:
    // Combo score background, without tinting the white score text.
    case 0x11cb01a4:
    // Gameplay menus: frame pieces, circular emblem, panels and accents.
    case 0xdd9f6764:  // Full-screen edge glow shared by pause and main menus.
    // The stock bezel, left ruler, and startup beam use the Albedo texture pack.
    case 0x85b1f8ee: case 0xb37bc727: case 0x0be29da8:
    case 0x060a0de2: case 0xf83b4ff3: case 0x3f9c7f9d:
    case 0x4122e4ab: case 0xf30238bb: case 0xc23d2509:
    case 0x38d9f43e: case 0x219d8654: case 0xca40fca7:
    case 0xd3505fdf: case 0xe514806e:
    case 0xd874a9de:
    case 0x799c0966: case 0x17c3c33d: case 0xe4f5ae94:  // Animated ring shared by startup and the main menu.
    case 0x494961d5: case 0xd3167483: case 0x2b9620d5: case 0x2e40c95d:
    case 0xdd7f9ba7: case 0x74847323: case 0x9f7334ec:
    case 0x9d979a7e:
    case 0x19e28fc1:  // Menu selection arrows.
    case 0x89c26bdb: case 0x11e4766a:  // Green menu arc textures.
    // Form selection ring, locked portrait, and the original visor holograms.
    case 0xa1a47c4c: case 0xa887e528:
    // Visor projector beam and base emblem, plus the Upgrades/DNA panel.
    case 0x2980ac11: case 0x346973c3:
    case 0x50a872a6: case 0xc1e52d91: case 0xce62110b:
    case 0x4592155d: case 0x02326f8d: case 0x3f52463d:
    case 0x8d729a2d: case 0xb012b39d: case 0xf7b2c94d:
    case 0xcad2e0fd: case 0x4882772c: case 0x75e25e9c:
    case 0xb3aeef48: case 0x8ecec6f8: case 0xc96ebc28:
    case 0xf40e9598: case 0x462e4988: case 0x7b4e6038:
    case 0x3cee1ae8: case 0x018e3358: case 0x83dea489:
    case 0xbebe8d39:
    // Special attack pictograms from the original gameplay and form tables.
    case 0x0137a091: case 0x89af0267: case 0x93eb00b0:
    case 0xd44b7a60: case 0x47f5d4c7:
      return true;
    default:
      return false;
  }
}

class TextureBind {
 public:
  explicit TextureBind(uint32_t key) : previous_(texture_key) { texture_key = key; }
  ~TextureBind() { texture_key = previous_; }

 private:
  uint32_t previous_;
};

constexpr uint32_t SwapRedGreen(uint32_t fetch) {
  constexpr uint32_t red_green = (7 << 1) | (7 << 4);
  return (fetch & ~red_green) | ((fetch & (7 << 1)) << 3) | ((fetch & (7 << 4)) >> 3);
}

inline uint32_t FetchWord(uint32_t fetch) {
  return IsHudTexture(texture_key) && enabled.load(std::memory_order_relaxed)
      ? SwapRedGreen(fetch) : fetch;
}
}
