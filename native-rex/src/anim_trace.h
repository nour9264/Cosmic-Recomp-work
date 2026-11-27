#pragma once

// Diagnostic: logs every clip the game starts through sub_821335C8 (the generic "play this clip on this character"
// routine; the clip key is its second argument), with the character's position and a millisecond tick. Reading two
// consecutive far-attack lines shows which clips the attack plays (travel, attack, out) and how far and how fast the
// character moved between them. Capped, and silent in normal play once the cap is reached.

#include <rex/logging.h>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <intrin.h>
#include <windows.h>

namespace ben10::anim_trace {
inline std::atomic<int> lines{0};
constexpr int kCap = 8000;
// On with BEN10_ANIM_TRACE, or with an (empty) user/anim-trace.txt in the installation: the launcher removes every BEN10_*
// variable before it starts the game, so the file is the way to switch it on from the launcher.
inline bool Detect() {
    if (std::getenv("BEN10_ANIM_TRACE") != nullptr) return true;
    const char* root = std::getenv("BEN10_PORTABLE_ROOT");
    if (!root) return false;
    const std::string path = std::string(root) + "/user/anim-trace.txt";
    return GetFileAttributesA(path.c_str()) != INVALID_FILE_ATTRIBUTES;
}
inline const bool enabled = Detect();

inline uint32_t Load(const uint8_t* base, uint32_t guest) {
    uint32_t value;
    std::memcpy(&value, base + guest, 4);
    return _byteswap_ulong(value);
}
inline float LoadF(const uint8_t* base, uint32_t guest) {
    const uint32_t bits = Load(base, guest);
    float value;
    std::memcpy(&value, &bits, 4);
    return value;
}

inline void Play(const uint8_t* base, uint32_t caller, uint32_t character, uint32_t key, double blend) {
    if (!enabled) return;
    if (lines.load(std::memory_order_relaxed) >= kCap) return;
    if (character < 0x10000 || character >= 0xe0000000u) return;
    if (key < 0x10000) return;  // Small values are not clip keys (the routine is also called every frame with a flag).
    // The same clip started again on the same character within half a second is one event.
    static thread_local uint32_t last_character = 0, last_key = 0;
    static thread_local ULONGLONG last_tick = 0;
    const ULONGLONG now = GetTickCount64();
    if (character == last_character && key == last_key && now - last_tick < 500) return;
    last_character = character, last_key = key, last_tick = now;
    const uint32_t person = Load(base, character + 24);
    // The player's character only: its controller (character +456 owns the animation controller either way), so
    // log anything with a position and let the reader pick the player by form.
    REXLOG_INFO("Anim trace: t={} caller={:08X} char={:08X} person={:08X} key={:08X} blend={:.3f} pos=({:.2f} {:.2f} {:.2f})",
                GetTickCount64(), caller, character, person, key, blend, LoadF(base, character + 192),
                LoadF(base, character + 196), LoadF(base, character + 200));
    lines.fetch_add(1, std::memory_order_relaxed);
}

// sub_821DE370 is the animation controller's "start this clip" routine, called by the role-based sub_821335C8 and by the
// attack code with a clip key from the attack record. r10 is the character in the role-based call.
inline void Controller(uint32_t routine, const uint8_t* base, uint32_t caller, uint32_t r3, uint32_t r4, uint32_t r5, uint32_t r6, uint32_t r7,
                       uint32_t r8, uint32_t r9, uint32_t r10) {
    if (!enabled) return;
    if (lines.load(std::memory_order_relaxed) >= kCap) return;
    // Each (controller, clip/role) pair is logged at most once per 600 ms: the idle and run roles are re-issued every frame.
    struct Seen { uint32_t controller = 0, key = 0; ULONGLONG tick = 0; };
    static thread_local Seen seen[128];
    const ULONGLONG now = GetTickCount64();
    Seen& slot = seen[(r3 * 31u + r4 + routine) % 128u];
    if (slot.controller == r3 && slot.key == r4 && now - slot.tick < 600) return;
    slot.controller = r3, slot.key = r4, slot.tick = now;
    float x = 0, y = 0, z = 0;
    if (r10 >= 0x10000 && r10 < 0xe0000000u) x = LoadF(base, r10 + 192), y = LoadF(base, r10 + 196), z = LoadF(base, r10 + 200);
    REXLOG_INFO("Anim controller: t={} fn={:X} caller={:08X} ctrl={:08X} a4={:08X} a5={:08X} a6={:08X} a7={:08X} a8={:08X} a9={:08X} a10={:08X} pos=({:.2f} {:.2f} {:.2f})",
                now, routine & 0xFFF, caller, r3, r4, r5, r6, r7, r8, r9, r10, x, y, z);
    lines.fetch_add(1, std::memory_order_relaxed);
}
}  // namespace ben10::anim_trace
