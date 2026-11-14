#pragma once

// Chromastone's special-attack effects hang under the fifth weapon slot, whose
// matrix is copied from the character every frame (sub_8213A9A0), so the gatling
// crystals turned and moved with him as he steered. From the gatling attack's start
// event (sub_82148DF0 sending 9AFEED8F to the slot) until any other attack's start
// that copy is skipped for Chromastone's specials root (20 frames after the start,
// so the effects take the heading he turns to first), leaving them where they were.

#include <rex/logging.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <intrin.h>

namespace ben10::slot_freeze {
constexpr uint32_t kSpecials = 0x36212CE1, kHeadStart = 0x1000, kGatlingStart = 0x9AFEED8F;
inline std::atomic<bool> frozen{false};
inline std::atomic<int> goop_attack_frames{0};  // Temporary: frames left to log Goop's bones.
inline std::atomic<int> delay{0};  // Frames left before the freeze takes hold.
constexpr int kFreezeAfterFrames = 20;
inline std::atomic<int> hide_in{0};  // Frames until the frozen effects are sent out of the world.
constexpr int kHideAfterStopFrames = 120;

inline uint32_t Load(const uint8_t* base, uint32_t g) {
    uint32_t v;
    std::memcpy(&v, base + g, 4);
    return _byteswap_ulong(v);
}
inline bool Ok(uint32_t g) { return g >= 0x10000 && g < 0xe0000000u; }

// sub_82148DF0: the head slot's (4) turn to get an attack's start or stop event.
inline bool Event(uint32_t character, uint32_t slot_address, uint32_t mask, bool start, const uint8_t* base) {
    if (!Ok(character) || !Ok(slot_address) || (slot_address - character - 776) / 4 != 4) return false;
    const uint32_t node = Load(base, slot_address);
    if (Ok(node) && start && (mask & kHeadStart) && Load(base, node + 8) == 0xF9DFC8A3u) goop_attack_frames.store(150);
    if (!Ok(node) || Load(base, node + 8) != kSpecials) return false;
    if (!start) {
        // The attack's end: crystals still in flight are cleared shortly after, so
        // they cannot reappear at the heading of the next attack.
        if ((mask & 0x200) && frozen.load(std::memory_order_relaxed)) hide_in.store(kHideAfterStopFrames, std::memory_order_relaxed);
        return false;
    }
    if (!(mask & kHeadStart)) return false;
    hide_in.store(0, std::memory_order_relaxed);
    const uint32_t state = Load(base, character + 1972);
    if (!Ok(state)) return false;
    const uint32_t record = Load(base, state + 20);
    if (!Ok(record)) return false;
    const bool gatling = Load(base, record + 120) == kGatlingStart;
    frozen.store(false, std::memory_order_relaxed);
    delay.store(gatling ? kFreezeAfterFrames : 0, std::memory_order_relaxed);
    return gatling;  // The caller clears the previous volley's crystals first.
}

// sub_8213A9A0: true when the matrix copy for this slot-4 node must be skipped.
inline float F(const uint8_t* base, uint32_t g) { uint32_t v = Load(base, g); float f; std::memcpy(&f, &v, 4); return f; }
inline std::atomic<int> goop_lines{0}, goop_frames{0};
// Temporary diagnostic: Goop's effects stayed where the form was made.
inline uint32_t FindKey(const uint8_t* base, uint32_t node, uint32_t key, int depth, int& budget) {
    if (!Ok(node) || depth > 12 || --budget < 0) return 0;
    if (Load(base, node + 8) == key) return node;
    if (uint32_t found = FindKey(base, Load(base, node + 176), key, depth + 1, budget)) return found;
    return FindKey(base, Load(base, node + 172), key, depth + 1, budget);
}
inline void Probe(uint32_t node, uint32_t character, const uint8_t* base) {
    if (!Ok(node) || !Ok(character) || Load(base, node + 8) != 0xF9DFC8A3u) return;
    if (goop_frames.fetch_add(1) % 30 || goop_lines.fetch_add(1) > 60) return;
    REXLOG_INFO("Goop probe: node={:08X} node pos ({:.2f} {:.2f} {:.2f}) world ({:.2f} {:.2f} {:.2f}) person ({:.2f} {:.2f} {:.2f}) flags={:08X}",
                node, F(base, node + 64), F(base, node + 68), F(base, node + 72), F(base, node + 128), F(base, node + 132),
                F(base, node + 136), F(base, character + 192), F(base, character + 196), F(base, character + 200), Load(base, node + 160));
    int budget = 200;
    for (uint32_t key : {0x93997AF2u, 0xD313E756u}) {
        const uint32_t child = FindKey(base, node, key, 0, budget);
        if (child)
            REXLOG_INFO("Goop probe: child {:08X} at {:08X} local ({:.2f} {:.2f} {:.2f}) world ({:.2f} {:.2f} {:.2f}) flags={:08X} parent={:08X}", key,
                        child, F(base, child + 64), F(base, child + 68), F(base, child + 72), F(base, child + 128), F(base, child + 132),
                        F(base, child + 136), Load(base, child + 160), Load(base, child + 12));
    }
}

// Goop's effect nodes never had their world matrix (node +80) refreshed after the form
// was made: only the specials root's was, so his puddle stayed where he transformed.
// World = local (+16) x parent's world, row-vector matrices of 16 floats.
inline void WorldFromParent(uint8_t* base, uint32_t node, uint32_t parent) {
    float l[16], p[16], w[16];
    for (int i = 0; i < 16; ++i) {
        l[i] = F(base, node + 16 + 4 * i);
        p[i] = F(base, parent + 80 + 4 * i);
    }
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c) {
            float sum = 0;
            for (int k = 0; k < 4; ++k) sum += l[4 * r + k] * p[4 * k + c];
            w[4 * r + c] = sum;
        }
    for (int i = 0; i < 16; ++i) {
        uint32_t bits;
        std::memcpy(&bits, &w[i], 4);
        bits = _byteswap_ulong(bits);
        std::memcpy(base + node + 80 + 4 * i, &bits, 4);
    }
}

inline void RefreshGoop(uint8_t* base, uint32_t root) {
    if (!Ok(root) || Load(base, root + 8) != 0xF9DFC8A3u) return;
    int budget = 0;
    budget = 5000;
    if (const uint32_t hose = FindKey(base, root, 0x9F8CCF10u, 0, budget)) {
        WorldFromParent(base, hose, root);
        budget = 5000;
        if (const uint32_t puffs = FindKey(base, hose, 0x668b7b0a, 0, budget)) WorldFromParent(base, puffs, hose);
    }
    budget = 200;
    const uint32_t tree = FindKey(base, root, 0x93997AF2u, 0, budget);
    if (!tree) return;
    WorldFromParent(base, tree, root);
    budget = 200;
    const uint32_t mesh = FindKey(base, tree, 0xD313E756u, 0, budget);
    if (!mesh) return;
    WorldFromParent(base, mesh, tree);
    for (uint32_t key : {0x0C177059u, 0x951E21E3u}) {
        budget = 200;
        if (const uint32_t child = FindKey(base, mesh, key, 0, budget)) WorldFromParent(base, child, mesh);
    }
}

inline bool Skip(uint32_t node, uint8_t* base) {
    if (!Ok(node) || Load(base, node + 8) != kSpecials) return false;
    if (!frozen.load(std::memory_order_relaxed) && delay.load(std::memory_order_relaxed) > 0 &&
        delay.fetch_sub(1, std::memory_order_relaxed) == 1)
        frozen.store(true, std::memory_order_relaxed);
    if (frozen.load(std::memory_order_relaxed) && hide_in.load(std::memory_order_relaxed) > 0 &&
        hide_in.fetch_sub(1, std::memory_order_relaxed) == 1) {
        const float below = -1000.0f;  // Translation row: x, y, z at +48, +52, +56 of the matrix at +16.
        uint32_t bits;
        std::memcpy(&bits, &below, 4);
        bits = _byteswap_ulong(bits);
        std::memcpy(base + node + 16 + 52, &bits, 4);
    }
    return frozen.load(std::memory_order_relaxed);
}
}
