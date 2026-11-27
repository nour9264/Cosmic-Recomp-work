#pragma once
#include <atomic>
#include <cstdint>
#include <rex/logging.h>

// The game's script VM (member access opcode at 0x8223A31C) calls sub_82239138 with the object reference taken
// from a script variable. When that variable holds a plain number instead of an object (Ampfibian's weapon event),
// the call reads guest memory at number + 8 and the game dies. Treat such a reference as "no object", as the
// VM already does for a null one, and say so in the log.
namespace ben10::vm_guard {
inline bool BadObject(uint32_t value, uint32_t selector, uint32_t word) {
  if (value == 0 || (value >= 0x10000u && value < 0xE0000000u)) return false;
  static std::atomic<unsigned> reports{0};
  if (reports.fetch_add(1) < 20)
    REXLOG_INFO("Script VM: object reference {:08X} is not an object (selector {:08X}, opcode word {:08X}); treated as none", value, selector, word);
  return true;
}
}  // namespace ben10::vm_guard
