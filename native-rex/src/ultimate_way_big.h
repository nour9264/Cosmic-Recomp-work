#pragma once

#include <atomic>
#include <cstdint>
#include <cstdlib>

namespace ben10::ultimate_way_big {
inline constexpr uint32_t kBenMesh = 0xec5e50dc;
inline constexpr uint32_t kAlbedoMesh = 0x1e6840cb;
inline constexpr uint32_t kVertices = 16264;
inline const bool separate_form = std::getenv("BEN10_ULTIMATE_WAY_BIG_FORM") != nullptr;
inline std::atomic<bool> preload_requested{false};
inline std::atomic<bool> active{false};
inline std::atomic<bool> form_albedo{false};
inline std::atomic<bool> checking_model{false};
inline std::atomic<bool> request_pressed{false};
inline std::atomic<bool> l3_armed{false};
inline bool ObserveL3(bool eligible, bool down) {
  return l3_armed.exchange(eligible && !down, std::memory_order_relaxed) &&
      eligible && down;
}
inline std::atomic<uint64_t> ready_frame[2]{};
inline std::atomic<uint64_t> player_frame{0};
inline std::atomic<uint32_t> player_person{0};
inline double Damage(uint32_t attacker, uint32_t victim, double original) {
  const auto player = player_person.load(std::memory_order_relaxed);
  return active.load(std::memory_order_relaxed) && player != 0 &&
      attacker == player && victim != player && original > 0 ? original * 1.5 : original;
}
}
