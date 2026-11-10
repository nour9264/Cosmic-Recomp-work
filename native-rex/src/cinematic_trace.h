#pragma once

#include <cstdint>
#include <cstdio>
#include <cstdlib>

namespace ben10::cinematic_trace {
inline bool Enabled() {
    static const bool enabled = std::getenv("REX_BEN10_CINEMATIC_TRACE") != nullptr;
    return enabled;
}

inline void Open(uint32_t caller, uint32_t movie) {
    if (Enabled()) {
        std::fprintf(stderr, "[cinematic] open caller=%08x object=%08x\n", caller, movie);
        std::fflush(stderr);
    }
}

inline void State(const char* event, uint32_t target, uint32_t value,
                  uint32_t& previous_target, uint32_t& previous_value) {
    if (!Enabled() || (target == previous_target && value == previous_value))
        return;
    previous_target = target;
    previous_value = value;
    std::fprintf(stderr, "[cinematic] %s target=%08x value=%08x\n", event, target, value);
    std::fflush(stderr);
}

inline void Closing(uint32_t target) {
    if (Enabled()) {
        std::fprintf(stderr, "[cinematic] story close target=%08x\n", target);
        std::fflush(stderr);
    }
}
}
