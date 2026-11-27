#pragma once
#include "ucb_screen_flash_state.h"
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace ben10::ucb_screen_flash {
class Flash final : public rex::ui::ImGuiDialog {
public:
    explicit Flash(rex::ui::ImGuiDrawer* drawer):ImGuiDialog(drawer){}
    bool NeedsContinuousRepaint() override {return Alpha()>0;}
private:
    struct Quad { ImVec2 lo, hi; std::array<float,4> mask; };
    ImVec2 cached_size_{};
    std::vector<Quad> quads_;
    void RebuildMask(ImVec2 size) {
        cached_size_=size;
        quads_.clear();
        // The guest HUD is already composited into the presented frame. Keep
        // its exact display-space footprint out of the host flash, feathering
        // only the adjacent scene so there are no hard rectangular borders.
        const float scale=std::min(size.x/1280.f,size.y/720.f);
        const float ox=(size.x-1280.f*scale)*.5f,oy=(size.y-720.f*scale)*.5f;
        auto coverage=[&](float x,float y){
            const float gx=(x-ox)/scale,gy=(y-oy)/scale;
            const float dial=std::hypot((gx-192.4f)/65.f,(gy-107.9f)/56.f);
            const float px=std::max({736.f-gx,0.f,gx-1048.f});
            const float py=std::max({57.f-gy,0.f,gy-129.f});
            const float banner=std::hypot(px,py);
            const float t=std::clamp(std::min((dial-1.f)*56.f,banner)/16.f,0.f,1.f);
            return t*t*(3.f-2.f*t);
        };
        // Keep the original 128x72 mask samples and feathered edge triangles.
        // Fully transparent cells need no geometry; contiguous solid cells
        // can be represented by one rectangle, with identical interpolation.
        // Compute this only when the viewport changes, not on every flash frame.
        constexpr int nx=128,ny=72;
        std::array<std::array<float,nx+1>,ny+1> samples{};
        std::array<std::array<bool,nx>,ny> solid{}, used{};
        auto x=[&](int i){return size.x*i/nx;};
        auto y=[&](int j){return size.y*j/ny;};
        for(int j=0;j<=ny;++j)for(int i=0;i<=nx;++i)
            samples[j][i]=coverage(x(i),y(j));
        auto corners=[&](int i,int j){return std::array<float,4>{samples[j][i],samples[j][i+1],samples[j+1][i+1],samples[j+1][i]};};
        for(int j=0;j<ny;++j)for(int i=0;i<nx;++i){
            const auto c=corners(i,j);
            solid[j][i]=std::all_of(c.begin(),c.end(),[](float v){return v==1.f;});
        }
        for(int j=0;j<ny;++j)for(int i=0;i<nx;++i){
            if(used[j][i])continue;
            const auto c=corners(i,j);
            if(std::all_of(c.begin(),c.end(),[](float v){return v==0.f;}))continue;
            int right=i+1,bottom=j+1;
            if(solid[j][i]){
                while(right<nx && solid[j][right] && !used[j][right])++right;
                while(bottom<ny){
                    bool full=true;
                    for(int k=i;k<right;++k)if(!solid[bottom][k] || used[bottom][k]){full=false;break;}
                    if(!full)break;
                    ++bottom;
                }
                for(int row=j;row<bottom;++row)for(int k=i;k<right;++k)used[row][k]=true;
            }
            quads_.push_back({ImVec2(x(i),y(j)),ImVec2(x(right),y(bottom)),c});
        }
    }
    void OnDraw(ImGuiIO& io) override {
        if(io.DisplaySize.x<=0 || io.DisplaySize.y<=0)return;
        if(cached_size_.x!=io.DisplaySize.x || cached_size_.y!=io.DisplaySize.y)RebuildMask(io.DisplaySize);
        const float a=Alpha();
        if(a<=0)return;
        auto* draw=ImGui::GetBackgroundDrawList();
        auto color=[a](float mask){return IM_COL32(247,252,255,static_cast<int>(a*mask*255+.5f));};
        for(const auto& q:quads_)
            draw->AddRectFilledMultiColor(q.lo,q.hi,color(q.mask[0]),color(q.mask[1]),color(q.mask[2]),color(q.mask[3]));
    }
};
}
