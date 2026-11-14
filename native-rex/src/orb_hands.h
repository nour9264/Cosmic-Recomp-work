#pragma once

// Chromastone's Energy Outburst orbs follow his hands. The orb emitters hang
// under the fifth weapon slot's tree (specials root 36212CE1), which follows the
// character's own transform, not a bone. Every frame the generated hook in
// sub_82148DF0 finds the two emitter nodes and writes the hand bones' matrices
// (slots 0 and 1 use bones 97 and 98) into their local transforms, expressed
// relative to the character.

#include <rex/logging.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <intrin.h>

namespace ben10::orb_hands {
constexpr uint32_t kSpecials = 0x36212CE1, kOrb[2] = {0x109C9B71, 0x679BABE7};

inline bool Ok(uint32_t g) { return g >= 0x10000 && g < 0xe0000000u && !(g & 3); }
inline uint32_t Load(const uint8_t* base, uint32_t g) {
    uint32_t v;
    std::memcpy(&v, base + g, 4);
    return _byteswap_ulong(v);
}
inline float LoadF(const uint8_t* base, uint32_t g) {
    const uint32_t v = Load(base, g);
    float f;
    std::memcpy(&f, &v, 4);
    return f;
}
inline void StoreF(uint8_t* base, uint32_t g, float f) {
    uint32_t v;
    std::memcpy(&v, &f, 4);
    v = _byteswap_ulong(v);
    std::memcpy(base + g, &v, 4);
}

// Looks for the orb emitter nodes below the character's fifth weapon node.
inline void Search(const uint8_t* base, uint32_t node, int depth, uint32_t (&found)[2], int& budget) {
    if (!Ok(node) || depth > 6 || --budget < 0) return;
    const uint32_t key = Load(base, node + 8);
    for (int i = 0; i < 2; ++i)
        if (key == kOrb[i]) found[i] = node;
    Search(base, Load(base, node + 176), depth + 1, found, budget);
    Search(base, Load(base, node + 172), depth + 1, found, budget);
}

// Nodes for a character. Searched afresh on every call: the nodes are created and
// freed with each use, and a remembered pointer would write into freed memory.
inline bool Find(uint32_t character, const uint8_t* base, uint32_t (&found)[2]) {
    if (!Ok(character)) return false;
    const uint32_t weapon = Load(base, character + 776 + 16);
    if (!Ok(weapon) || Load(base, weapon + 8) != kSpecials) return false;
    found[0] = found[1] = 0;
    int budget = 200;
    Search(base, weapon, 0, found, budget);
    return found[0] && found[1];
}

// Goop's Acid Hose emitter hangs under his specials root (F9DFC8A3); it is moved to the
// hand bone each frame so the smoke starts at the end of his arm.
constexpr uint32_t kGoopSpecials = 0xF9DFC8A3, kHosePuffs = 0x668b7b0a;
inline bool FindGoop(uint32_t character, const uint8_t* base, uint32_t& node) {
    if (!Ok(character)) return false;
    const uint32_t weapon = Load(base, character + 776 + 16);
    if (!Ok(weapon) || Load(base, weapon + 8) != kGoopSpecials) return false;
    uint32_t found[2] = {0, 0};
    int budget = 5000;  // The sibling links wander through the whole scene graph before the children are reached.
    const uint32_t save = kOrb[0];
    (void)save;
    // Same search, other key.
    struct Local {
        static void Go(const uint8_t* base, uint32_t node, int depth, uint32_t& out, int& budget) {
            if (!Ok(node) || depth > 12 || --budget < 0) return;
            if (Load(base, node + 8) == kHosePuffs) out = node;
            Go(base, Load(base, node + 176), depth + 1, out, budget);
            Go(base, Load(base, node + 172), depth + 1, out, budget);
        }
    };
    uint32_t out = 0;
    Local::Go(base, weapon, 0, out, budget);
    node = out;
    (void)found;
    return out != 0;
}

// out = hand * inverse(person), both rigid 4x4 row-vector matrices of 16 floats.
inline void Relative(const uint8_t* base, uint32_t hand, uint32_t person, float (&out)[16]) {
    float h[16], p[16];
    for (int i = 0; i < 16; ++i) {
        h[i] = LoadF(base, hand + 4 * i);
        p[i] = LoadF(base, person + 4 * i);
    }
    float inverse[16] = {};
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c) inverse[4 * r + c] = p[4 * c + r];
    for (int c = 0; c < 3; ++c)
        inverse[12 + c] = -(p[12] * inverse[c] + p[13] * inverse[4 + c] + p[14] * inverse[8 + c]);
    inverse[15] = 1.0f;
    for (int r = 0; r < 4; ++r)
        for (int c = 0; c < 4; ++c) {
            float sum = 0;
            for (int k = 0; k < 4; ++k) sum += h[4 * r + k] * inverse[4 * k + c];
            out[4 * r + c] = sum;
        }
}

// A matrix the effect nodes can take: finite, a rotation part of about unit size and a nearby translation. While a form is
// still being made the character's transform can be zero or garbage, and writing that makes the nodes cover the screen.
inline bool Sane(const float (&m)[16]) {
    for (int i = 0; i < 16; ++i)
        if (!(m[i] == m[i]) || m[i] > 1.0e4f || m[i] < -1.0e4f) return false;
    for (int r = 0; r < 3; ++r)
        for (int c = 0; c < 3; ++c)
            if (m[4 * r + c] > 1.5f || m[4 * r + c] < -1.5f) return false;
    return m[12] < 50.0f && m[12] > -50.0f && m[13] < 50.0f && m[13] > -50.0f && m[14] < 50.0f && m[14] > -50.0f;
}

inline std::atomic<int> lines{0};
inline void Log(uint32_t slot, const float (&m)[16], const uint8_t* base, uint32_t person) {
    if (lines.fetch_add(1) < 40)
        REXLOG_INFO("Orb hands: bone {} relative pos ({:.2f} {:.2f} {:.2f}) person pos ({:.2f} {:.2f} {:.2f})", slot, m[12],
                    m[13], m[14], LoadF(base, person + 48), LoadF(base, person + 52), LoadF(base, person + 56));
}
}
