#pragma once

#include "pc_menu_bridge.h"
#include "cinematic_player.h"
#include <rex/input/mnk/mnk_input_driver.h>
#include <algorithm>

namespace ben10 {
class MenuCursor final : public rex::ui::ImGuiDialog {
 public:
  MenuCursor(rex::ui::ImGuiDrawer* drawer, ImFontAtlasRectId sprite, ImFontAtlasRectId albedo_sprite)
      : ImGuiDialog(drawer), sprite_(sprite), albedo_sprite_(albedo_sprite),
        tracks_missions_(std::getenv("BEN10_DISCORD_STATUS_FILE") != nullptr) {}
  bool NeedsContinuousRepaint() override { return false; }

 private:
  void OnDraw(ImGuiIO& io) override {
    auto* window = ben10_pc_menu::window.load();
    HideSystemCursor(window, Draw(io, window));
  }

  bool Draw(ImGuiIO& io, rex::ui::Window* window) {
    const bool in_menu = ben10_pc_video::visible.load() || ben10_pc_video::music_overlay.load() ||
        ben10_pc_menu::pause_menu_active.load() ||
        ben10_pc_menu::menu_mouse::Active() ||
        (tracks_missions_ && !ben10_pc_menu::mission_active.load());
    if (!in_menu || cinematic_player::Playing() || !window) return false;
    const auto handle = static_cast<HWND>(window->GetNativeWindowHandle());
    if (GetForegroundWindow() != handle) return false;
    POINT cursor{};
    RECT client{};
    if (!GetCursorPos(&cursor) || !ScreenToClient(handle, &cursor) ||
        !GetClientRect(handle, &client) || !PtInRect(&client, cursor)) return false;
    // Play as Albedo swaps the green Omnitrix accents for his red ones.
    const auto sprite = ben10::albedo_hud::enabled.load(std::memory_order_relaxed) ? albedo_sprite_ : sprite_;
    ImFontAtlasRect texture{};
    if (!io.Fonts->GetCustomRect(sprite, &texture)) return false;
    const ImVec2 position(cursor.x * io.DisplaySize.x / client.right,
                          cursor.y * io.DisplaySize.y / client.bottom);
    const float size = std::clamp(io.DisplaySize.y / 18.0f, 28.0f, 64.0f);
    ImGui::GetForegroundDrawList()->AddImage(io.Fonts->TexRef, position,
        ImVec2(position.x + size, position.y + size), texture.uv0, texture.uv1);
    return true;
  }

  // SDL restores the arrow on every mouse move, so hide it through the
  // window's own visibility state rather than per-message SetCursor calls.
  void HideSystemCursor(rex::ui::Window* window, bool hidden) {
    if (!window || hidden == system_cursor_hidden_) return;
    system_cursor_hidden_ = hidden;
    window->app_context().CallInUIThreadDeferred([window, hidden] {
      using Visibility = rex::ui::Window::CursorVisibility;
      if (hidden) window->SetCursorVisibility(Visibility::kHidden);
      // Gameplay mouse look owns the cursor once it captures.
      else if (!rex::input::mnk::IsMouseLookActive()) window->SetCursorVisibility(Visibility::kVisible);
    });
  }

  ImFontAtlasRectId sprite_;
  ImFontAtlasRectId albedo_sprite_;
  bool tracks_missions_;
  bool system_cursor_hidden_ = false;
};
}
