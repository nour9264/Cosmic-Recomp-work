#pragma once
// Temporary diagnostic: what a laser beam's ray reports (sub_82109D70).
#include <rex/logging.h>
#include <atomic>
#include <cstdint>
namespace ben10::beam_trace {
inline std::atomic<int> lines{0};
inline void Note(const char* what, uint32_t a, uint32_t b, uint32_t c) {
    if (lines.fetch_add(1) < 120) REXLOG_INFO("Beam trace: {} {:08X} {:08X} {:08X}", what, a, b, c);
}
}
