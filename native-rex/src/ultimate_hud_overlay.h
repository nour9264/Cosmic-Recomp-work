#pragma once
// Ultimate HUD prongs: while an Ultimate form is active, four dark Ultimatrix
// prongs extend diagonally from behind the circular HUD dial. They start at
// the dial's outer edge, so the original dial art stays untouched, and they
// appear only on frames where the game drew that dial.
#include "frame_metrics.h"
#include "ultimate_hud_palette.h"
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>
#include <algorithm>
#include <array>
#include <cmath>

namespace ben10::ultimate_hud {
class Prongs final : public rex::ui::ImGuiDialog {
 public:
  explicit Prongs(rex::ui::ImGuiDrawer* drawer) : ImGuiDialog(drawer) {}
  bool NeedsContinuousRepaint() override { return Active(); }

 private:
  // The dial in 1280x720 game space: centre and outer radii.
  static constexpr float kCenterX = 192.4f, kCenterY = 107.9f;
  static constexpr float kRadiusX = 62.0f, kRadiusY = 53.0f;
  // Prong length beyond the dial edge, and its width.
  static constexpr float kLength = 31.0f, kWidth = 18.0f;

  void OnDraw(ImGuiIO& io) override {
    if (!Active()) return;
    if (Ben10SubmittedFrames() > dial_frame.load(std::memory_order_relaxed) + 2) return;
    const float scale = std::min(io.DisplaySize.x / 1280.0f, io.DisplaySize.y / 720.0f);
    if (scale <= 0) return;
    const ImVec2 origin((io.DisplaySize.x - 1280 * scale) * .5f, (io.DisplaySize.y - 720 * scale) * .5f);
    auto* draw = ImGui::GetBackgroundDrawList();
    // Prong rectangles are laid out in the dial's circular space, then
    // squashed vertically like the dial art.
    const float squash = kRadiusY / kRadiusX;
    for (const float degrees : {-135.0f, -45.0f, 45.0f, 135.0f}) {
      const float angle = degrees * 3.14159265f / 180.0f;
      const float c = std::cos(angle), s = std::sin(angle);
      auto point = [&](float along, float across, float dx = 0, float dy = 0) {
        const float x = along * c - across * s, y = (along * s + across * c) * squash;
        return ImVec2(origin.x + (kCenterX + x + dx) * scale, origin.y + (kCenterY + y + dy) * scale);
      };
      // The dial end follows the dial's outer edge, so the prongs never cover
      // the ring or the meters' tips and read as passing behind the dial.
      auto shape = [&](float inset, float edge, float dx = 0, float dy = 0) {
        const float w = kWidth * .5f - inset, x1 = kRadiusX + kLength - inset;
        auto inner = [&](float across) { return std::sqrt(edge * edge - across * across) + inset; };
        std::array<ImVec2, 12> points{point(inner(-w), -w, dx, dy), point(x1, -w, dx, dy),
                                      point(x1, w, dx, dy), point(inner(w), w, dx, dy)};
        for (int i = 1; i <= 8; ++i) {
          const float across = w - 2 * w * i / 9.0f;
          points[3 + i] = point(inner(across), across, dx, dy);
        }
        return points;
      };
      const float edge = kRadiusX + 0.5f;
      const auto shadow = shape(0, edge + 1.5f, 2, 3);
      draw->AddConcavePolyFilled(shadow.data(), int(shadow.size()), IM_COL32(0, 0, 0, 90));
      const auto body = shape(0, edge);
      draw->AddConcavePolyFilled(body.data(), int(body.size()), IM_COL32(52, 55, 61, 255));
      // Outlines stay open at the dial end so no line crosses the dial edge.
      const auto rim = shape(2.6f, edge);
      draw->AddPolyline(rim.data(), 4, IM_COL32(128, 134, 143, 255), ImDrawFlags_None, 1.6f * scale);
      draw->AddPolyline(body.data(), 4, IM_COL32(14, 14, 16, 255), ImDrawFlags_None, 2.4f * scale);
    }
  }
};
}
