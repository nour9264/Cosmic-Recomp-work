#pragma once
// Arabic shaping for Dear ImGui, which has no bidi or joining support: letters become their
// contextual presentation forms and the text is ordered for left-to-right drawing.
// Shared by the launcher and the game's subtitles.
#include <array>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace arabic {
inline bool IsArabicLetter(uint32_t c) { return c >= 0x0621 && c <= 0x064a; }

// Isolated, final, initial, medial presentation forms (0 = none), for U+0621..U+064A.
inline const std::array<uint16_t, 4>& Forms(uint32_t c) {
    static const std::map<uint32_t, std::array<uint16_t, 4>> table = {
        {0x0621, {0xfe80, 0, 0, 0}}, {0x0622, {0xfe81, 0xfe82, 0, 0}}, {0x0623, {0xfe83, 0xfe84, 0, 0}},
        {0x0624, {0xfe85, 0xfe86, 0, 0}}, {0x0625, {0xfe87, 0xfe88, 0, 0}}, {0x0626, {0xfe89, 0xfe8a, 0xfe8b, 0xfe8c}},
        {0x0627, {0xfe8d, 0xfe8e, 0, 0}}, {0x0628, {0xfe8f, 0xfe90, 0xfe91, 0xfe92}}, {0x0629, {0xfe93, 0xfe94, 0, 0}},
        {0x062a, {0xfe95, 0xfe96, 0xfe97, 0xfe98}}, {0x062b, {0xfe99, 0xfe9a, 0xfe9b, 0xfe9c}},
        {0x062c, {0xfe9d, 0xfe9e, 0xfe9f, 0xfea0}}, {0x062d, {0xfea1, 0xfea2, 0xfea3, 0xfea4}},
        {0x062e, {0xfea5, 0xfea6, 0xfea7, 0xfea8}}, {0x062f, {0xfea9, 0xfeaa, 0, 0}}, {0x0630, {0xfeab, 0xfeac, 0, 0}},
        {0x0631, {0xfead, 0xfeae, 0, 0}}, {0x0632, {0xfeaf, 0xfeb0, 0, 0}}, {0x0633, {0xfeb1, 0xfeb2, 0xfeb3, 0xfeb4}},
        {0x0634, {0xfeb5, 0xfeb6, 0xfeb7, 0xfeb8}}, {0x0635, {0xfeb9, 0xfeba, 0xfebb, 0xfebc}},
        {0x0636, {0xfebd, 0xfebe, 0xfebf, 0xfec0}}, {0x0637, {0xfec1, 0xfec2, 0xfec3, 0xfec4}},
        {0x0638, {0xfec5, 0xfec6, 0xfec7, 0xfec8}}, {0x0639, {0xfec9, 0xfeca, 0xfecb, 0xfecc}},
        {0x063a, {0xfecd, 0xfece, 0xfecf, 0xfed0}}, {0x0641, {0xfed1, 0xfed2, 0xfed3, 0xfed4}},
        {0x0642, {0xfed5, 0xfed6, 0xfed7, 0xfed8}}, {0x0643, {0xfed9, 0xfeda, 0xfedb, 0xfedc}},
        {0x0644, {0xfedd, 0xfede, 0xfedf, 0xfee0}}, {0x0645, {0xfee1, 0xfee2, 0xfee3, 0xfee4}},
        {0x0646, {0xfee5, 0xfee6, 0xfee7, 0xfee8}}, {0x0647, {0xfee9, 0xfeea, 0xfeeb, 0xfeec}},
        {0x0648, {0xfeed, 0xfeee, 0, 0}}, {0x0649, {0xfeef, 0xfef0, 0, 0}}, {0x064a, {0xfef1, 0xfef2, 0xfef3, 0xfef4}},
    };
    static const std::array<uint16_t, 4> none{};
    const auto found = table.find(c);
    return found == table.end() ? none : found->second;
}

inline std::vector<uint32_t> Decode(const std::string& text) {
    std::vector<uint32_t> out;
    for (size_t i = 0; i < text.size();) {
        const unsigned char b = text[i];
        uint32_t c = b;
        int extra = 0;
        if (b >= 0xf0) { c = b & 7; extra = 3; } else if (b >= 0xe0) { c = b & 15; extra = 2; } else if (b >= 0xc0) { c = b & 31; extra = 1; }
        ++i;
        for (; extra && i < text.size(); --extra, ++i) c = c << 6 | (text[i] & 63);
        out.push_back(c);
    }
    return out;
}

inline void Append(std::string& out, uint32_t c) {
    if (c < 0x80) out += char(c);
    else if (c < 0x800) { out += char(0xc0 | c >> 6); out += char(0x80 | (c & 63)); }
    else if (c < 0x10000) { out += char(0xe0 | c >> 12); out += char(0x80 | (c >> 6 & 63)); out += char(0x80 | (c & 63)); }
    else { out += char(0xf0 | c >> 18); out += char(0x80 | (c >> 12 & 63)); out += char(0x80 | (c >> 6 & 63)); out += char(0x80 | (c & 63)); }
}

// Joins Arabic letters into their contextual forms and orders the text for left-to-right drawing.
inline std::string Visual(const std::string& text) {
    const std::vector<uint32_t> in = Decode(text);
    auto joinsNext = [](uint32_t c) { return IsArabicLetter(c) && Forms(c)[2] != 0; };           // has an initial form
    auto joinsPrevious = [](uint32_t c) { return IsArabicLetter(c) && Forms(c)[1] != 0; };       // has a final form
    // Shape letter by letter against the original neighbours.
    std::vector<uint32_t> run;
    for (size_t i = 0; i < in.size(); ++i) {
        const uint32_t c = in[i];
        if (!IsArabicLetter(c)) { run.push_back(c); continue; }
        const bool previous = i > 0 && joinsNext(in[i - 1]);
        const bool next = i + 1 < in.size() && joinsPrevious(in[i + 1]);
        if (c == 0x0644 && i + 1 < in.size() && (in[i + 1] == 0x0627 || in[i + 1] == 0x0623 || in[i + 1] == 0x0625 || in[i + 1] == 0x0622)) {
            const uint32_t alef = in[i + 1];
            const uint32_t base = alef == 0x0627 ? 0xfefb : alef == 0x0623 ? 0xfef7 : alef == 0x0625 ? 0xfef9 : 0xfef5;
            run.push_back(previous ? base + 1 : base);
            ++i;
            continue;
        }
        const auto& forms = Forms(c);
        uint32_t glyph = forms[0];
        if (previous && next && forms[3]) glyph = forms[3];
        else if (previous && forms[1]) glyph = forms[1];
        else if (next && forms[2]) glyph = forms[2];
        run.push_back(glyph);
    }
    auto isRight = [](uint32_t c) { return (c >= 0xfe70 && c <= 0xfeff) || (c >= 0x0600 && c <= 0x06ff); };
    auto isLeft = [](uint32_t c) { return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= 0x80 && !((c >= 0xfe70 && c <= 0xfeff) || (c >= 0x0600 && c <= 0x06ff))); };
    // Direction per character: neutrals take the surrounding direction, otherwise the paragraph's (right).
    const size_t n = run.size();
    std::vector<char> direction(n, 'R');
    for (size_t i = 0; i < n; ++i) direction[i] = isRight(run[i]) ? 'R' : isLeft(run[i]) ? 'L' : 'N';
    for (size_t i = 0; i < n; ++i) {
        if (direction[i] != 'N') continue;
        size_t a = i, b = i;
        while (a > 0 && direction[a - 1] == 'N') --a;
        while (b + 1 < n && direction[b + 1] == 'N') ++b;
        const char before = a > 0 ? direction[a - 1] : 'R', after = b + 1 < n ? direction[b + 1] : 'R';
        const char chosen = before == after ? before : 'R';
        for (size_t k = a; k <= b; ++k) direction[k] = chosen;
        i = b;
    }
    // Split into same-direction runs, reverse the run order, and reverse the characters of right-to-left runs.
    std::vector<std::vector<uint32_t>> runs;
    std::vector<char> runDirection;
    for (size_t i = 0; i < n; ++i) {
        if (runs.empty() || runDirection.back() != direction[i]) { runs.emplace_back(); runDirection.push_back(direction[i]); }
        runs.back().push_back(run[i]);
    }
    auto mirrored = [](uint32_t c) { return c == '(' ? uint32_t(')') : c == ')' ? uint32_t('(') : c; };
    std::string out;
    for (size_t r = runs.size(); r-- > 0;) {
        if (runDirection[r] == 'R') for (size_t k = runs[r].size(); k-- > 0;) Append(out, mirrored(runs[r][k]));
        else for (uint32_t c : runs[r]) Append(out, c);
    }
    return out;
}

}  // namespace arabic
