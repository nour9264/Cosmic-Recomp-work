#pragma once
#include <atomic>
#include <cstdint>
#include <rex/logging.h>

// sub_821EA860 builds an effect instance (sub_822313C8 returns it, or null when the handle could not be made) and then
// initialises it with sub_821EDF18, which reads the instance's flag byte at +6. With a null instance that read kills the
// game (seen on the double jump of Ultimate Swampfire). The code that follows the call already handles a null instance,
// so the call is skipped and the log says so.
namespace ben10::effect_guard {
inline void Skipped(uint32_t effect) {
  static std::atomic<unsigned> reports{0};
  if (reports.fetch_add(1) < 20) REXLOG_INFO("Effect guard: effect {:08X} could not be created; its set-up was skipped", effect);
}
}  // namespace ben10::effect_guard
