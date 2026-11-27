#pragma once
#include <atomic>
#include <algorithm>
#include <array>
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>
#include "ultimate_hud_palette.h"
#include "ben_upgrade_arc.h"
namespace ben10::upgrade_frame {
inline std::atomic<bool> ready{false},enabled{false};
inline std::atomic<unsigned> health{0},energy{0};
class Art final:public rex::ui::ImGuiDialog {
 public:
 Art(rex::ui::ImGuiDrawer* drawer,std::array<ImFontAtlasRectId,16> frames):ImGuiDialog(drawer),frames_(frames){}
 bool NeedsContinuousRepaint() override{return Visible();}
 private:
 bool Visible() const {return enabled.load(std::memory_order_relaxed) &&
   Ben10SubmittedFrames()<=ben10::ultimate_hud::dial_frame.load(std::memory_order_relaxed)+2;}
 void OnDraw(ImGuiIO& io) override {
  if(!Visible())return;
  const auto h=std::min(3u,health.load()),e=std::min(3u,energy.load());
  ImFontAtlasRect rect;if(!io.Fonts->GetCustomRect(frames_[h*4+e],&rect))return;
  const float scale=std::min(io.DisplaySize.x/1280.f,io.DisplaySize.y/720.f);
  const ImVec2 origin((io.DisplaySize.x-1280*scale)*.5f,(io.DisplaySize.y-720*scale)*.5f);
  const ImVec2 a(origin.x+129*scale,origin.y+45*scale),b(a.x+126*scale,a.y+126*scale);
  auto* draw=ImGui::GetBackgroundDrawList();
  const auto track_flags=draw->Flags;draw->Flags&=~ImDrawListFlags_AntiAliasedFill;
  // The stock empty-track quarter sprite stops at the original endpoints.
  // Extend only the unfilled area, leaving the native animated fill visible.
  for(int side=0;side<2;++side) {
    const unsigned tier=side?e:h;if(!tier)continue;
    const float fill=ben10::upgrade_arc::Fraction(side?ben10::upgrade_arc::energy_fill.load():ben10::upgrade_arc::health_fill.load());
    int count=int(fill*66);if(count&1)++count;
    const float filled=count>2?std::min(1.f,float(count/2-1)/32.f):0.f;
    const float extent=53.f+8.f*tier+2.f;
    const float start=side?-extent:180.f+extent,end=side?extent:180.f-extent;
    const float begin=start+(end-start)*filled;
    // Guest HUD coordinates have positive Y upwards; ImGui has positive Y downwards.
    const auto ringpoint=[&](float angle,float radius){angle*=3.14159265359f/180.f;return ImVec2(origin.x+(192+std::cos(angle)*radius)*scale,origin.y+(108-std::sin(angle)*radius)*scale);};
    const ImU32 green=IM_COL32(13,57,28,255);
    for(int step=0;step<64 && filled<1.f;++step) {
      const float x=begin+(end-begin)*step/64.f,y=begin+(end-begin)*(step+1)/64.f;
      const ImVec2 strip[]={ringpoint(x,56.4f),ringpoint(y,56.4f),ringpoint(y,40.9f),ringpoint(x,40.9f)};
      draw->AddConvexPolyFilled(strip,4,green);
    }
  }
  draw->Flags=track_flags;
  draw->AddImage(io.Fonts->TexRef,a,b,rect.uv0,rect.uv1);
 }
 std::array<ImFontAtlasRectId,16> frames_;
};
}
