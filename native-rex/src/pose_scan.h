#pragma once

// Diagnostic: finds the array of bone matrices the game keeps for a character and logs it. A bone matrix is a rigid 4x4 of
// 16 big-endian floats (rows 0-2 are the axes, row 3 the position, the last column 0 0 0 1), 64 bytes apart in an array.
// The scan walks the character object and every pointer found in its first bytes, and reports runs of consecutive matrices.

#include <rex/logging.h>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <intrin.h>
#include <string>
#include <vector>
#include <windows.h>

namespace ben10::pose_scan {
inline std::atomic<int> reports{0};

inline bool Readable(const uint8_t* address, size_t size) {
    MEMORY_BASIC_INFORMATION info{};
    return VirtualQuery(address, &info, sizeof(info)) && info.State == MEM_COMMIT &&
           !(info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) &&
           address + size <= static_cast<const uint8_t*>(info.BaseAddress) + info.RegionSize;
}
inline float F(const uint8_t* p) {
    uint32_t v;
    std::memcpy(&v, p, 4);
    v = _byteswap_ulong(v);
    float f;
    std::memcpy(&f, &v, 4);
    return f;
}
inline bool IsMatrix(const uint8_t* p) {
    float m[16];
    for (int i = 0; i < 16; ++i) {
        m[i] = F(p + 4 * i);
        if (!(m[i] == m[i]) || m[i] > 1.0e3f || m[i] < -1.0e3f) return false;
    }
    if (std::fabs(m[3]) > 1e-3f || std::fabs(m[7]) > 1e-3f || std::fabs(m[11]) > 1e-3f || std::fabs(m[15] - 1.0f) > 1e-3f) return false;
    for (int r = 0; r < 3; ++r) {
        const float len = std::sqrt(m[4 * r] * m[4 * r] + m[4 * r + 1] * m[4 * r + 1] + m[4 * r + 2] * m[4 * r + 2]);
        if (len < 0.2f || len > 5.0f) return false;
    }
    return true;
}
inline uint32_t Load(const uint8_t* base, uint32_t g) {
    uint32_t v;
    std::memcpy(&v, base + g, 4);
    return _byteswap_ulong(v);
}
inline bool Ok(uint32_t g) { return g >= 0x10000 && g < 0xe0000000u; }

// Scans [start, start + span) (guest addresses) for runs of at least `minimum` consecutive matrices; logs the longest ones.
inline void ScanRegion(const uint8_t* base, uint32_t start, uint32_t span, const char* label, int& best_length, uint32_t& best_at) {
    if (!Ok(start) || !Readable(base + start, span)) return;
    for (uint32_t at = start; at + 64 <= start + span; at += 4) {
        if (!IsMatrix(base + at)) continue;
        int run = 1;
        while (at + 64 * (run + 1) <= start + span && IsMatrix(base + at + 64 * run)) ++run;
        if (run >= 20) {
            REXLOG_INFO("Pose scan: {} run of {} matrices at {:08X} (offset {:#x})", label, run, at, at - start);
            if (run > best_length) best_length = run, best_at = at;
            at += 64 * run - 4;
        }
    }
}

struct Run { uint32_t at; int length; };
// Every run of at least `minimum` consecutive bone-like matrices reachable from the character (one pointer level deep).
inline std::vector<Run> FindRuns(const uint8_t* base, uint32_t character, int minimum) {
    std::vector<Run> runs;
    auto scan = [&](uint32_t start, uint32_t span) {
        if (!Ok(start) || !Readable(base + start, span)) return;
        for (uint32_t at = start; at + 64 <= start + span; at += 4) {
            if (!IsMatrix(base + at)) continue;
            int run = 1;
            while (at + 64 * (run + 1) <= start + span && IsMatrix(base + at + 64 * run)) ++run;
            if (run >= minimum) {
                bool seen = false;
                for (const Run& r : runs) seen |= (at >= r.at && at < r.at + 64u * r.length);
                if (!seen) runs.push_back({at, run});
            }
            at += 64 * run - 4;
        }
    };
    scan(character, 0x2000);
    for (uint32_t off = 0; off < 0x800; off += 4) {
        const uint32_t pointer = Load(base, character + off);
        if (Ok(pointer) && pointer != character) scan(pointer, 0x3000);
    }
    return runs;
}
inline void Scan(const uint8_t* base, uint32_t character) {
    if (reports.fetch_add(1) >= 4) return;
    const std::vector<Run> runs = FindRuns(base, character, 20);
    REXLOG_INFO("Pose scan {}: {} arrays", reports.load(), runs.size());
    int index = 0;
    for (const Run& r : runs) {
        const int count = r.length < 128 ? r.length : 128;
        REXLOG_INFO("Pose run {} at {:08X}: {} matrices (logging {})", index, r.at, r.length, count);
        for (int i = 0; i < count; ++i) {
            const uint8_t* m = base + r.at + 64 * i;
            REXLOG_INFO("PR{} #{} {:.4f} {:.4f} {:.4f} | {:.4f} {:.4f} {:.4f} | {:.4f} {:.4f} {:.4f} | {:.4f} {:.4f} {:.4f}", index, i,
                        F(m), F(m + 4), F(m + 8), F(m + 16), F(m + 20), F(m + 24), F(m + 32), F(m + 36), F(m + 40), F(m + 48), F(m + 52), F(m + 56));
        }
        ++index;
    }
}

// ---- Experiment: write the character's bone matrices from a control file next to ben10.exe (goop_pose_test.txt).
// Modes: "identity" writes the identity to every bone matrix; anything else does nothing.
inline void StoreF(uint8_t* base, uint32_t g, float f) {
    uint32_t v;
    std::memcpy(&v, &f, 4);
    v = _byteswap_ulong(v);
    std::memcpy(base + g, &v, 4);
}
inline std::string ReadMode() {
    static ULONGLONG last = 0;
    static std::string mode;
    const ULONGLONG now = GetTickCount64();
    if (now - last < 500) return mode;
    last = now;
    char path[MAX_PATH]{};
    GetModuleFileNameA(nullptr, path, MAX_PATH);
    std::string file = path;
    file = file.substr(0, file.find_last_of("\/") + 1) + "goop_pose_test.txt";
    mode.clear();
    static bool reported = false;
    FILE* opened = std::fopen(file.c_str(), "rb");
    if (!reported) {
        reported = true;
        REXLOG_INFO("Pose override: control file {} {}", file, opened ? "found" : "not found (experiment off)");
    }
    if (!opened) return mode;   // No file: the experiment is off.
    if (FILE* f = opened) {
        char line[64]{};
        if (std::fgets(line, sizeof(line), f)) mode = line;
        std::fclose(f);
        while (!mode.empty() && (mode.back() == '\n' || mode.back() == '\r' || mode.back() == ' ')) mode.pop_back();
    }
    return mode;
}
inline void Override(uint8_t* base, uint32_t character) {
    const std::string mode = ReadMode();
    if (mode.empty()) return;
    static std::vector<Run> runs;
    static uint32_t runs_character = 0;
    static int age = 0;
    if (runs_character != character || ++age > 120) {
        runs = FindRuns(base, character, 30);
        runs_character = character;
        age = 0;
        REXLOG_INFO("Pose override: {} candidate arrays", runs.size());
        for (const Run& r : runs) REXLOG_INFO("Pose override: array at {:08X}, {} matrices", r.at, r.length);
    }
    if (mode == "identity") {
        for (const Run& r : runs)
            if (Readable(base + r.at, 64u * r.length))
                for (int i = 0; i < r.length; ++i)
                    for (int k = 0; k < 16; ++k) StoreF(base, r.at + 64 * i + 4 * k, (k % 5 == 0) ? 1.0f : 0.0f);
    }
}
}  // namespace ben10::pose_scan
