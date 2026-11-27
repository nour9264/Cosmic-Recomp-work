#pragma once

// sub_8219D398 looks a key up in one loaded package's hash map and returns 0 when it is not there; the caller
// (sub_821AD188) then tries the next package. Changing alien to Goop reaches a package whose map pointer (package +28)
// refers to memory that was released and reused: its header holds leftover data, the lookup computes an index far outside
// the game's memory and the process crashes. A map header that cannot be real counts as "not found", exactly as an empty
// package does, so the search continues with the next package (Goop's own).

#include <rex/logging.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <intrin.h>
#include <windows.h>

namespace ben10::lookup_guard {
inline std::atomic<int> reported{0};
// Diagnostic: for a few seconds after a form's weapon slots are built (a transformation), every package lookup is logged with the
// package that answered it, to show where a form's model, skeleton and animation data come from.
inline std::atomic<ULONGLONG> trace_until{0};
inline std::atomic<int> trace_lines{0};
inline thread_local uint32_t current_package = 0;
inline const bool trace_enabled = std::getenv("BEN10_RESOURCE_TRACE") != nullptr;
inline void OpenWindow(const uint8_t* base = nullptr) {
    if (!trace_enabled) return;
    trace_until.store(GetTickCount64() + 4000, std::memory_order_relaxed);
    // Temporary diagnostic: Chromastone's skin container keeps its directory at 0xBECB5C20 in every run so far; log it at each transformation.
    if (base) {
        uint32_t words[8];
        std::memcpy(words, base + 0xBECB5C20u, sizeof(words));
        REXLOG_INFO("Cosmic skin directory: {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}", _byteswap_ulong(words[0]),
                    _byteswap_ulong(words[1]), _byteswap_ulong(words[2]), _byteswap_ulong(words[3]), _byteswap_ulong(words[4]),
                    _byteswap_ulong(words[5]), _byteswap_ulong(words[6]), _byteswap_ulong(words[7]));
    }
}
inline void Package(uint32_t package) { if (trace_enabled) current_package = package; }
// Packages walked for the current (type, key) lookup, so the one line logged on success says how far the search went.
inline thread_local uint32_t walk_type = 0xffffffffu, walk_key = 0, walk_count = 0;
inline void Result(uint32_t type, uint32_t key, uint32_t found) {
    if (!trace_enabled) return;
    const uint32_t package = current_package;
    current_package = 0;
    if (type != walk_type || key != walk_key) walk_type = type, walk_key = key, walk_count = 0;
    ++walk_count;
    if (!found) return;
    const uint32_t walked = walk_count;
    walk_count = 0;
    // Colors, meshes, skeletons and skins found in the seconds after a transformation: one line each.
    if (GetTickCount64() > trace_until.load(std::memory_order_relaxed) || trace_lines.load(std::memory_order_relaxed) >= 400) return;
    if (type != 3 && type != 4 && type != 12 && type != 22) return;
    trace_lines.fetch_add(1, std::memory_order_relaxed);
    REXLOG_INFO("Cosmic lookup: type={} key={:08X} found in package {:08X} at {:08X} after {} packages", type, key, package, found, walked);
}

inline uint32_t Load(const uint8_t* base, uint32_t g) {
    uint32_t v;
    std::memcpy(&v, base + g, 4);
    return _byteswap_ulong(v);
}

// map: the guest address of the hash map header. Its first word is the number of buckets.
inline bool StaleMap(const uint8_t* base, uint32_t map, uint32_t key) {
    if (map < 0x10000 || map >= 0xe0000000u) return false;
    constexpr uint32_t kMaxBuckets = 0x1000000;
    const uint32_t buckets = Load(base, map);
    if (buckets <= kMaxBuckets) return false;
    if (reported.fetch_add(1, std::memory_order_relaxed) < 5)
        REXLOG_INFO("Cosmic lookup guard: key {:08X} skipped a released package map {:08X} (bucket count {:08X})", key, map, buckets);
    return true;
}
}  // namespace ben10::lookup_guard
