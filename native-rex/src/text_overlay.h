#pragma once

// Russian, Japanese and Arabic text for the original game menus.
//
// The game draws each menu text with sub_8221F328; the text object (vtable 820193C8) keeps its string
// inline at +124, a rectangle at +8 (x), +12 (y from the bottom of a 1280x720 space), +20 (width), the
// colour at +88..+96, the size at +384, an alignment at +120 (1 centred) and integer arguments at +388.
// The game's font has no glyphs for these languages, so for them the object's letters are blanked while
// it draws (its button icon still shows) and an overlay draws the translated line in the same place.
#include <windows.h>
#include <intrin.h>
#include <rex/logging.h>

#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <chrono>
#include <mutex>
#include <thread>
#include <string>
#include <vector>

#include "arabic_shaping.h"
#include "language_setting.h"

namespace ben10::text_overlay {
struct Entry {
    std::string text;
    float x = 0, y = 0, width = 0, size = 50, red = 1, green = 1, blue = 1, alpha = 1, text_left = 0;
    bool centred = true, has_left = false;
    // Dialogue boxes: translated text is right-aligned in Arabic, limited to `max_lines` lines (the size shrinks to fit),
    // and other overlay text is dimmed while one is showing.
    bool dialogue = false, rtl = false;
    int max_lines = 0;
    float line_pitch = 0;
    ULONGLONG tick = 0;
};
inline std::mutex& Lock() { static std::mutex lock; return lock; }
inline std::map<uint32_t, Entry>& Entries() { static std::map<uint32_t, Entry> entries; return entries; }

inline uint32_t Word(const uint8_t* base, uint32_t address) {
    uint32_t value;
    std::memcpy(&value, base + address, 4);
    return _byteswap_ulong(value);
}
inline float Real(const uint8_t* base, uint32_t address) {
    const uint32_t bits = Word(base, address);
    float value;
    std::memcpy(&value, &bits, 4);
    return value;
}

using Row = std::array<const char*, 4>;  // English, Arabic, Russian, Japanese
inline const std::vector<Row>& Rows() {
    static const std::vector<Row> rows = {
#include "og_text_table.inc"
    };
    return rows;
}

// Where the per-language game text tables (text-<code>.tsv, "English<TAB>translation") live.
inline std::filesystem::path& UserDirectory() { static std::filesystem::path path; return path; }

// FNV-1a over the game's English text. The shipped translation files are keyed by this hash, so they hold the
// translations only and not the original lines (tools/build_game_text_translations.py writes the same hash).
inline uint64_t Hash(const std::string& text) {
    uint64_t hash = 1469598103934665603ull;
    for (const unsigned char c : text) { hash ^= c; hash *= 1099511628211ull; }
    return hash;
}

// <folder of the executable>/translations: the language files that ship with the game.
inline std::filesystem::path ShippedDirectory() {
    wchar_t path[MAX_PATH]{};
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    return std::filesystem::path(path).parent_path() / "translations";
}

// Every translation line of a language (code "ar", "ru", "ja"): the shipped hash-keyed file ("<16 hex>	text"), then a
// private English-keyed file in the user folder ("English	text") that overrides it.
template <typename Visit>
inline void ReadTranslations(const char* code, Visit&& visit) {
    for (int pass = 0; pass < 2; ++pass) {
        const auto folder = pass == 0 ? ShippedDirectory() : UserDirectory();
        if (folder.empty()) continue;
        std::ifstream file(folder / (std::string("text-") + code + ".tsv"), std::ios::binary);
        for (std::string line; std::getline(file, line);) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            const size_t tab = line.find('\t');
            if (tab == std::string::npos) continue;
            uint64_t key = 0;
            if (pass == 0) {
                if (tab != 16) continue;
                key = std::strtoull(line.substr(0, 16).c_str(), nullptr, 16);
            } else {
                key = Hash(line.substr(0, tab));
            }
            visit(key, line.substr(tab + 1));
        }
    }
}

inline const std::map<uint64_t, std::string>& Loaded(int language) {
    static std::mutex lock;
    static std::map<int, std::map<uint64_t, std::string>> tables;
    std::lock_guard guard(lock);
    auto found = tables.find(language);
    if (found != tables.end()) return found->second;
    auto& table = tables[language];
    const char* code = language == 1 ? "ar" : language == 8 ? "ru" : language == 9 ? "ja" : nullptr;
    if (!code) return table;
    ReadTranslations(code, [&](uint64_t key, std::string text) { table[key] = std::move(text); });
    return table;
}

inline std::string Trimmed(const std::string& text) {
    size_t begin = 0, end = text.size();
    while (begin < end && (text[begin] == ' ' || text[begin] == '\t')) ++begin;
    while (end > begin && (text[end - 1] == ' ' || text[end - 1] == '\t')) --end;
    return text.substr(begin, end - begin);
}

// One segment: the overlay table, then the loaded game text table.
inline const char* TranslateSegment(const std::string& english, int language) {
    const int column = language == 1 ? 1 : language == 8 ? 2 : language == 9 ? 3 : 0;
    if (!column) return nullptr;
    for (const Row& row : Rows())
        if (english == row[0]) return row[column];
    const auto& table = Loaded(language);
    const auto found = table.find(Hash(english));
    return found == table.end() ? nullptr : found->second.c_str();
}

// A text object's line in language 1 (Arabic), 8 (Russian) or 9 (Japanese). A line may hold several
// sentences separated by timing tags ({2}, [6.5]); each is translated and they are joined by spaces.
// Button codes inside a line (the game's font draws them as icons) become private-use markers U+E001..U+E01D,
// which the overlay draws as button icons.
inline void IconLabels(std::string& text) {
    std::string result;
    for (const char c : text) {
        const uint8_t code = uint8_t(c);
        if (code >= 1 && code <= 29 && code != '\n' && code != '\t' && code != '\r') {
            result += char(0xEE);
            result += char(0x80);
            result += char(0x80 | code);
        } else if (code >= 0x20 || c == '\n') {
            result += c;
        }
    }
    text = std::move(result);
}

inline bool TranslateLine(const std::string& english, int language, std::string& out);
inline bool Translate(const std::string& english, int language, std::string& out) {
    const bool done = TranslateLine(english, language, out);
    if (done) IconLabels(out);
    return done;
}

inline bool TranslateLine(const std::string& english, int language, std::string& out) {
    if (const char* whole = TranslateSegment(Trimmed(english), language)) { out = whole; return true; }
    std::vector<std::string> parts;
    std::string current;
    for (size_t i = 0; i < english.size(); ++i) {
        const char c = english[i];
        if (c == '{' || c == '[') {
            const char close = c == '{' ? '}' : ']';
            size_t j = i + 1;
            while (j < english.size() && (std::isdigit(uint8_t(english[j])) || english[j] == '.')) ++j;
            if (j < english.size() && english[j] == close) {
                parts.push_back(current);
                current.clear();
                i = j;
                continue;
            }
        }
        current += c;
    }
    parts.push_back(current);
    out.clear();
    int translated = 0;
    for (const auto& part : parts) {
        const std::string trimmed = Trimmed(part);
        if (trimmed.empty()) continue;
        const char* line = TranslateSegment(trimmed, language);
        if (line) ++translated;
        if (!out.empty()) out += ' ';
        out += line ? std::string(line) : trimmed;
    }
    return translated > 0;
}

// Set by the overlay: width in 1280x720 units of `text` at the given size (units), for placing icon labels.
inline std::function<float(const std::string&, float)>& MeasureHook() {
    static std::function<float(const std::string&, float)> hook;
    return hook;
}

// The object's own opacity (+32) times its parents' (+84 chain), as the game's sub_821F8B68 computes it.
inline float Opacity(const uint8_t* base, uint32_t object) {
    float value = 1.0f;
    for (int depth = 0; object && depth < 16; ++depth) {
        value *= Real(base, object + 32);
        object = Word(base, object + 84);
    }
    return value;
}

// Draws the object's letters blank while the original routine runs; restores them afterwards. The entry carries
// the object's opacity (its fade), so hidden and fading texts stay hidden and fade.
class Blank {
public:
    Blank(uint8_t* base, uint32_t object) {
        id_ = object;
        const int language = ben10::language::current.load();
        if (language != 1 && language != 8 && language != 9) return;
        if (Word(base, object) != 0x820193C8) return;
        uint8_t* text = base + object + 124;
        size_t length = 0;
        while (length < 255 && text[length]) ++length;
        size_t prefix = 0;
        while (prefix < length && text[prefix] < 0x20) ++prefix;  // Button icon codes
        size_t begin = prefix;
        while (begin < length && text[begin] == ' ') ++begin;
        const std::string english(reinterpret_cast<const char*>(text + begin), length - begin);
        std::string shown;
        if (!Translate(english, language, shown)) return;
        // Integer arguments replace %d in order.
        const uint32_t count = Word(base, object + 380);
        for (uint32_t i = 0; i < count && i < 4; ++i) {
            const size_t at = shown.find("%d");
            if (at == std::string::npos) break;
            shown.replace(at, 2, std::to_string(int32_t(Word(base, object + 388 + 4 * i))));
        }
        Entry entry;
        entry.text = shown;
        entry.x = Real(base, object + 8);
        entry.y = Real(base, object + 12);
        entry.width = Real(base, object + 20);
        entry.size = Real(base, object + 384);
        entry.red = Real(base, object + 88);
        entry.green = Real(base, object + 92);
        entry.blue = Real(base, object + 96);
        entry.alpha = Opacity(base, object);
        entry.centred = Word(base, object + 120) == 1;
        entry.tick = GetTickCount64();
        // Keep only the button icon (and one space) in the original draw; our line goes after it.
        constexpr float kIcon = 30.0f, kGap = 6.0f;
        size_t blank_to = length;
        if (prefix) {
            blank_to = begin > prefix ? prefix + 1 : prefix;  // icon, one space
            const auto& measure = MeasureHook();
            const float width = measure ? measure(shown, entry.size) : 0.0f;
            if (entry.centred) {
                // Centre the whole "[icon] text" group: shift the original (icon) draw left by half the text.
                const float centre = entry.x + entry.width * 0.5f;
                const float total = kIcon + kGap + width;
                shift_ = -(kGap + width) * 0.5f;
                object_ = base + object + 8;
                saved_x_ = Real(base, object + 8);
                const float shifted = saved_x_ + shift_;
                uint32_t bits;
                std::memcpy(&bits, &shifted, 4);
                bits = _byteswap_ulong(bits);
                std::memcpy(object_, &bits, 4);
                entry.text_left = centre - total * 0.5f + kIcon + kGap;
            } else {
                entry.text_left = entry.x + kIcon + kGap;
            }
            entry.centred = false;
            entry.has_left = true;
            entry.width = 0;
        }
        {
            std::lock_guard guard(Lock());
            Entries()[object] = std::move(entry);
        }
        text_ = text;
        length_ = length;
        std::memcpy(saved_.data(), text, length + 1);
        begin_ = begin;
        blank_to_ = blank_to;
        for (size_t i = begin; i < length; ++i) text[i] = ' ';
        if (prefix && blank_to < length) text[blank_to] = 0;  // draw the icon and a single space only
        else if (prefix == 0) text[0] = 0;
    }
    ~Blank() {
        if (text_) {
            std::memcpy(text_, saved_.data(), length_ + 1);  // letters and terminator
            if (object_) {
                uint32_t bits;
                std::memcpy(&bits, &saved_x_, 4);
                bits = _byteswap_ulong(bits);
                std::memcpy(object_, &bits, 4);
            }
        }
    }
    // The opacity the original draw is about to use (its fade), taken from the call's last argument.
    void Alpha(double value) {
        if (!id_) return;
        (void)value;  // the draw call's last argument is not needed: hidden texts are not an issue with the baked-size drawing
    }
    Blank(const Blank&) = delete;
    Blank& operator=(const Blank&) = delete;

private:
    uint8_t* text_ = nullptr;
    uint8_t* object_ = nullptr;
    uint32_t id_ = 0;
    size_t length_ = 0, begin_ = 0, blank_to_ = 0;
    float shift_ = 0, saved_x_ = 0;
    std::array<uint8_t, 256> saved_{};
};

// Dialogue lines (Gwen's tips, the characters' speech during play) are drawn by sub_821E81D8, which hands the current
// entry's text buffer to sub_821C6C80 (that splits it into lines for sub_821C62D8). The buffer is emptied for that call
// and the translated line is drawn by the overlay in the dialogue box.
class DialogueBlank {
public:
    DialogueBlank(uint8_t* base, uint32_t address, double x, double y, double width) {
        const int language = ben10::language::current.load();
        if (language != 1 && language != 8 && language != 9) return;
        if (address < 0x10000 || address >= 0xC0000000u) return;
        uint8_t* text = base + address;
        size_t length = 0;
        while (length < 127 && text[length]) ++length;
        if (!length) return;
        std::string english(reinterpret_cast<const char*>(text), length);
        for (char& c : english) if (c == '\n' || c == '\r') c = ' ';
        std::string shown;
        if (!Translate(english, language, shown)) return;
        Entry entry;
        entry.text = shown;
        // The box the original draws into: the first line is centred 151.2 up from the bottom, lines 37.44 apart.
        entry.x = (x > 100 && x < 900) ? float(x) : 438.4f;
        entry.y = 151.2f;
        entry.width = (width > 200 && width < 1100) ? float(width) : 530.0f;
        entry.size = 51.2f;
        entry.red = entry.green = entry.blue = 1.0f;
        entry.alpha = 1.0f;
        entry.centred = false;
        entry.dialogue = true;
        entry.rtl = language == 1;
        entry.max_lines = 2;
        entry.line_pitch = 37.44f;
        entry.tick = GetTickCount64();
        {
            std::lock_guard guard(Lock());
            Entries()[0xFFFF0002u] = std::move(entry);
        }
        text_ = text;
        saved_ = text[0];
        text[0] = 0;
    }
    ~DialogueBlank() {
        if (text_) text_[0] = saved_;
    }
    DialogueBlank(const DialogueBlank&) = delete;
    DialogueBlank& operator=(const DialogueBlank&) = delete;

private:
    uint8_t* text_ = nullptr;
    uint8_t saved_ = 0;
};

// sub_821C62D8 is the game's low-level "draw this string here" routine, which HUD banners ("Point of Interest")
// and other texts reach directly. Its string is the stack argument at +84 of the caller's frame, x and y are f1/f2,
// the colour f3..f6 (red, green, blue, opacity), and the low bits of r9 pick the alignment (1 centred, 2 left, 4 right).
// A translatable string loses its letters (a leading button icon stays) and the overlay draws the translation.
class PrimitiveBlank {
public:
    PrimitiveBlank(uint8_t* base, uint32_t sp, uint32_t flags, double x, double y, double red, double green, double blue,
                   double alpha) {
        const int language = ben10::language::current.load();
        if (language != 1 && language != 8 && language != 9) return;
        const uint32_t pointer = Word(base, sp + 84);
        if (pointer < 0x10000 || pointer >= 0xC0000000u) return;
        uint8_t* text = base + pointer;
        size_t length = 0;
        while (length < 255 && text[length]) ++length;
        if (!length || length >= 255) return;
        size_t prefix = 0;
        while (prefix < length && text[prefix] < 0x20) ++prefix;  // Button icon codes
        size_t begin = prefix;
        while (begin < length && text[begin] == ' ') ++begin;
        if (begin >= length) return;
        const std::string english(reinterpret_cast<const char*>(text + begin), length - begin);
        std::string shown;
        if (!Translate(english, language, shown)) return;
        Entry entry;
        entry.text = shown;
        entry.x = float(x);
        entry.y = float(y);
        entry.width = 450.0f;
        entry.size = 51.2f;
        entry.red = float(red);
        entry.green = float(green);
        entry.blue = float(blue);
        entry.alpha = float(alpha);
        constexpr float kIcon = 30.0f, kGap = 6.0f;
        const uint32_t align = flags & 7;
        entry.centred = align == 1;
        if (prefix && !entry.centred) {
            entry.has_left = true;
            entry.text_left = align == 4 ? float(x) : float(x) + kIcon + kGap;
            entry.centred = false;
            entry.width = 0;
        }
        entry.tick = GetTickCount64();
        {
            std::lock_guard guard(Lock());
            Entries()[0xFFFF1000u + (uint32_t(int(y * 4)) & 0x3FFFu) * 16 + (uint32_t(int(x)) & 15u)] = std::move(entry);
        }
        text_ = text;
        length_ = length;
        std::memcpy(saved_.data(), text, length + 1);
        for (size_t i = begin; i < length; ++i) text[i] = ' ';
        if (prefix) text[prefix + (begin > prefix ? 1 : 0)] = 0;  // keep the icon (and one space)
        else text[0] = 0;
    }
    ~PrimitiveBlank() {
        if (text_) std::memcpy(text_, saved_.data(), length_ + 1);
    }
    PrimitiveBlank(const PrimitiveBlank&) = delete;
    PrimitiveBlank& operator=(const PrimitiveBlank&) = delete;

private:
    uint8_t* text_ = nullptr;
    size_t length_ = 0;
    std::array<uint8_t, 256> saved_{};
};

// The title screen's blinking prompt is drawn by a different routine (sub_821C0120), which passes the string
// through the stack slot at `slot` and the rectangle, colour and opacity in f1..f8.
inline void TitleDraw(uint8_t* base, uint32_t slot, double x, double y, double, double width, double red, double green,
                      double blue, double alpha) {
    const int language = ben10::language::current.load();
    if (language != 1 && language != 8 && language != 9) return;
    const uint32_t pointer = Word(base, slot);
    if (pointer < 0x10000) return;
    const char* text = reinterpret_cast<const char*>(base + pointer);
    size_t length = 0;
    while (length < 255 && text[length]) ++length;
    std::string shown;
    if (!Translate(std::string(text, length), language, shown)) return;
    Entry entry;
    entry.text = shown;
    entry.x = float(x);
    entry.y = float(y);
    entry.width = float(width);
    entry.size = 50.0f;
    entry.red = float(red);
    entry.green = float(green);
    entry.blue = float(blue);
    entry.alpha = float(alpha);
    entry.centred = true;
    entry.tick = GetTickCount64();
    {
        std::lock_guard guard(Lock());
        Entries()[0xFFFF0001u] = std::move(entry);
    }
    // Empty the string for the original draw: point at its terminator.
    const uint32_t empty = _byteswap_ulong(pointer + uint32_t(length));
    std::memcpy(base + slot, &empty, 4);
}
}  // namespace ben10::text_overlay

// Diagnostic: finds a string in guest memory and logs the words around it (to identify other text classes).
namespace ben10::text_overlay {
// Logs every 4-byte aligned word holding `target` (a pointer to a string) with the words around it.
inline void ProbeReferences(uint8_t* base, uint32_t target, const char* needle) {
    int found = 0;
    const uint32_t wanted = _byteswap_ulong(target);
    for (uint64_t address = 0x10000; address < 0xC0000000ull && found < 6;) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(base + address, &info, sizeof(info))) break;
        const uint64_t size = info.RegionSize;
        if (info.State == MEM_COMMIT && !(info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            const uint8_t* start = base + address;
            for (uint64_t at = 96; at + 32 <= size && found < 6; at += 4) {
                if (*reinterpret_cast<const uint32_t*>(start + at) != wanted) continue;
                std::string dump;
                char part[32];
                for (int offset = -96; offset < 32; offset += 4) {
                    std::snprintf(part, sizeof(part), "%d:%02X%02X%02X%02X ", offset, start[at + offset], start[at + offset + 1],
                                  start[at + offset + 2], start[at + offset + 3]);
                    dump += part;
                }
                REXLOG_INFO("Cosmic text ref '{}' string {:08X} held at {:08X}: {}", needle, target, uint32_t(address + at), dump);
                ++found;
            }
        }
        address += size ? size : 0x1000;
    }
}

template <typename Host>
inline void ProbeString(Host* host, const char* needle) {
    uint8_t* base = host->memory()->virtual_membase();
    const size_t length = std::strlen(needle);
    int found = 0;
    for (uint64_t address = 0x10000; address < 0xC0000000ull && found < 6;) {
        MEMORY_BASIC_INFORMATION info{};
        if (!VirtualQuery(base + address, &info, sizeof(info))) break;
        const uint64_t size = info.RegionSize;
        if (info.State == MEM_COMMIT && !(info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
            const uint8_t* start = base + address;
            for (uint64_t at = 140; at + length + 8 <= size && found < 6; ++at) {
                if (start[at] != uint8_t(needle[0]) || std::memcmp(start + at, needle, length) != 0) continue;
                std::string dump;
                char part[24];
                for (int offset = -140; offset < 0; offset += 4) {
                    std::snprintf(part, sizeof(part), "%d:%02X%02X%02X%02X ", offset, start[at + offset], start[at + offset + 1],
                                  start[at + offset + 2], start[at + offset + 3]);
                    dump += part;
                }
                REXLOG_INFO("Cosmic text probe '{}' at {:08X}: {}", needle, uint32_t(address + at), dump);
                ++found;
                if (found <= 3) ProbeReferences(base, uint32_t(address + at), needle);
            }
        }
        address += size ? size : 0x1000;
    }
    REXLOG_INFO("Cosmic text probe '{}': {} hits", needle, found);
}

// Diagnostic for sub_821C62D8 (a printf-style text draw called by several UI routines): logs each distinct
// (caller, text) once, with the registers that place and style the text.
inline void ProbeDraw(const uint8_t* base, uint32_t caller, uint32_t sp, uint32_t r3, uint32_t r9, uint32_t r10, double f1,
                      double f2, double f3, double f4, double f5, double f6) {
    static std::mutex lock;
    static std::map<std::string, int> seen;
    static int total = 0;
    std::lock_guard guard(lock);
    if (total > 600) return;
    const uint32_t format = Word(base, sp + 84);
    if (format < 0x10000 || format >= 0xC0000000u) return;
    const char* text = reinterpret_cast<const char*>(base + format);
    size_t length = 0;
    while (length < 160 && text[length] >= 0x09) ++length;
    const std::string line(text, length);
    char key[32];
    std::snprintf(key, sizeof(key), "%08X|", caller);
    if (seen[key + line]++) return;
    ++total;
    std::string arg;
    if (line.find("%s") != std::string::npos) {
        const uint32_t pointer = Word(base, sp + 88);
        if (pointer >= 0x10000 && pointer < 0xC0000000u) {
            const char* s = reinterpret_cast<const char*>(base + pointer);
            size_t n = 0;
            while (n < 160 && s[n] >= 0x09) ++n;
            arg = std::string(s, n);
        }
    }
    REXLOG_INFO("Cosmic draw62D8 caller {:08X} fmt '{}' arg '{}' r3 {:08X} r9 {:X} r10 {:08X} f {} {} {} {} {} {}", caller, line, arg, r3,
                r9, r10, f1, f2, f3, f4, f5, f6);
}

// Diagnostic: probes the dialogue lines every few seconds until they have been seen on screen.
template <typename Host>
inline void StartProbeThread(Host* host) {
    std::thread([host] {
        static const char* needles[] = {"The door's sealed tight! You're going", "On this screen, you can change"};
        for (int round = 0; round < 45; ++round) {
            std::this_thread::sleep_for(std::chrono::seconds(8));
            for (int i = 0; i < 2; ++i) {
                ProbeString(host, needles[i]);
            }
        }
    }).detach();
}
}  // namespace ben10::text_overlay
