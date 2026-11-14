#pragma once

// Switches the language of the game's own text (menus, level names, dialogue strings) while it runs.
//
// The game loads its text table once, as heap strings referenced by hash-map nodes that hold
// `key, pointer` pairs. This builds the table of the chosen language (the game's own French, German,
// Spanish and Italian tables, or the English one with a few translated lines for Portuguese and Turkish),
// writes the differing strings into guest memory and repoints every node whose string is still the
// previously loaded one. The next time a menu reads its text, it gets the new language.
#include <windows.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "language_setting.h"

namespace ben10::text_swap {
using Table = std::map<uint32_t, std::string>;  // key -> text bytes without the terminator

inline Table Parse(const std::filesystem::path& file) {
    Table table;
    std::ifstream stream(file, std::ios::binary);
    const std::string data((std::istreambuf_iterator<char>(stream)), {});
    auto be = [&](size_t at) {
        return uint32_t(uint8_t(data[at])) << 24 | uint32_t(uint8_t(data[at + 1])) << 16 |
               uint32_t(uint8_t(data[at + 2])) << 8 | uint8_t(data[at + 3]);
    };
    if (data.size() < 4 || be(0) != 0x1badbabe) return table;
    for (size_t at = 4; at + 8 <= data.size();) {
        const uint32_t key = be(at), length = be(at + 4);
        at += 8;
        if (length == 0 || length > data.size() - at) return {};
        table[key] = std::string(data.data() + at, length - 1);
        at += length;
    }
    return table;
}

// English lines translated for languages the game has no table for (as in GameMenuPatch.cs).
inline const std::map<std::string, std::string>& Partial(int language) {
    static const std::map<std::string, std::string> pt = {
        {"CONTINUE", "CONTINUAR"}, {"Continue", "Continuar"}, {"LEVEL SELECT", "SELE\xc7\xc3O DE FASE"},
        {"OPTIONS", "OP\xc7\xd5" "ES"}, {"Options", "Op\xe7\xf5" "es"}, {"CHEATS", "TRAPA\xc7" "AS"},
        {"BONUS MATERIAL", "MATERIAL B\xd4NUS"}, {"The Catacombs", "As Catacumbas"}, {"Eiffel Tower", "Torre Eiffel"},
        {"Devil's Tower", "Torre do Diabo"}, {"The Great Wall", "A Grande Muralha"}, {"Tokyo Nights", "Noites de T\xf3quio"},
        {"The Amazon", "A Amaz\xf4nia"}, {"The Colosseum", "O Coliseu"}, {"The Final Battle", "A Batalha Final"},
        {"Total DNA: %d", "DNA total: %d"}, {"Pickups %d/%d", "Itens %d/%d"}};
    static const std::map<std::string, std::string> tr = {
        {"CONTINUE", "DEVAM ET"}, {"Continue", "Devam Et"}, {"LEVEL SELECT", "BOLUM SECIMI"},
        {"OPTIONS", "SECENEKLER"}, {"Options", "Secenekler"}, {"CHEATS", "HILELER"}, {"BONUS MATERIAL", "BONUS ICERIK"},
        {"The Catacombs", "Yeralti Mezarlari"}, {"Eiffel Tower", "Eyfel Kulesi"}, {"Devil's Tower", "Seytan Kulesi"},
        {"The Great Wall", "Buyuk Sur"}, {"Tokyo Nights", "Tokyo Geceleri"}, {"The Amazon", "Amazon"},
        {"The Colosseum", "Kolezyum"}, {"The Final Battle", "Son Savas"},
        {"Total DNA: %d", "Toplam DNA: %d"}, {"Pickups %d/%d", "Toplananlar %d/%d"}};
    static const std::map<std::string, std::string> none;
    return language == 6 ? pt : language == 7 ? tr : none;
}

inline Table& Current() {
    static Table current;
    return current;
}

template <typename Host>
inline void Apply(Host* host, int language) {
    namespace fs = std::filesystem;
    static std::mutex one_at_a_time;
    std::lock_guard<std::mutex> only(one_at_a_time);
    const fs::path scripts = host->user_data_root().parent_path() / "game" / "global" / "scripts";
    static const char* official[] = {nullptr, nullptr, "xbx_ge.txt", "xbx_fr.txt", "xbx_sp.txt", "xbx_it.txt"};
    Table english = Parse(scripts / "xbx_us.txt.cosmic-original");
    if (english.empty()) english = Parse(scripts / "xbx_us.txt");
    if (english.empty()) return;
    Table& current = Current();
    if (current.empty()) current = Parse(scripts / "xbx_us.txt");  // What was loaded at start.
    if (current.empty()) return;

    Table target = english;
    if (language >= 2 && language <= 5) {
        const Table translated = Parse(scripts / official[language]);
        if (translated.empty()) return;
        for (auto& [key, text] : target) {
            const auto found = translated.find(key);
            if (found != translated.end()) text = found->second;
        }
    } else if (language == 6 || language == 7) {
        for (auto& [key, text] : target) {
            const auto found = Partial(language).find(text);
            if (found != Partial(language).end()) text = found->second;
        }
    }

    struct Change { std::string old_text; uint32_t fresh; };
    std::unordered_map<uint32_t, Change> changes;
    auto* memory = host->memory();
    uint8_t* base = memory->virtual_membase();
    for (const auto& [key, text] : target) {
        const auto old = current.find(key);
        if (old == current.end() || old->second == text) continue;
        const uint32_t address = memory->SystemHeapAlloc(uint32_t(text.size() + 1));
        if (!address) return;
        std::memcpy(base + address, text.c_str(), text.size() + 1);
        changes[key] = {old->second, address};
    }
    if (changes.empty()) return;

    std::vector<bool> filter(1 << 16, false);
    for (const auto& entry : changes) filter[entry.first & 0xffff] = true;
    auto readable = [&](uint64_t address, size_t length) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(base + address, &info, sizeof(info))) return false;
        return info.State == MEM_COMMIT && !(info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
               (reinterpret_cast<uintptr_t>(base + address) + length <=
                reinterpret_cast<uintptr_t>(info.BaseAddress) + info.RegionSize);
    };
    int patched = 0;
    for (uint64_t address = 0x10000; address < 0x100000000ull;) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(base + address, &info, sizeof(info))) break;
        const uint64_t size = info.RegionSize;
        const bool open = info.State == MEM_COMMIT && info.Protect == PAGE_READWRITE;
        if (open) {
            uint8_t* start = base + address;
            for (uint64_t at = 0; at + 8 <= size; at += 4) {
                const uint32_t raw = *reinterpret_cast<const uint32_t*>(start + at);
                const uint32_t key = _byteswap_ulong(raw);
                if (!filter[key & 0xffff]) continue;
                const auto found = changes.find(key);
                if (found == changes.end()) continue;
                const uint32_t pointer = _byteswap_ulong(*reinterpret_cast<const uint32_t*>(start + at + 4));
                const std::string& old_text = found->second.old_text;
                if (pointer < 0x10000 || !readable(pointer, old_text.size() + 1)) continue;
                if (std::memcmp(base + pointer, old_text.c_str(), old_text.size() + 1) != 0) continue;
                *reinterpret_cast<uint32_t*>(start + at + 4) = _byteswap_ulong(found->second.fresh);
                ++patched;
            }
        }
        address += size ? size : 0x1000;
    }
    // Menus already on screen draw from their own inline copy of the text: a text object keeps its string at
    // +124 (256 bytes), its vtable at +0 and a small argument count at +380. Rewrite those copies in place.
    std::unordered_map<uint32_t, std::vector<const std::pair<const uint32_t, Change>*>> by_head;
    std::vector<std::string> fresh_text;
    for (const auto& entry : changes) {
        const std::string& old_text = entry.second.old_text;
        if (old_text.size() < 4) continue;
        uint32_t head = uint32_t(uint8_t(old_text[0])) << 24 | uint32_t(uint8_t(old_text[1])) << 16 |
                        uint32_t(uint8_t(old_text[2])) << 8 | uint8_t(old_text[3]);
        by_head[head].push_back(&entry);
    }
    std::vector<bool> head_filter(1 << 16, false);
    for (const auto& entry : by_head) head_filter[entry.first & 0xffff] = true;
    int objects = 0;
    for (uint64_t address = 0x10000; address < 0xC0000000ull;) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(base + address, &info, sizeof(info))) break;
        const uint64_t size = info.RegionSize;
        if (info.State == MEM_COMMIT && info.Protect == PAGE_READWRITE && address >= 0x1000) {
            uint8_t* start = base + address;
            for (uint64_t at = 124; at + 264 <= size; at += 4) {
                const uint32_t head = _byteswap_ulong(*reinterpret_cast<const uint32_t*>(start + at));
                if (!head_filter[head & 0xffff]) continue;
                const auto found = by_head.find(head);
                if (found == by_head.end()) continue;
                const uint32_t vtable = _byteswap_ulong(*reinterpret_cast<const uint32_t*>(start + at - 124));
                const uint32_t count = _byteswap_ulong(*reinterpret_cast<const uint32_t*>(start + at + 256));
                if (vtable != 0x820193C8 || count > 4) continue;
                for (const auto* entry : found->second) {
                    const std::string& old_text = entry->second.old_text;
                    if (std::memcmp(start + at, old_text.c_str(), old_text.size() + 1) != 0) continue;
                    const std::string& text = target[entry->first];
                    if (text.size() >= 255) continue;
                    std::memset(start + at, 0, std::max(old_text.size(), text.size()) + 1);
                    std::memcpy(start + at, text.c_str(), text.size());
                    ++objects;
                    break;
                }
            }
        }
        address += size ? size : 0x1000;
    }
    for (const auto& entry : changes) current[entry.first] = target[entry.first];
    REXLOG_INFO("Cosmic text: language {} -> {} strings changed, {} table references and {} on-screen text copies rewritten", language,
                changes.size(), patched, objects);
}
}  // namespace ben10::text_swap
