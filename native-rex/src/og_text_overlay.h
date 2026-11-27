#pragma once

// Draws the Russian, Japanese and Arabic lines requested by text_overlay.h over the original menus.
//
// The SDK's ImGui (1.92) bakes glyphs for every new font size lazily, but the presenter uploads the font atlas
// only once, so text drawn at an unbaked size never reaches the screen. As the Options pages do, every line is
// drawn at the font's baked size and its glyph quads are then scaled to the wanted size.
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>

#include <algorithm>
#include <cfloat>

#include "albedo_textures.h"
#include "text_overlay.h"

class Ben10OgText final : public rex::ui::ImGuiDialog {
public:
    Ben10OgText(rex::ui::ImGuiDrawer* drawer, ImFont* font) : ImGuiDialog(drawer), font_(font) {
        // Lets the game thread size an icon label before it draws (width in 1280x720 units).
        ben10::text_overlay::MeasureHook() = [this](const std::string& text, float size) {
            if (!font_) return 0.0f;
            const bool arabic = ben10::language::current.load() == 1;
            return Width(arabic ? arabic::Visual(text) : text, Pixels(size)) / scale_x_;
        };
    }
    // Keep repainting while the game is feeding lines, so they show on every frame.
    bool NeedsContinuousRepaint() override {
        if(ben10_pc_menu::ben_upgrades::active.load(std::memory_order_relaxed))return false;
        std::lock_guard guard(ben10::text_overlay::Lock());
        const ULONGLONG now = GetTickCount64();
        for (const auto& entry : ben10::text_overlay::Entries())
            if (now - entry.second.tick <= 500) return true;
        return false;
    }

protected:
    // Wanted glyph height in pixels for a game text size (1280x720 units).
    float Pixels(float size) const { return std::max(10.0f, size * scale_y_ * 0.62f); }

    // Text and button-icon markers (U+E001..) of a line.
    struct Piece { std::string text; int icon = 0; };
    static std::vector<Piece> Pieces(const std::string& text) {
        std::vector<Piece> pieces;
        std::string current;
        for (size_t i = 0; i < text.size();) {
            if (i + 2 < text.size() && uint8_t(text[i]) == 0xEE && uint8_t(text[i + 1]) == 0x80 && (uint8_t(text[i + 2]) & 0xC0) == 0x80) {
                if (!current.empty()) { pieces.push_back({current, 0}); current.clear(); }
                pieces.push_back({"", uint8_t(text[i + 2]) & 63});
                i += 3;
                continue;
            }
            current += text[i++];
        }
        if (!current.empty()) pieces.push_back({current, 0});
        return pieces;
    }

    static bool PlayStationIcons() { return ben10::albedo_textures::CurrentButtonIcons() == ben10::albedo_textures::ButtonIcons::PlayStation; }

    static const char* ShoulderLabel(int code) {
        if (PlayStationIcons()) {
            switch (code) { case 25: return "SELECT"; case 26: return "L1"; case 27: return "R1"; case 28: return "L2"; case 29: return "R2"; }
        } else {
            switch (code) { case 25: return "BACK"; case 26: return "LB"; case 27: return "RB"; case 28: return "LT"; case 29: return "RT"; }
        }
        return "";
    }

    // Space a button icon takes in a line of `size` pixels.
    float IconWidth(int code, float size) const {
        if (code >= 1 && code <= 4) return size;
        const char* label = ShoulderLabel(code);
        return Width(label, size * 0.55f) + size * 0.5f;
    }

    // Width in pixels at `size` pixels, measured at the baked size and scaled.
    float Width(const std::string& text, float size) const {
        const float base = font_->LegacySize;
        float total = 0;
        for (const Piece& piece : Pieces(text))
            total += piece.icon ? IconWidth(piece.icon, size) : font_->CalcTextSizeA(base, FLT_MAX, 0.0f, piece.text.c_str()).x * (size / base);
        return total;
    }

    static size_t Utf8Length(const std::string& text, size_t at) {
        const unsigned char c = text[at];
        return c >= 0xf0 ? 4 : c >= 0xe0 ? 3 : c >= 0xc0 ? 2 : 1;
    }

    // Greedy wrap of `logical` text to `max_width` pixels. Arabic is shaped per line, so wrapping happens first.
    std::vector<std::string> Wrap(float size, const std::string& logical, float max_width, bool arabic, bool japanese) const {
        auto width = [&](const std::string& line) { return Width(arabic ? arabic::Visual(line) : line, size); };
        std::vector<std::string> tokens;
        for (size_t i = 0; i < logical.size();) {
            if (japanese) { const size_t n = Utf8Length(logical, i); tokens.push_back(logical.substr(i, n)); i += n; continue; }
            size_t j = logical.find(' ', i);
            if (j == std::string::npos) j = logical.size();
            tokens.push_back(logical.substr(i, j - i));
            i = j < logical.size() ? j + 1 : j;
        }
        std::vector<std::string> lines;
        std::string current;
        for (const auto& token : tokens) {
            const std::string candidate = current.empty() ? token : (japanese ? current + token : current + " " + token);
            if (!current.empty() && width(candidate) > max_width) { lines.push_back(current); current = token; }
            else current = candidate;
        }
        if (!current.empty()) lines.push_back(current);
        return lines;
    }

    // Draws `text` with its top-left corner at `pos`, `size` pixels high, from the baked glyphs.
    void DrawScaled(ImDrawList* draw, const std::string& text, ImVec2 pos, float size, ImU32 color) const {
        const float base = font_->LegacySize, stretch = size / base;
        const int first = draw->VtxBuffer.Size;
        draw->AddText(font_, base, pos, color, text.c_str());
        for (int i = first; i < draw->VtxBuffer.Size; ++i) {
            auto& vertex = draw->VtxBuffer[i];
            vertex.pos.x = pos.x + (vertex.pos.x - pos.x) * stretch;
            vertex.pos.y = pos.y + (vertex.pos.y - pos.y) * stretch;
        }
    }

    // A game button as a small icon: PlayStation symbols or Xbox letters, or a pill for shoulders and triggers.
    void DrawIcon(ImDrawList* draw, int code, ImVec2 pos, float size, int alpha) const {
        const bool playstation = PlayStationIcons();
        const float slot = IconWidth(code, size);
        const float height = size * 0.82f, radius = height * 0.5f;
        const ImVec2 centre(pos.x + slot * 0.5f, pos.y + size * 0.52f);
        const float line = std::max(1.5f, size * 0.07f);
        const ImU32 dark = IM_COL32(15, 25, 20, int(215 * alpha / 255.0f)), edge = IM_COL32(225, 235, 230, alpha);
        if (code >= 1 && code <= 4) {
            if (playstation) {
                const ImU32 colours[] = {0, IM_COL32(110, 150, 255, alpha), IM_COL32(255, 135, 205, alpha), IM_COL32(90, 220, 150, alpha), IM_COL32(255, 90, 90, alpha)};
                const ImU32 colour = colours[code];
                const float s = radius * 0.5f;
                draw->AddCircleFilled(centre, radius, dark, 28);
                draw->AddCircle(centre, radius, edge, 28, std::max(1.0f, size * 0.04f));
                switch (code) {
                    case 1:  // cross
                        draw->AddLine(ImVec2(centre.x - s, centre.y - s), ImVec2(centre.x + s, centre.y + s), colour, line);
                        draw->AddLine(ImVec2(centre.x - s, centre.y + s), ImVec2(centre.x + s, centre.y - s), colour, line);
                        break;
                    case 2:  // square
                        draw->AddRect(ImVec2(centre.x - s, centre.y - s), ImVec2(centre.x + s, centre.y + s), colour, 0.0f, 0, line);
                        break;
                    case 3:  // triangle
                        draw->AddTriangle(ImVec2(centre.x, centre.y - s * 1.1f), ImVec2(centre.x - s * 1.15f, centre.y + s * 0.8f),
                                          ImVec2(centre.x + s * 1.15f, centre.y + s * 0.8f), colour, line);
                        break;
                    default:  // circle
                        draw->AddCircle(centre, s * 1.05f, colour, 24, line);
                        break;
                }
            } else {
                const ImU32 colours[] = {0, IM_COL32(110, 200, 90, alpha), IM_COL32(80, 150, 255, alpha), IM_COL32(245, 205, 60, alpha), IM_COL32(235, 80, 70, alpha)};
                static const char* letters[] = {"", "A", "X", "Y", "B"};
                draw->AddCircleFilled(centre, radius, colours[code], 28);
                const float letter = size * 0.55f, w = Width(letters[code], letter);
                DrawScaled(draw, letters[code], ImVec2(centre.x - w * 0.5f, centre.y - letter * 0.5f), letter, IM_COL32(20, 25, 20, alpha));
            }
            return;
        }
        const char* label = ShoulderLabel(code);
        const float pill = slot - size * 0.12f;
        draw->AddRectFilled(ImVec2(centre.x - pill * 0.5f, centre.y - radius), ImVec2(centre.x + pill * 0.5f, centre.y + radius), dark, radius);
        draw->AddRect(ImVec2(centre.x - pill * 0.5f, centre.y - radius), ImVec2(centre.x + pill * 0.5f, centre.y + radius), edge, radius, 0,
                      std::max(1.0f, size * 0.04f));
        const float letter = size * 0.55f, w = Width(label, letter);
        DrawScaled(draw, label, ImVec2(centre.x - w * 0.5f, centre.y - letter * 0.5f), letter, IM_COL32(235, 240, 235, alpha));
    }

    // One line left to right: text pieces from the baked glyphs, button markers as icons (not in the shadow pass).
    void DrawLine(ImDrawList* draw, const std::string& text, ImVec2 pos, float size, ImU32 colour, bool shadow, int alpha) const {
        float x = pos.x;
        for (const Piece& piece : Pieces(text)) {
            if (piece.icon) {
                if (!shadow) DrawIcon(draw, piece.icon, ImVec2(x, pos.y), size, alpha);
                x += IconWidth(piece.icon, size);
            } else {
                DrawScaled(draw, piece.text, ImVec2(x, pos.y), size, colour);
                x += Width(piece.text, size);
            }
        }
    }

    void OnDraw(ImGuiIO& io) override {
        if (!font_ || ben10_pc_menu::ben_upgrades::active.load(std::memory_order_relaxed)) return;
        const ULONGLONG now = GetTickCount64();
        std::vector<ben10::text_overlay::Entry> visible;
        {
            std::lock_guard guard(ben10::text_overlay::Lock());
            auto& entries = ben10::text_overlay::Entries();
            for (auto it = entries.begin(); it != entries.end();)
                if (now - it->second.tick > 1000) it = entries.erase(it);
                else { if (now - it->second.tick <= 120) visible.push_back(it->second); ++it; }
        }
        scale_x_ = io.DisplaySize.x / 1280.0f;
        scale_y_ = io.DisplaySize.y / 720.0f;
        if (visible.empty()) return;
        const int language = ben10::language::current.load();
        const bool arabic = language == 1, japanese = language == 9;
        auto* draw = ImGui::GetForegroundDrawList();
        // A dialogue box dims the rest of the screen (the game fades its menus behind it); the overlay text follows.
        bool dialogue_showing = false;
        for (const auto& entry : visible) dialogue_showing |= entry.dialogue && entry.alpha >= 0.02f;
        for (const auto& entry : visible) {
            if (entry.alpha < 0.02f) continue;  // hidden, or fully faded
            float size = Pixels(entry.size);
            const float max_width = entry.width > 0 ? entry.width * scale_x_ : 1000.0f * scale_x_;
            auto lines = Wrap(size, entry.text, max_width, arabic, japanese);
            for (int shrink = 0; entry.max_lines > 0 && int(lines.size()) > entry.max_lines && shrink < 12; ++shrink) {
                size *= 0.92f;  // a longer translation: smaller letters, so it still fits the box
                lines = Wrap(size, entry.text, max_width, arabic, japanese);
            }
            const float line_height = entry.line_pitch > 0 ? entry.line_pitch * scale_y_ : size * 1.18f;
            const float fade = std::clamp(entry.alpha, 0.0f, 1.0f) * (dialogue_showing && !entry.dialogue ? 0.12f : 1.0f);
            const ImU32 color = IM_COL32(int(std::clamp(entry.red, 0.0f, 1.0f) * 255), int(std::clamp(entry.green, 0.0f, 1.0f) * 255),
                                         int(std::clamp(entry.blue, 0.0f, 1.0f) * 255), int(fade * 255));
            float y = (720.0f - entry.y) * scale_y_ - line_height * 0.5f;
            for (const auto& line : lines) {
                const std::string shown = arabic ? arabic::Visual(line) : line;
                const float extent = Width(shown, size);
                const float x = entry.rtl ? (entry.x + entry.width) * scale_x_ - extent
                              : entry.has_left ? entry.text_left * scale_x_
                              : entry.centred ? (entry.x + entry.width * 0.5f) * scale_x_ - extent * 0.5f : entry.x * scale_x_;
                DrawLine(draw, shown, ImVec2(x + 2, y + 2), size, IM_COL32(0, 0, 0, int(170 * fade)), true, int(255 * fade));
                DrawLine(draw, shown, ImVec2(x, y), size, color, false, int(255 * fade));
                y += line_height;
            }
        }
    }

private:
    ImFont* font_;
    float scale_x_ = 1.5f, scale_y_ = 1.5f;
};
