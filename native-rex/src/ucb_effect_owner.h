#pragma once

// UCB's private attack signals belong to the live, attached weapon tree.
// Do not broadcast them through the scene's script dispatcher or deliver
// them to another instance of a node template elsewhere in the level.
#include "weapon_trace.h"
#include <atomic>
#include <cstring>

namespace ben10::ucb_effect_owner {
inline constexpr uint32_t kRoot = 0x1b34d861u;
inline thread_local uint32_t owner = 0;
inline thread_local uint32_t owner_person = 0;
inline std::atomic<unsigned> reports{0};

inline constexpr bool Private(uint32_t e) {
    switch (e) {
        case 0x059c8510u: case 0x0ab16e70u: case 0x261f503cu:
        case 0x3383f0c4u: case 0x4f343cc3u: case 0x4f7af340u:
        case 0x5722ce4bu: case 0x5c9baff6u: case 0x73ba4a55u:
        case 0x855115a2u: case 0x86ecee30u: case 0x8d0a69dfu:
        case 0x9429ad53u: case 0x9c95d4aau: case 0xb7c01e48u:
        case 0xda570eb9u: case 0xeb92e43cu: case 0xfab88642u:
        case 0xff0a1d9du: return true;
        default: return false;
    }
}

// Probe by reading, not by VirtualQuery: every VirtualQuery takes the process
// address-space lock, and a burst of them per node per event starved the render
// thread's VirtualProtect for tens of milliseconds (frame hitches on UCB attacks).
inline bool ProbeRead(const uint8_t* address, size_t bytes) {
    __try {
        const volatile uint8_t* p = address;
        for (size_t off = 0; off < bytes; off += 4096) (void)p[off];
        (void)p[bytes - 1];
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

inline bool Valid(const uint8_t* base, uint32_t p, size_t bytes) {
    return p >= 0x10000u && p < 0xe0000000u && !(p & 3u) && bytes &&
           ProbeRead(base + p, bytes);
}
inline uint32_t Word(const uint8_t* base, uint32_t p) {
    uint32_t v;
    std::memcpy(&v, base + p, 4);
    return _byteswap_ulong(v);
}

// Called only at event dispatch. Offset 168 is the native node's parent,
// not a global hash lookup; matching a name alone does not establish ownership.
inline bool Belongs(const uint8_t* base, uint32_t node, uint32_t root) {
    if (!root) return false;
    for (unsigned depth = 0; depth < 12 && Valid(base, node, 180); ++depth) {
        if (node == root) return Word(base, node + 8) == kRoot;
        node = Word(base, node + 168);
    }
    return false;
}

inline bool Active(const uint8_t* base) {
    return owner && Valid(base, owner_person, 796) &&
           Word(base, owner_person + 792) == owner && Valid(base, owner, 180) &&
           Word(base, owner + 8) == kRoot;
}

inline bool Reject(const uint8_t* base, uint32_t node, uint32_t e,
                   uint32_t caller, uint32_t person) {
    if (!Private(e)) return false;
    // 82148EA8 is the actual character attack-start dispatch. Its r29
    // is the person, and person+792 is the fifth attached weapon slot.
    if (caller == 0x82148ea8u && Valid(base, person, 796) &&
        Valid(base, node, 180) && Word(base, person + 792) == node &&
        Word(base, node + 8) == kRoot) {
        owner = node;
        owner_person = person;
    }
    if (!Active(base)) return false;
    const bool allowed = Belongs(base, node, owner);
    // Local relays can dispatch dozens of events in one simulation tick.
    // Keep the ownership guard unchanged but avoid synchronous log writes
    // for successful dispatches (especially the suction release burst).
    if (!allowed && reports.fetch_add(1, std::memory_order_relaxed) < 12) {
        const uint32_t key = Valid(base, node, 180) ? Word(base, node + 8) : 0;
        REXLOG_INFO("UCB private VFX {}: event={:08X} node={:08X} key={:08X} owner={:08X} caller={:08X}",
                    allowed ? "local" : "rejected", e, node, key, owner, caller);
    }
    return !allowed;
}

inline bool Local(const uint8_t* base, uint32_t node, uint32_t e) {
    return Private(e) && Active(base) && Belongs(base, node, owner);
}
}
