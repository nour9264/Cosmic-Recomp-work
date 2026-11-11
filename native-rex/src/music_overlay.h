#pragma once
// Quick Music Overlay: a compact panel over gameplay for the active Windows
// media session (music_session.h). Opens with M or View / Share during
// gameplay only. While open it holds game input like the Options pages
// (ben10_pc_video::music_overlay is part of CapturesGameInput), so its keys
// and buttons never reach the game; gameplay itself keeps running.
#include "music_session.h"
#include "options_video_preview.h"
#include <rex/ui/immediate_drawer.h>
#include <imgui.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace ben10::music_overlay {
class Overlay final : public rex::ui::ImGuiDialog {
 public:
  using ImmediateSource = std::function<rex::ui::ImmediateDrawer*()>;
  Overlay(rex::ui::ImGuiDrawer* drawer, ImFont* font, std::array<ImFontAtlasRectId, 2> badges, ImmediateSource immediate)
      : ImGuiDialog(drawer), font_(font), badges_(badges), immediate_(std::move(immediate)) {}
  bool NeedsContinuousRepaint() override { return ben10_pc_video::music_overlay.load(); }

 private:
  static constexpr int kDuckingFocus = 4;
  ImFont* font_;
  std::array<ImFontAtlasRectId, 2> badges_;
  ImmediateSource immediate_;
  // Album art lives in its own texture; the font atlas is uploaded only once.
  std::unique_ptr<rex::ui::ImmediateTexture> art_;
  uint32_t art_id_ = 0;
  int focus_ = 1;  // 0 previous, 1 play/pause, 2 next, 3 close, 4 ducking.
  uint16_t last_buttons_ = 0;
  bool armed_ = false;  // Ignore the keys/buttons that opened the overlay.

  // Music priority: how far the game audio drops while music plays, 0% = Off.
  static int Ducking(const ben10::music::Settings& settings) { return settings.priority; }
  static void SetDucking(int value) {
    auto settings = ben10::music::CurrentSettings();
    value = std::clamp(value, 0, 100) / 5 * 5;
    if (value == Ducking(settings)) return;
    settings.priority = value;
    ben10::music::UpdateSettings(settings);
  }

  void UpdateArtwork(uint32_t id) {
    if (id == art_id_) return;
    if (!id) { art_.reset(); art_id_ = 0; return; }
    auto* immediate = immediate_ ? immediate_() : nullptr;
    std::vector<uint8_t> pixels;
    if (!immediate || !ben10::music::Artwork(pixels)) return;  // Retried next frame.
    constexpr auto size = ben10::music::kArtworkSize;
    art_ = immediate->CreateTexture(size, size, rex::ui::ImmediateTextureFilter::kLinear, false, pixels.data());
    art_id_ = id;
  }

  static bool Gameplay() {
    return ben10_pc_menu::mission_active.load() && !ben10_pc_menu::pause_menu_active.load() &&
           !ben10_pc_video::visible.load() && !ben10::cinematic_player::Playing();
  }

  void SetOpen(bool open) {
    ben10_pc_video::music_overlay = open;
    ben10::music::SetOverlayOpen(open);
    armed_ = false;
    focus_ = 1;
    // Drop the snapshot left over from earlier menus: arming must see the
    // current controller state, or the held opening press reads as a close.
    ben10_pc_video::controller_sample = 0;
    // Closing: keep game input held until the closing key is released.
    if (!open) {
      ben10_pc_video::release_guard = true;
      view_latch = true;
      toggle_request = false;
    }
  }

  static std::string Time(double seconds) {
    const int total = int(std::max(0.0, seconds));
    return std::to_string(total / 60) + ":" + (total % 60 < 10 ? "0" : "") + std::to_string(total % 60);
  }

  void OnDraw(ImGuiIO& io) override {
    const bool integration = ben10::music::CurrentSettings().integration;
    const bool open = ben10_pc_video::music_overlay.load();
    const bool shortcut = toggle_request.exchange(false) ||
        (!io.WantTextInput && ImGui::IsKeyPressed(ImGuiKey_M, false) && !io.KeyCtrl && !io.KeyAlt);
    if (!open) {
      if (shortcut && integration && Gameplay()) SetOpen(true);
      return;
    }
    if (!Gameplay() || !integration) { SetOpen(false); return; }

    // Navigation: keyboard through ImGui, controller through the UI snapshot.
    const auto sample = ben10_pc_video::controller_sample.load(std::memory_order_relaxed);
    const uint16_t buttons = (sample & ben10_pc_video::sample_valid) ? uint16_t(sample) : 0;
    bool any_key = false;
    for (ImGuiKey key : {ImGuiKey_M, ImGuiKey_Escape, ImGuiKey_Enter, ImGuiKey_Space, ImGuiKey_LeftArrow, ImGuiKey_RightArrow,
                         ImGuiKey_UpArrow, ImGuiKey_DownArrow, ImGuiKey_Q, ImGuiKey_E})
      any_key |= ImGui::IsKeyDown(key);
    if (!armed_) {
      // Wait until the opening input is released before reacting to anything.
      if ((sample & ben10_pc_video::sample_valid) && !buttons && !any_key) armed_ = true;
      last_buttons_ = buttons;
    }
    const uint16_t pressed = armed_ ? uint16_t(buttons & ~last_buttons_) : 0;
    last_buttons_ = buttons;
    auto key = [&](ImGuiKey code, bool repeat = false) { return armed_ && ImGui::IsKeyPressed(code, repeat); };
    const bool left = (pressed & 0x4) || key(ImGuiKey_LeftArrow, true);
    const bool right = (pressed & 0x8) || key(ImGuiKey_RightArrow, true);
    const int ducking = Ducking(ben10::music::CurrentSettings());
    if ((pressed & 0x1) || key(ImGuiKey_UpArrow)) { if (focus_ == kDuckingFocus) focus_ = 1; }
    if ((pressed & 0x2) || key(ImGuiKey_DownArrow)) focus_ = kDuckingFocus;
    if (focus_ == kDuckingFocus) {
      if (left) SetDucking(ducking - 5);
      if (right) SetDucking(ducking + 5);
    } else {
      if (left) focus_ = (focus_ + 3) % 4;
      if (right) focus_ = (focus_ + 1) % 4;
    }
    bool activate = (pressed & 0x1000) || key(ImGuiKey_Enter);
    // Direct shortcuts: LB / L1 or Q previous, X / Square or Space play-pause, RB / R1 or E next.
    int direct = -1;
    if ((pressed & 0x100) || key(ImGuiKey_Q)) direct = 0;
    if ((pressed & 0x4000) || key(ImGuiKey_Space)) direct = 1;
    if ((pressed & 0x200) || key(ImGuiKey_E)) direct = 2;
    if (direct >= 0) { focus_ = direct; activate = true; }
    bool close = (pressed & 0x2000) || (pressed & 0x20) || key(ImGuiKey_Escape) || key(ImGuiKey_M);

    const auto music = ben10::music::Current();
    UpdateArtwork(music.artwork);
    const bool has_session = music.status != ben10::music::Status::none;
    const bool albedo = ben10::albedo_hud::enabled.load();
    const ImU32 accent = albedo ? IM_COL32(255, 59, 57, 255) : IM_COL32(151, 235, 40, 255);
    const ImU32 dim = albedo ? IM_COL32(110, 40, 38, 255) : IM_COL32(60, 96, 30, 255);
    const ImU32 panel = albedo ? IM_COL32(20, 8, 9, 236) : IM_COL32(8, 18, 9, 236);
    const ImU32 white = IM_COL32(239, 250, 230, 255), muted = IM_COL32(170, 190, 165, 255);
    const float scale = std::min(io.DisplaySize.x / 1280.0f, io.DisplaySize.y / 720.0f);
    if (scale <= 0) return;
    const ImVec2 size(500 * scale, 190 * scale);
    const ImVec2 origin((io.DisplaySize.x - size.x) * 0.5f, 18 * scale);
    auto point = [&](float x, float y) { return ImVec2(origin.x + x * scale, origin.y + y * scale); };

    ImGui::SetNextWindowPos(origin, ImGuiCond_Always);
    ImGui::SetNextWindowSize(size, ImGuiCond_Always);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0, 0, 0, 0));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0);
    if (font_) ImGui::PushFont(font_);
    if (ImGui::Begin("Cosmic Music", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoSavedSettings |
                     ImGuiWindowFlags_NoNav | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoFocusOnAppearing)) {
      auto* draw = ImGui::GetWindowDrawList();
      // Text at a fixed baked size, scaled by moving glyph quads (see VideoPage).
      auto label = [&](const std::string& text, float height, float x, float y, ImU32 color, float max_width) {
        const auto extent = ImGui::CalcTextSize(text.c_str());
        if (extent.y <= 0) return;
        float stretch = height * scale / extent.y;
        if (extent.x * stretch > max_width * scale) stretch = max_width * scale / extent.x;
        const auto pos = point(x, y);
        const int first = draw->VtxBuffer.Size;
        draw->AddText(pos, color, text.c_str());
        for (int i = first; i < draw->VtxBuffer.Size; ++i) {
          auto& vertex = draw->VtxBuffer[i];
          vertex.pos.x = pos.x + (vertex.pos.x - pos.x) * stretch;
          vertex.pos.y = pos.y + (vertex.pos.y - pos.y) * stretch;
        }
      };
      const ImVec2 frame[] = {point(14, 0), point(500, 0), point(500, 176), point(486, 190), point(0, 190), point(0, 14)};
      draw->AddConvexPolyFilled(frame, 6, panel);
      draw->AddPolyline(frame, 6, accent, ImDrawFlags_Closed, 2 * scale);

      // Artwork: the track's album art, else the Omnitrix badge.
      ImFontAtlasRect badge;
      if (art_ && has_session) {
        draw->AddImageRounded(ImTextureRef(reinterpret_cast<ImTextureID>(art_.get())), point(12, 12), point(96, 96),
                              ImVec2(0, 0), ImVec2(1, 1), IM_COL32_WHITE, 6 * scale);
        draw->AddRect(point(12, 12), point(96, 96), accent, 6 * scale, 0, 1.5f * scale);
      } else if (io.Fonts->GetCustomRect(badges_[albedo ? 1 : 0], &badge))
        draw->AddImage(io.Fonts->TexRef, point(12, 12), point(96, 96), badge.uv0, badge.uv1);
      else
        draw->AddCircle(point(54, 54), 38 * scale, accent, 32, 3 * scale);

      if (!has_session) {
        label("No music player detected", 20, 110, 22, white, 370);
        label("Play music in Spotify or another media app", 14, 110, 52, muted, 370);
      } else {
        label(music.title.empty() ? "Unknown track" : music.title, 20, 110, 12, white, 375);
        std::string detail = music.artist;
        if (!music.app.empty()) detail += (detail.empty() ? "" : "  |  ") + music.app;
        if (music.status == ben10::music::Status::paused) detail += "  |  Paused";
        label(detail, 14, 110, 38, muted, 375);
        const float fraction = music.duration > 0 ? float(music.position / music.duration) : 0.0f;
        draw->AddRectFilled(point(110, 62), point(400, 66), dim, 2 * scale);
        draw->AddRectFilled(point(110, 62), point(110 + 290 * fraction, 66), accent, 2 * scale);
        if (music.duration > 0)
          label(Time(music.position) + " / " + Time(music.duration), 13, 408, 56, muted, 85);
      }

      // Buttons: previous, play/pause, next, close.
      const bool enabled[] = {has_session && music.can_previous, has_session && music.can_toggle,
                              has_session && music.can_next, true};
      for (int i = 0; i < 4; ++i) {
        const float x = 110 + i * 62.0f, y = 78;
        ImGui::PushID(i);
        ImGui::SetCursorScreenPos(point(x, y));
        if (ImGui::InvisibleButton("button", ImVec2(52 * scale, 34 * scale))) { focus_ = i; activate = true; }
        if (ImGui::IsItemHovered() && (io.MouseDelta.x || io.MouseDelta.y)) focus_ = i;
        ImGui::PopID();
        const bool focused = focus_ == i;
        const ImU32 ink = !enabled[i] ? dim : focused ? IM_COL32(15, 20, 12, 255) : accent;
        if (focused) draw->AddRectFilled(point(x, y), point(x + 52, y + 34), enabled[i] ? accent : dim, 6 * scale);
        draw->AddRect(point(x, y), point(x + 52, y + 34), enabled[i] ? accent : dim, 6 * scale, 0, 1.5f * scale);
        const ImVec2 c = point(x + 26, y + 17);
        auto tri = [&](float dx, float sign) {
          draw->AddTriangleFilled(ImVec2(c.x + (dx + sign * 7) * scale, c.y), ImVec2(c.x + (dx - sign * 6) * scale, c.y - 8 * scale),
                                  ImVec2(c.x + (dx - sign * 6) * scale, c.y + 8 * scale), ink);
        };
        if (i == 0) { draw->AddRectFilled(ImVec2(c.x - 11 * scale, c.y - 8 * scale), ImVec2(c.x - 8 * scale, c.y + 8 * scale), ink); tri(2, -1); }
        if (i == 2) { tri(-2, 1); draw->AddRectFilled(ImVec2(c.x + 8 * scale, c.y - 8 * scale), ImVec2(c.x + 11 * scale, c.y + 8 * scale), ink); }
        if (i == 1) {
          if (music.status == ben10::music::Status::playing) {
            draw->AddRectFilled(ImVec2(c.x - 7 * scale, c.y - 8 * scale), ImVec2(c.x - 2 * scale, c.y + 8 * scale), ink);
            draw->AddRectFilled(ImVec2(c.x + 2 * scale, c.y - 8 * scale), ImVec2(c.x + 7 * scale, c.y + 8 * scale), ink);
          } else tri(1, 1);
        }
        if (i == 3) {
          draw->AddLine(ImVec2(c.x - 7 * scale, c.y - 7 * scale), ImVec2(c.x + 7 * scale, c.y + 7 * scale), ink, 2.5f * scale);
          draw->AddLine(ImVec2(c.x + 7 * scale, c.y - 7 * scale), ImVec2(c.x - 7 * scale, c.y + 7 * scale), ink, 2.5f * scale);
        }
      }

      // Shortcut glyphs under the buttons, in the current button icon mode.
      using Icons = ben10::albedo_textures::ButtonIcons;
      const auto icons = ben10::albedo_textures::button_icons.load(std::memory_order_relaxed);
      for (int i = 0; i < 4; ++i) {
        const ImVec2 c = point(110 + i * 62.0f + 26, 124);
        const ImU32 ink = enabled[i] ? white : dim;
        auto pill = [&](const char* text, float width) {
          draw->AddRect(ImVec2(c.x - width * 0.5f * scale, c.y - 7 * scale), ImVec2(c.x + width * 0.5f * scale, c.y + 7 * scale),
                        ink, 4 * scale, 0, 1.2f * scale);
          const float w = ImGui::CalcTextSize(text).x * 10 * scale / std::max(1.0f, ImGui::CalcTextSize(text).y);
          label(text, 10, (c.x - w * 0.5f - origin.x) / scale, (c.y - 5 * scale - origin.y) / scale, ink, width - 4);
        };
        if (icons == Icons::Keyboard) {
          static const char* keys[] = {"Q", "Space", "E", "M"};
          ImFontAtlasRect keycap;
          const auto id = ben10::controls::KeyIconForToken(keys[i]);
          if (id != ImFontAtlasRectId_Invalid && io.Fonts->GetCustomRect(id, &keycap))
            draw->AddImage(io.Fonts->TexRef, ImVec2(c.x - 9 * scale, c.y - 9 * scale), ImVec2(c.x + 9 * scale, c.y + 9 * scale),
                           keycap.uv0, keycap.uv1, enabled[i] ? IM_COL32_WHITE : IM_COL32(255, 255, 255, 110));
          else pill(keys[i], 30);
        } else if (icons == Icons::PlayStation) {
          if (i == 0) pill("L1", 24);
          if (i == 2) pill("R1", 24);
          if (i == 1) {
            const ImU32 pink = enabled[i] ? IM_COL32(232, 140, 200, 255) : dim;
            draw->AddCircle(c, 8 * scale, pink, 20, 1.2f * scale);
            draw->AddRect(ImVec2(c.x - 3.5f * scale, c.y - 3.5f * scale), ImVec2(c.x + 3.5f * scale, c.y + 3.5f * scale), pink, 0, 0, 1.2f * scale);
          }
          if (i == 3) pill("SHARE", 36);
        } else {
          if (i == 0) pill("LB", 24);
          if (i == 2) pill("RB", 24);
          if (i == 1) {
            const ImU32 blue = enabled[i] ? IM_COL32(64, 140, 255, 255) : dim;
            draw->AddCircleFilled(c, 8 * scale, blue, 20);
            const float w = ImGui::CalcTextSize("X").x * 10 * scale / std::max(1.0f, ImGui::CalcTextSize("X").y);
            label("X", 10, (c.x - w * 0.5f - origin.x) / scale, (c.y - 5 * scale - origin.y) / scale, IM_COL32_WHITE, 10);
          }
          if (i == 3) {
            // View: two overlapping windows.
            draw->AddCircle(c, 8 * scale, ink, 20, 1.2f * scale);
            draw->AddRect(ImVec2(c.x - 4 * scale, c.y - 3.5f * scale), ImVec2(c.x + 1.5f * scale, c.y + 1 * scale), ink, 0, 0, 1 * scale);
            draw->AddRect(ImVec2(c.x - 1.5f * scale, c.y - 1 * scale), ImVec2(c.x + 4 * scale, c.y + 3.5f * scale), ink, 0, 0, 1 * scale);
          }
        }
      }

      // Music priority: how far the game audio drops while music plays.
      {
        const bool focused = focus_ == kDuckingFocus;
        const float x0 = 270, x1 = 420, y = 152;
        label("Music priority", 13, 110, 144, focused ? white : muted, 155);
        ImGui::SetCursorScreenPos(point(x0 - 6, y - 10));
        ImGui::InvisibleButton("ducking", ImVec2((x1 - x0 + 12) * scale, 20 * scale));
        if (ImGui::IsItemHovered() && (io.MouseDelta.x || io.MouseDelta.y)) focus_ = kDuckingFocus;
        if (ImGui::IsItemActive()) {
          focus_ = kDuckingFocus;
          const float t = std::clamp((io.MousePos.x - point(x0, 0).x) / ((x1 - x0) * scale), 0.0f, 1.0f);
          SetDucking(int(std::lround(t * 20)) * 5);
        }
        const int value = Ducking(ben10::music::CurrentSettings());
        const float fill = x0 + (x1 - x0) * value / 100.0f;
        if (focused) draw->AddRect(point(104, y - 13), point(492, y + 13), accent, 6 * scale, 0, 1.5f * scale);
        draw->AddRectFilled(point(x0, y - 2), point(x1, y + 2), dim, 2 * scale);
        draw->AddRectFilled(point(x0, y - 2), point(fill, y + 2), accent, 2 * scale);
        draw->AddCircleFilled(point(fill, y), (focused ? 7 : 5) * scale, focused ? white : accent, 16);
        label(value <= 0 ? std::string("Off") : std::to_string(value) + "%", 13, 432, 144, focused ? white : muted, 55);
      }

      // Prompt hints in the current button icon mode.
      auto prompt = [&](bool confirm, float x, const char* text) {
        const ImVec2 c = point(x, 180);
        ImFontAtlasRect keycap;
        // The overlay reads Enter / Esc itself, so show those keys, not game bindings.
        const auto keyboard = icons == Icons::Keyboard ?
            ben10::controls::KeyIconForToken(confirm ? "Return" : "Escape") : ImFontAtlasRectId_Invalid;
        if (keyboard != ImFontAtlasRectId_Invalid && io.Fonts->GetCustomRect(keyboard, &keycap)) {
          draw->AddImage(io.Fonts->TexRef, ImVec2(c.x - 8 * scale, c.y - 8 * scale), ImVec2(c.x + 8 * scale, c.y + 8 * scale),
                         keycap.uv0, keycap.uv1);
        } else {
          const bool ps = icons == Icons::PlayStation;
          const ImU32 color = confirm ? (ps ? IM_COL32(126, 173, 255, 255) : IM_COL32(163, 248, 50, 255)) : IM_COL32(255, 114, 125, 255);
          draw->AddCircle(c, 7 * scale, color, 20, 1.5f * scale);
          if (ps && confirm) {
            draw->AddLine(ImVec2(c.x - 3 * scale, c.y - 3 * scale), ImVec2(c.x + 3 * scale, c.y + 3 * scale), color, 1.5f * scale);
            draw->AddLine(ImVec2(c.x - 3 * scale, c.y + 3 * scale), ImVec2(c.x + 3 * scale, c.y - 3 * scale), color, 1.5f * scale);
          } else if (ps) draw->AddCircle(c, 3 * scale, color, 12, 1.5f * scale);
          else label(confirm ? "A" : "B", 10, x - 3, 174, color, 10);
        }
        label(text, 11, x + 11, 174, muted, 80);
      };
      prompt(true, 362, "Select");
      prompt(false, 428, "Close");
    }
    ImGui::End();
    if (font_) ImGui::PopFont();
    ImGui::PopStyleVar(2);
    ImGui::PopStyleColor();

    if (activate && armed_) {
      if (focus_ == kDuckingFocus) SetDucking(ducking > 0 ? 0 : ben10::music::Settings{}.priority);
      else if (focus_ == 3) close = true;
      else if (has_session && music.can_previous && focus_ == 0) ben10::music::Request(ben10::music::Command::previous);
      else if (has_session && music.can_toggle && focus_ == 1) ben10::music::Request(ben10::music::Command::toggle);
      else if (has_session && music.can_next && focus_ == 2) ben10::music::Request(ben10::music::Command::next);
    }
    if (close && armed_) SetOpen(false);
  }
};
}
