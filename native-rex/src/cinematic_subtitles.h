#pragma once

#include "cinematic_player.h"
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>
#include <string>

class Ben10CinematicSubtitles final : public rex::ui::ImGuiDialog {
public:
    explicit Ben10CinematicSubtitles(rex::ui::ImGuiDrawer* drawer) : ImGuiDialog(drawer) {}
    bool NeedsContinuousRepaint() override { return false; }
protected:
    void OnDraw(ImGuiIO& io) override {
        const auto text = ben10::cinematic_player::CurrentSubtitle();
        if (text.empty()) return;
        const float font_size = io.DisplaySize.y * .029f;
        auto* font = ImGui::GetFont();
        const float wrap_width = io.DisplaySize.x * .8f;
        const auto size = font->CalcTextSizeA(font_size, 100000, wrap_width, text.c_str());
        const float x = (io.DisplaySize.x - size.x) * .5f;
        const float y = io.DisplaySize.y * .91f - size.y;
        auto* draw = ImGui::GetForegroundDrawList();
        draw->AddRectFilled(ImVec2(x-12,y-6), ImVec2(x+size.x+12,y+size.y+6),
                            IM_COL32(0,0,0,205), 4);
        draw->AddText(font, font_size, ImVec2(x,y), IM_COL32_WHITE, text.c_str(),
                      nullptr, wrap_width);
    }
};
