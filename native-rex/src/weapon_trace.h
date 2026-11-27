#pragma once

// Diagnostic trace for character weapons (person:setweapon) and script
// errors. Written to runtime.log; each kind is capped so a long session
// does not flood the log. Used to check imported aliens' hit volumes and
// effect roots, which attach through the same weapon slots.

#include "lookup_guard.h"
#include "ucb_screen_flash_state.h"
#include <rex/logging.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <windows.h>

namespace ben10::weapon_trace {
inline std::atomic<int> weapon_lines{0}, bone_lines{0}, error_lines{0};
inline std::mutex instances_lock;
inline std::unordered_map<uint32_t, uint32_t> instances;  // weapon instance -> slot
inline std::atomic<bool> any_instance{false};

inline bool Readable(const uint8_t* address, size_t size) {
    MEMORY_BASIC_INFORMATION info{};
    return VirtualQuery(address, &info, sizeof(info)) && info.State == MEM_COMMIT &&
           !(info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
           address + size <= static_cast<const uint8_t*>(info.BaseAddress) + info.RegionSize;
}

inline uint8_t Byte(const uint8_t* base, uint32_t guest) {
    if (!guest || guest >= 0xe0000000u || !Readable(base + guest, 1)) return 0;
    return base[guest];
}

// sub_821417F8(person, slot, weapon hash): the node lookup result.
inline void Lookup(uint32_t person, uint32_t slot, uint32_t weapon, uint32_t handle,
                   const uint8_t* base) {
    if (slot == 0) ben10::lookup_guard::OpenWindow(base);
    if (weapon_lines.fetch_add(1) < 400)
        REXLOG_INFO("Weapon trace: person={:08X} slot={} weapon={:08X} handle={:08X} flags={:02X}",
                    person, slot, weapon, handle, handle ? Byte(base, handle + 6) : 0);
}

// The instance created from that node and attached to the slot.
inline void Instance(uint32_t person, uint32_t slot, uint32_t instance) {
    if (instance) {
        std::lock_guard lock(instances_lock);
        instances[instance] = slot;
        any_instance.store(true, std::memory_order_relaxed);
    }
    if (weapon_lines.fetch_add(1) < 400)
        REXLOG_INFO("Weapon trace: person={:08X} slot={} instance={:08X}", person, slot, instance);
}

// sub_82132F40(person, bone id) inside the weapon attach: 0 = bone missing.
inline void Bone(uint32_t person, uint32_t slot, uint32_t bone) {
    if (bone_lines.fetch_add(1) < 200)
        REXLOG_INFO("Weapon trace: person={:08X} slot={} bone={:08X}", person, slot, bone);
}

// sub_82238A28(format, ...): the game's script/debug error print.
inline void ScriptError(uint32_t format, const uint8_t* base) {
    if (!format || format >= 0xe0000000u || error_lines.fetch_add(1) >= 300) return;
    std::string text;
    for (uint32_t i = 0; i < 240; ++i) {
        if (!Readable(base + format + i, 1)) break;
        char c = static_cast<char>(base[format + i]);
        if (!c) break;
        text += (c == '\n' || c == '\r') ? ' ' : c;
    }
    REXLOG_INFO("Game error print: {}", text);
}

// sub_821E2680(node, event, recurse): events delivered to weapon instances.
inline void Event(uint32_t node, uint32_t event, uint32_t recurse, uint32_t caller) {
    // All ordinary node events previously took the diagnostic mutex. Only
    // the suction release depends on the instance lookup during gameplay.
    if (!ben10::lookup_guard::trace_enabled && event != 0x8d0a69dfu) return;
    if (!any_instance.load(std::memory_order_relaxed)) return;
    static std::unordered_set<uint64_t> seen;
    // Attack events from the Four Arms / Chromastone attack tables.
    static const std::unordered_set<uint32_t> attack_events{
        0x8d0fbaab, 0xfff06adf, 0x47c4f3ff, 0x0f36cd29, 0x232a7457, 0x8cf4d407, 0x2ed690aa,
        0x1d7a178d, 0x9afeed8f, 0x3eb90571, 0x7ee4e8e7, 0x2a7366fd, 0xfcee430c, 0x316e5fd5,
        0x8be9739a, 0x46696f43, 0x65e712b6, 0xa8670e6f, 0xc73d9f7e, 0x3f8a6eb8};
    uint32_t slot = 9;
    {
        std::lock_guard lock(instances_lock);
        auto found = instances.find(node);
        if (found == instances.end() && !attack_events.count(event)) return;
        if (found != instances.end()) slot = found->second;
        if (slot == 4 && event == 0x8d0a69dfu) ben10::ucb_screen_flash::Release();
        if (!ben10::lookup_guard::trace_enabled) return;
        if (seen.size() >= 600 ||
            !seen.insert((uint64_t(node) << 32) ^ (uint64_t(event) << 8) ^ caller).second) return;
    }
    REXLOG_INFO("Weapon event: instance={:08X} slot={} event={:08X} recurse={} caller={:08X}",
                node, slot, event, recurse, caller);
}

// sub_8221AD00(sound descriptor): the entry sounds.ddf builds for a sound
// name; logs its words once so an imported sound can be compared with a
// working one.
inline void Descriptor(uint32_t descriptor, const uint8_t* base) {
    if (!ben10::lookup_guard::trace_enabled) return;
    static std::mutex lock;
    static std::unordered_set<uint32_t> seen;
    if (!descriptor || descriptor >= 0xe0000000u || !Readable(base + descriptor, 64)) return;
    {
        std::lock_guard guard(lock);
        if (seen.size() >= 400 || !seen.insert(descriptor).second) return;
    }
    uint32_t words[16];
    for (int i = 0; i < 16; ++i) {
        uint32_t value;
        std::memcpy(&value, base + descriptor + i * 4, 4);
        words[i] = _byteswap_ulong(value);
    }
    REXLOG_INFO("Sound descriptor {:08X}: {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X} {:08X}",
                descriptor, words[0], words[1], words[2], words[3], words[4], words[5], words[6], words[7],
                words[8], words[9], words[10], words[11]);
}
}
