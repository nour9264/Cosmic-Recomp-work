#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>

namespace ben10::ucb_screen_flash {
inline std::atomic<int64_t> started_ns{0};
inline int64_t Now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
inline void Release() {
    const auto now=Now();
    auto last=started_ns.load(std::memory_order_relaxed);
    // A native release may be forwarded to multiple children. Do not restart the fade.
    if (now-last>1200000000LL) started_ns.compare_exchange_strong(last,now,std::memory_order_relaxed);
}
inline float Alpha() {
    const auto start=started_ns.load(std::memory_order_relaxed);
    if (!start) return 0;
    const float t=float(Now()-start)*1.e-9f;
    if (t<0 || t>=1.12f) return 0;
    if(t<.06f) return .93f*t/.06f;
    if(t<.42f) return .93f;
    const float x=(t-.42f)/.70f;
    return .93f*(1-x*x*(3-2*x));
}
}
