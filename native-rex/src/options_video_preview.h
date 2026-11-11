#pragma once

#include "pc_menu_bridge.h"
#include "keyboard_mouse_runtime.h"
#include "fov_runtime.h"
#include "music_session.h"

namespace ben10_options {
inline std::atomic<bool> mouse_captured{false};
class VideoPage final : public rex::ui::ImGuiDialog {
 public:
  VideoPage(rex::ui::ImGuiDrawer* drawer, ImFont* font, std::array<ImFontAtlasRectId,2> badges)
      : ImGuiDialog(drawer), font_(font), badges_(badges) {}

  bool NeedsContinuousRepaint() override { return ben10_pc_video::CapturesGameInput(); }

 private:
  struct Row {
    const char* name;
    const char* key;
    const char* values[5];
    const char* labels[5];
    int count;
  };
  static constexpr Row rows_[]={
    {"Output Resolution","resolution",{"720p","1080p","1440p","4k"},{"1280 x 720","1920 x 1080","2560 x 1440","3840 x 2160"},4},
    {"Frame Limit","frame_limit",{"30","60","120","unlimited"},{"30 FPS","60 FPS","120 FPS","Unlimited"},4},
    {"Show FPS","performance_overlay",{"on","off"},{"On","Off"},2},
    {"Display Mode","display_mode",{"windowed","borderless","exclusive"},{"Windowed","Borderless","Exclusive"},3},
    {"Button Icons","button_icons",{"xbox","playstation","keyboard","auto"},{"Xbox","PlayStation","Keyboard and Mouse","Auto"},4},
    {"Internal Resolution",nullptr,{},{"Original","Native (1x)","2x"},3},
    {"Anti-Aliasing",nullptr,{},{"Original","Off","FXAA","FXAA Extreme"},4},
    {"Texture Filtering",nullptr,{},{"Original","2x","4x","8x","16x"},5},
    {"Sharpening",nullptr,{},{"Original","Low","Medium","High"},4},
    {"Screen Bloom",nullptr,{},{"Original","Low","Medium","High"},4},
    {"Game Monitor",nullptr,{}, {},0},
  };
  static constexpr int count_=int(std::size(rows_));
  static constexpr const char* gameplay_rows_[]={
      "Invert Up / Down","Invert Left / Right","Vibration",
      "All Aliens","Hero Time (L3)","Play as Albedo","Background Controller Input",
      "Customize Keyboard and Mouse Controls","Wipe Data","Field of View"};
  static constexpr const char* sound_rows_[]={"Music Volume","SFX Volume","Voice Volume",
      "Music Integration","Music Overlay Shortcut"};
  // Rows before kVolumeRows are the game's own volumes (script snapshot);
  // the music rows after them are saved directly to pc-sound.ini.
  // Detection and ducking follow Music Integration. Music Priority is set in the
  // gameplay music overlay only.
  static constexpr int kVolumeRows=3, kIntegrationRow=3, kShortcutRow=4;
  // Rows before controls_row_ mirror script switches; Field of View is ours, saved directly.
  static constexpr int fov_row_=int(std::size(gameplay_rows_))-1;
  static constexpr int wipe_row_=fov_row_-1;
  static constexpr int controls_row_=wipe_row_-1;
  int selected_=0;
  bool confirm_wipe_=false;
  int current_page_=-1;
  int hub_selection_=0;
  std::array<int,count_> values_{}, saved_{};
  uint16_t last_buttons_=0;
  bool loaded_=false;
  bool display_busy_=false;
  ImFont* font_;
  std::array<ImFontAtlasRectId,2> badges_;
  std::vector<ben10::monitors::Monitor> monitors_;
  ben10::controls::Editor controls_editor_;

  void Read(const std::filesystem::path& path) {
    using namespace ben10_pc_menu;
    for(int i=0;i<5;++i) {
      const auto& row=rows_[i];
      const auto value=ReadVideoSetting(path,row.key,row.values[0]);
      values_[i]=0;
      for(int j=0;j<row.count;++j)if(value==row.values[j])values_[i]=j;
    }
    values_[5]=GraphicsChoice<0>(path);
    values_[6]=GraphicsChoice<1>(path);
    values_[7]=GraphicsChoice<2>(path);
    values_[8]=GraphicsChoice<3>(path);
    values_[9]=GraphicsChoice<4>(path);
    monitors_=ben10::monitors::Enumerate();
    std::string monitor;
    std::ifstream file(path.parent_path()/"monitor.txt");
    std::getline(file,monitor);
    values_[10]=ben10::monitors::Find(monitors_,monitor);
  }

  void Apply() {
    using namespace ben10_pc_menu;
    using Icons=ben10::albedo_textures::ButtonIcons;
    auto* active=window.load();
    if(!active || values_==saved_ || display_busy_)return;
    display_busy_=true;
    const auto monitor=monitors_[values_[10]].id;
    if(!active->app_context().CallInUIThreadDeferred([this,values=values_,saved=saved_,monitor] {
      auto* host=runtime.load();auto* active=window.load();
      if(!host || !active)return;
      const auto path=host->user_data_root()/"pc-video.ini";
      try {
        if(values[0]!=saved[0] || values[3]!=saved[3] || values[10]!=saved[10]) {
          std::lock_guard guard(video_settings_mutex);
          if(values[3]!=saved[3] || values[3]!=1 || values[10]!=saved[10])
            ApplyPresentation(active,values[3],values[0],&monitor);
          auto target=path.parent_path()/"monitor.txt";
          auto temporary=target;temporary+=L".presentation.tmp";
          {std::ofstream file(temporary,std::ios::binary|std::ios::trunc);
           file<<monitor;file.close();
           if(!file)throw std::runtime_error("Could not save monitor selection");}
          if(!MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
            throw std::runtime_error("Could not commit monitor selection");
          SaveVideoKey(path,"resolution",rows_[0].values[values[0]]);
          SaveVideoKey(path,"display_mode",rows_[3].values[values[3]]);
        }
        PPCContext context{};
        context.r4.s32=-1;
        static constexpr PPCFunc* rates[]={SetVideo<-1,30>,SetVideo<-1,60>,SetVideo<-1,120>,SetVideo<-1,0>};
        static constexpr PPCFunc* fps[]={SetPerformanceOverlay<true>,SetPerformanceOverlay<false>};
        static constexpr PPCFunc* icons[]={SetButtonIcons<Icons::Xbox>,SetButtonIcons<Icons::PlayStation>,
            SetButtonIcons<Icons::Keyboard>,SetButtonIcons<Icons::Auto>};
        if(values[1]!=saved[1])rates[values[1]](context,nullptr);
        if(values[2]!=saved[2])fps[values[2]](context,nullptr);
        if(values[4]!=saved[4])icons[values[4]](context,nullptr);
        for(int i=5;i<10;++i)if(values[i]!=saved[i]) {
          const auto& setting=GraphicsSettings[i-5];
          std::lock_guard guard(video_settings_mutex);
          SaveVideoKey(path,setting.key,setting.values[values[i]]);
        }
      }catch(const std::exception& error){REXLOG_ERROR("Cosmic preview settings failed: {}",error.what());}
      Read(path);
      saved_=values_;
      display_busy_=false;
      REXLOG_INFO("Cosmic Options preview: Apply completed");
    }))display_busy_=false;
  }

  void SyncMusic() {
    const auto music=ben10::music::CurrentSettings();
    values_[kIntegrationRow]=saved_[kIntegrationRow]=music.integration;
  }

  void Change(int direction) {
    if(display_busy_)return;
    if(ben10_pc_menu::gameplay_preview::active.load()) {
      if(selected_==fov_row_ && !confirm_wipe_) {
        // Applies immediately and saves to the file the launcher also uses.
        const int degrees=ben10::fov::Clamp(values_[fov_row_]+direction);
        values_[fov_row_]=saved_[fov_row_]=degrees;
        ben10::fov::offset=degrees;
        if(auto* host=ben10_pc_menu::runtime.load())
          ben10::fov::Save(host->user_data_root()/"pc-gameplay.ini",degrees);
        return;
      }
      if(!confirm_wipe_ && selected_<controls_row_ && !ben10_pc_menu::gameplay_preview::pending.load())
        values_[selected_]^=1;
      return;
    }
    if(ben10_pc_menu::sound_preview::active.load()) {
      if(selected_>=kVolumeRows) {
        auto music=ben10::music::CurrentSettings();
        if(selected_==kIntegrationRow)music.integration=!music.integration;
        if(selected_==kShortcutRow)return;
        ben10::music::UpdateSettings(music);  // Applies immediately and saves.
        SyncMusic();
        return;
      }
      values_[selected_]=std::clamp(values_[selected_]+direction,0,int(ben10_pc_menu::sound_preview::step_count));
      return;
    }
    const int n=selected_==10?int(monitors_.size()):rows_[selected_].count;
    values_[selected_]=(values_[selected_]+direction+n)%n;
  }

  void OnDraw(ImGuiIO& io) override {
    using namespace ben10_pc_video;
    mouse_captured.store(io.WantCaptureMouse,std::memory_order_relaxed);
    if(!CapturesGameInput())return;
    auto* host=ben10_pc_menu::runtime.load();
    if(!host)return;
    if(controls_editor_.open) {
      mouse_captured=true;
      controls_editor_.Draw(host->user_data_root(),ben10::controls::Apply);
      if(!controls_editor_.open) {
        opening_guard=true;
        last_buttons_=0;
      }
      return;
    }
    const auto sample=controller_sample.load(std::memory_order_relaxed);
    const uint16_t buttons=uint16_t(sample);
    const ImGuiKey menu_keys[]={ImGuiKey_Escape,ImGuiKey_Backspace,ImGuiKey_Enter,ImGuiKey_Space,
        ImGuiKey_UpArrow,ImGuiKey_DownArrow,ImGuiKey_LeftArrow,ImGuiKey_RightArrow};
    bool key_down=false;
    for(auto key:menu_keys)key_down|=ImGui::IsKeyDown(key);
    if((sample&sample_valid) && !buttons && !key_down){opening_guard=false;release_guard=false;}
    if(!visible){loaded_=false;return;}
    const auto path=host->user_data_root()/"pc-video.ini";
    namespace gameplay=ben10_pc_menu::gameplay_preview;
    const bool is_gameplay=gameplay::active.load();
    namespace sound=ben10_pc_menu::sound_preview;
    const bool is_sound=sound::active.load();
    namespace hub=ben10_pc_menu::options_hub;
    const bool is_hub=hub::active.load();
    const int page=is_hub?3:is_sound?2:is_gameplay?1:0;
    const int row_count=is_hub?(hub::credits.load()?4:3):is_sound?int(std::size(sound_rows_)):is_gameplay?int(std::size(gameplay_rows_)):count_;
    const auto sync_sound=[&] {
      const auto bits=sound::snapshot.load();
      for(int i=0;i<kVolumeRows;++i)values_[i]=int((bits>>(i*5))&31u);
      saved_=values_;
      SyncMusic();
    };
    const auto sync_gameplay=[&] {
      const auto bits=gameplay::snapshot.load();
      for(int i=0;i<controls_row_;++i)values_[i]=int((bits>>i)&1u);
      values_[fov_row_]=ben10::fov::offset.load();
      saved_=values_;
    };
    if(!loaded_ || page!=current_page_) {
      current_page_=page;
      if(is_hub)selected_=std::min(hub_selection_,row_count-1);
      else if(is_sound)sync_sound();
      else if(is_gameplay)sync_gameplay();
      else {Read(path);saved_=values_;}
      if(!is_hub)selected_=0;
      confirm_wipe_=false;
      loaded_=true;
      REXLOG_INFO("Cosmic Options preview: {} opened",is_hub?"Options":is_sound?"Sound":is_gameplay?"Gameplay":"Video");
    }
    if(is_gameplay && display_busy_ && !gameplay::pending.load()) {
      sync_gameplay();
      display_busy_=false;
    }
    if(is_sound && display_busy_ && !sound::pending.load()) {
      sync_sound();
      display_busy_=false;
    }
    const uint16_t pressed=opening_guard?0:uint16_t(buttons & ~last_buttons_);
    last_buttons_=buttons;
    auto key=[&](ImGuiKey code){return !opening_guard && ImGui::IsKeyPressed(code,false);};
    if(!confirm_wipe_ && ((pressed&1) || key(ImGuiKey_UpArrow)))selected_=(selected_+row_count-1)%row_count;
    if(!confirm_wipe_ && ((pressed&2) || key(ImGuiKey_DownArrow)))selected_=(selected_+1)%row_count;
    if((pressed&4) || key(ImGuiKey_LeftArrow)) {
      if(is_hub)selected_=(selected_+row_count-1)%row_count; else Change(-1);
    }
    if((pressed&8) || key(ImGuiKey_RightArrow)) {
      if(is_hub)selected_=(selected_+1)%row_count; else Change(1);
    }
    bool close=(pressed&0x2000) || key(ImGuiKey_Escape) || key(ImGuiKey_Backspace);

    const bool albedo=ben10::albedo_hud::enabled.load();
    const ImU32 accent=albedo?IM_COL32(255,59,57,255):IM_COL32(151,235,40,255);
    const ImU32 line=albedo?IM_COL32(151,36,34,255):IM_COL32(77,139,25,255);
    const ImU32 panel=albedo?IM_COL32(30,10,11,255):IM_COL32(13,28,12,255);
    const auto theme=[albedo](ImU32 ben,ImU32 red){return albedo?red:ben;};
    const ImU32 selected=theme(IM_COL32(163,248,50,255),IM_COL32(255,110,104,255));
    const ImU32 white=IM_COL32(239,250,230,255);
    const float scale=std::min(io.DisplaySize.x/1280.0f,io.DisplaySize.y/720.0f);
    if(scale<=0)return;
    const ImVec2 origin((io.DisplaySize.x-1280*scale)*.5f,(io.DisplaySize.y-720*scale)*.5f);
    auto point=[&](float x,float y){return ImVec2(origin.x+x*scale,origin.y+y*scale);};
    ImGui::SetNextWindowPos(ImVec2(0,0),ImGuiCond_Always);
    ImGui::SetNextWindowSize(io.DisplaySize,ImGuiCond_Always);
    ImGui::PushStyleColor(ImGuiCol_WindowBg,albedo?ImVec4(.021f,.014f,.015f,1):ImVec4(.014f,.021f,.015f,1));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding,ImVec2(0,0));
    if(font_)ImGui::PushFont(font_);
    if(ImGui::Begin("Cosmic Options",nullptr,ImGuiWindowFlags_NoDecoration|ImGuiWindowFlags_NoSavedSettings|
        ImGuiWindowFlags_NoNav|ImGuiWindowFlags_NoScrollbar|ImGuiWindowFlags_NoScrollWithMouse)){
      auto* draw=ImGui::GetWindowDrawList();
      const auto draw_flags=draw->Flags;
      draw->Flags|=ImDrawListFlags_AntiAliasedFill|ImDrawListFlags_AntiAliasedLines;
      auto polygon=[&](float x,float y,float w,float h,float cut,ImU32 fill,ImU32 edge,float thickness){
        const ImVec2 path[]={point(x+cut,y),point(x+w,y),point(x+w,y+h-cut),
          point(x+w-cut,y+h),point(x,y+h),point(x,y+cut)};
        draw->AddConvexPolyFilled(path,6,fill);
        draw->AddPolyline(path,6,edge,ImDrawFlags_Closed,thickness*scale);
      };
      // The SDK uploads the legacy font atlas once. Requesting new font
      // sizes during a draw can rebuild that atlas while the presenter uses it.
      auto label=[&](const char* value,float size,float x,float y,ImU32 color,bool centered=false){
        const auto extent=ImGui::CalcTextSize(value);
        if(extent.y<=0)return;
        const float stretch=size*scale/extent.y;
        const auto pos=point(x,y);
        const float left=pos.x-(centered?extent.x*stretch*.5f:0.0f);
        const int first=draw->VtxBuffer.Size;
        draw->AddText(pos,color,value);
        // Transform the existing glyph quads. The atlas stays at its baked size.
        for(int i=first;i<draw->VtxBuffer.Size;++i) {
          auto& vertex=draw->VtxBuffer[i];
          const float dy=(vertex.pos.y-pos.y)*stretch;
          vertex.pos.x=left+(vertex.pos.x-pos.x)*stretch;
          vertex.pos.y=pos.y+dy;
        }
      };
      // Hovering a row or tile selects it, like the stock menus; only an actual
      // mouse movement does, so a resting cursor never fights the pad.
      const bool mouse_moved=io.MouseDelta.x!=0 || io.MouseDelta.y!=0;
      auto hit=[&](const char* id,float x,float y,float w,float h,int row=-1){
        ImGui::SetCursorScreenPos(point(x,y));
        const bool clicked=ImGui::InvisibleButton(id,ImVec2(w*scale,h*scale));
        if(row>=0 && mouse_moved && !confirm_wipe_ && ImGui::IsItemHovered())selected_=row;
        return clicked;
      };
      auto triangle=[&](float x,float y,float sign,ImU32 color){
        draw->AddTriangleFilled(point(x+sign*5,y),point(x-sign*3,y-6),point(x-sign*3,y+6),color);
      };

      draw->AddRectFilledMultiColor(point(0,0),point(1280,720),
          theme(IM_COL32(4,10,4,255),IM_COL32(10,4,4,255)),theme(IM_COL32(4,8,4,255),IM_COL32(8,4,4,255)),theme(IM_COL32(18,39,9,255),IM_COL32(39,12,12,255)),theme(IM_COL32(7,19,5,255),IM_COL32(19,6,7,255)));
      for(float radius:{232.0f,259.0f,291.0f,328.0f})
        draw->AddCircle(point(640,410),radius*scale,theme(IM_COL32(86,147,38,39),IM_COL32(170,44,40,39)),64,3*scale);
      const ImVec2 watermark[]={point(430,214),point(850,214),point(670,410),
          point(850,606),point(430,606),point(610,410)};
      draw->AddPolyline(watermark,6,theme(IM_COL32(126,181,46,29),IM_COL32(201,52,48,29)),ImDrawFlags_Closed,5*scale);

      polygon(112,129,1056,468,34,theme(IM_COL32(10,16,8,255),IM_COL32(16,8,8,255)),theme(IM_COL32(105,170,38,77),IM_COL32(181,49,43,77)),8);
      polygon(123,139,1034,445,28,theme(IM_COL32(8,14,8,255),IM_COL32(14,8,8,255)),accent,2);
      draw->AddRectFilledMultiColor(point(141,144),point(1127,581),
          theme(IM_COL32(54,97,16,38),IM_COL32(97,24,22,38)),theme(IM_COL32(78,128,31,57),IM_COL32(128,33,29,57)),theme(IM_COL32(2,8,3,180),IM_COL32(8,2,3,180)),theme(IM_COL32(2,8,3,180),IM_COL32(8,2,3,180)));
      polygon(135,49,987,76,26,panel,accent,2);
      draw->AddRectFilledMultiColor(point(176,53),point(1088,116),
          theme(IM_COL32(142,217,44,105),IM_COL32(217,64,55,105)),theme(IM_COL32(76,147,28,42),IM_COL32(147,34,29,42)),theme(IM_COL32(8,11,5,180),IM_COL32(11,5,5,180)),theme(IM_COL32(8,11,5,180),IM_COL32(11,5,5,180)));
      draw->AddLine(point(181,125),point(1086,125),accent,3*scale);
      draw->AddLine(point(124,177),point(124,553),selected,5*scale);
      draw->AddLine(point(1156,176),point(1156,543),accent,5*scale);
      for(int i=0;i<24;++i) {
        const float y=190+i*15.0f;
        draw->AddLine(point(112,y),point(i%4==0?124.0f:119.0f,y),line,scale);
      }
      ImFontAtlasRect badge;
      if(io.Fonts->GetCustomRect(badges_[albedo?1:0],&badge))
        draw->AddImage(io.Fonts->TexRef,point(87,31),point(197,141),badge.uv0,badge.uv1);
      label(is_hub?"OPTIONS":is_sound?"SOUND":is_gameplay?"GAMEPLAY":"VIDEO",45,is_hub?239.0f:642.0f,64,white,!is_hub);
      bool tile_clicked=false;
      if(is_hub) {
        static constexpr const char* tiles[]={"GAMEPLAY","SOUND","VIDEO","CREDITS"};
        const float width=row_count==4?211.0f:230.0f;
        const float gap=18.0f;
        const float left=(1280-width*row_count-gap*(row_count-1))*.5f;
        for(int i=0;i<row_count;++i) {
          const float x=left+i*(width+gap), y=241, cx=x+width*.5f, cy=y+79;
          ImGui::PushID(i);
          if(hit("tile",x,y,width,213,i)){selected_=i;tile_clicked=true;}
          ImGui::PopID();
          const bool focused=i==selected_;
          if(focused)polygon(x-5,y-5,width+10,223,25,panel,theme(IM_COL32(110,205,18,75),IM_COL32(239,40,30,75)),10);
          polygon(x,y,width,213,22,panel,focused?selected:accent,focused?3:1.5f);
          polygon(x+8,y+8,width-16,197,16,panel,line,1);
          draw->AddLine(point(x+width-46,y+12),point(x+width-16,y+12),accent,3*scale);
          draw->AddLine(point(x+18,y+200),point(x+48,y+200),accent,3*scale);
          const auto ink=focused?selected:accent;
          if(i==0) {
            draw->AddRectFilled(point(cx-42,cy-23),point(cx+42,cy+22),ink,15*scale);
            draw->AddRectFilled(point(cx-32,cy-13),point(cx-13,cy-5),panel);
            draw->AddRectFilled(point(cx-26,cy-19),point(cx-19,cy+1),panel);
            for(int j=0;j<4;++j) {
              const float dx=j%2?8.0f:-8.0f,dy=j/2?8.0f:-8.0f;
              draw->AddCircleFilled(point(cx+22+dx,cy+dy),4*scale,panel);
            }
          } else if(i==1) {
            draw->AddRectFilled(point(cx-37,cy-12),point(cx-23,cy+12),ink,2*scale);
            const ImVec2 speaker[]={point(cx-21,cy-12),point(cx+1,cy-26),
                point(cx+1,cy+26),point(cx-21,cy+12)};
            draw->AddConvexPolyFilled(speaker,4,ink);
            for(float radius:{17.0f,30.0f}) {
              draw->PathArcTo(point(cx+1,cy),radius*scale,-.76f,.76f,14);
              draw->PathStroke(ink,0,4*scale);
            }
          } else if(i==2) {
            draw->AddRect(point(cx-40,cy-27),point(cx+40,cy+20),ink,3*scale,0,4*scale);
            draw->AddLine(point(cx,cy+20),point(cx,cy+31),ink,4*scale);
            draw->AddLine(point(cx-20,cy+31),point(cx+20,cy+31),ink,4*scale);
          } else {
            draw->AddRect(point(cx-38,cy-16),point(cx+38,cy+27),ink,2*scale,0,4*scale);
            draw->AddLine(point(cx-39,cy-18),point(cx+37,cy-33),ink,5*scale);
            draw->AddLine(point(cx-39,cy-18),point(cx+38,cy-18),ink,4*scale);
            draw->AddTriangleFilled(point(cx-7,cy-6),point(cx-7,cy+15),point(cx+12,cy+4),ink);
          }
          label(tiles[i],25,cx,y+150,white,true);
        }
      }
      for(int i=0;!is_hub && i<row_count;++i) {
        ImGui::PushID(i);
        const float y=is_sound?176+i*50.0f:is_gameplay?176+i*42.0f:154+i*39.0f;
        if(!confirm_wipe_ && hit("row",160,y,635,35,i)) {
          selected_=i;
          if(is_gameplay && i==controls_row_)controls_editor_.Open(host->user_data_root());
        }
        if(hit("previous",796,y,56,35,i)){selected_=i;Change(-1);}
        if(hit("next",1068,y,52,35,i)){selected_=i;Change(1);}
        const bool focused=i==selected_;
        if(focused && is_sound)polygon(153,y-2,974,39,13,theme(IM_COL32(76,140,12,115),IM_COL32(140,31,27,115)),theme(IM_COL32(155,246,49,115),IM_COL32(246,68,62,115)),5);
        else if(focused)polygon(153,y-2,974,39,13,theme(IM_COL32(77,139,25,100),IM_COL32(139,38,32,100)),theme(IM_COL32(149,245,48,80),IM_COL32(245,66,58,80)),5);
        if(is_sound)polygon(160,y,960,35,17,focused?theme(IM_COL32(28,66,6,255),IM_COL32(66,16,14,255)):panel,focused?theme(IM_COL32(169,255,56,255),IM_COL32(255,108,101,255)):line,focused?2:1);
        else polygon(160,y,960,35,12,focused?theme(IM_COL32(36,69,13,255),IM_COL32(69,19,17,255)):panel,focused?selected:line,focused?2:1);
        if(!is_sound)draw->AddRectFilledMultiColor(point(174,y+2),point(1106,y+32),
            focused?theme(IM_COL32(173,247,63,105),IM_COL32(247,89,78,105)):theme(IM_COL32(100,153,43,53),IM_COL32(153,43,40,53)),
            focused?theme(IM_COL32(115,210,38,76),IM_COL32(210,57,48,76)):theme(IM_COL32(73,122,24,45),IM_COL32(122,32,28,45)),
            theme(IM_COL32(3,11,4,160),IM_COL32(11,3,4,160)),theme(IM_COL32(5,14,4,169),IM_COL32(14,4,5,169)));
        const ImVec2 value_panel[]={point(818,y+2),point(1106,y+2),point(1106,y+32),point(791,y+32)};
        if(!is_sound)draw->AddConvexPolyFilled(value_panel,4,theme(IM_COL32(2,8,3,125),IM_COL32(8,2,3,125)));
        if(!is_sound)draw->AddLine(point(817,y+3),point(792,y+32),focused?selected:line,2*scale);
        if(!is_sound)draw->AddLine(point(177,y+33),point(784,y+33),focused?selected:line,scale);
        label(is_sound?sound_rows_[i]:is_gameplay?gameplay_rows_[i]:rows_[i].name,
            is_gameplay && i==controls_row_?19:23,187,y+5,white);
        if(is_sound && i>=kVolumeRows) {
          const std::string value=i==kShortcutRow?std::string("M  |  View / Share"):
std::string(values_[i]?"On":"Off");
          label(value.c_str(),i==kShortcutRow?17:21,960,y+7,focused?selected:white,true);
          if(i!=kShortcutRow) {
            triangle(826,y+18,-1,focused?selected:accent);
            triangle(1093,y+18,1,focused?selected:accent);
          }
        } else if(is_sound) {
          for(int segment=0;segment<8;++segment) {
            const float x=844+segment*23.0f;
            const ImVec2 bar[]={point(x+5,y+10),point(x+22,y+10),point(x+17,y+25),point(x,y+25)};
            const float fraction=std::clamp(values_[i]*8.0f/sound::step_count-segment,0.0f,1.0f);
            draw->AddConvexPolyFilled(bar,4,theme(IM_COL32(15,22,10,255),IM_COL32(31,12,11,255)));
            if(fraction>0) {
              const ImVec2 fill[]={bar[0],point(x+5+17*fraction,y+10),point(x+17*fraction,y+25),bar[3]};
              draw->AddConvexPolyFilled(fill,4,theme(IM_COL32(154,236,42,255),IM_COL32(236,66,59,255)));
            }
          }
          const auto percent=std::to_string(values_[i]*5)+"%";
          label(percent.c_str(),18,1058,y+9,white,true);
        } else if(is_gameplay && i==controls_row_) {
          label("OPEN",20,960,y+7,selected,true);
          if(hit("customize",796,y,324,35))controls_editor_.Open(host->user_data_root());
        } else if(is_gameplay && i==wipe_row_) {
          label(confirm_wipe_?"CONFIRM RESET":"RESET PROGRESS",20,960,y+7,selected,true);
        } else if(is_gameplay && i==fov_row_) {
          // Slider: the track spans -20..+30 degrees; drag or click it, or use the arrows.
          const float left=852,right=1062,track=y+28;
          const float fraction=float(values_[i]-ben10::fov::kMin)/float(ben10::fov::kMax-ben10::fov::kMin);
          draw->AddLine(point(left,track),point(right,track),line,3*scale);
          draw->AddLine(point(left,track),point(left+(right-left)*fraction,track),focused?selected:accent,3*scale);
          draw->AddCircleFilled(point(left+(right-left)*fraction,track),5*scale,focused?selected:accent);
          ImGui::SetCursorScreenPos(point(left,y+18));
          ImGui::InvisibleButton("fov_track",ImVec2((right-left)*scale,17*scale));
          if(ImGui::IsItemActive() && !confirm_wipe_) {
            selected_=i;
            const float at=std::clamp((io.MousePos.x-point(left,0).x)/((right-left)*scale),0.0f,1.0f);
            const int degrees=ben10::fov::kMin+int(std::lround(at*(ben10::fov::kMax-ben10::fov::kMin)));
            if(degrees!=values_[i])Change(degrees-values_[i]);
          }
          label(ben10::fov::Label(values_[i]).c_str(),18,960,y+1,focused?selected:white,true);
          triangle(826,y+18,-1,focused?selected:accent);
          triangle(1093,y+18,1,focused?selected:accent);
        } else {
          const char* value=is_gameplay?(values_[i]?"On":"Off"):
              i==10?monitors_[values_[i]].label.c_str():rows_[i].labels[values_[i]];
          label(value,!is_gameplay && i==10?15:23,960,y+5,focused?selected:white,true);
          triangle(826,y+18,-1,focused?selected:accent);
          triangle(1093,y+18,1,focused?selected:accent);
        }
        ImGui::PopID();
      }

      using Icons=ben10::albedo_textures::ButtonIcons;
      const auto icons=ben10::albedo_textures::button_icons.load(std::memory_order_relaxed);
      auto prompt=[&](bool confirm,float x,float y,float width) {
        const float cx=x+24, cy=y+20;
        // The page also accepts pad A/B, so show the keys bound to them, like the game prompts.
        ImFontAtlasRect keycap;
        const auto key=icons==Icons::Keyboard?
            ben10::controls::KeyIcon(confirm?"keybind_a":"keybind_b"):ImFontAtlasRectId_Invalid;
        if(key!=ImFontAtlasRectId_Invalid && io.Fonts->GetCustomRect(key,&keycap)) {
          draw->AddImage(io.Fonts->TexRef,point(cx-17,cy-17),point(cx+17,cy+17),keycap.uv0,keycap.uv1);
        } else if(icons==Icons::Keyboard) {
          draw->AddRect(point(cx-16,cy-10),point(cx+16,cy+10),white,3*scale,0,scale);
          label(confirm?"ENT":"ESC",12,cx,cy-6,white,true);
        } else {
          const bool ps=icons==Icons::PlayStation;
          const ImU32 color=confirm?(ps?IM_COL32(126,173,255,255):IM_COL32(163,248,50,255)):IM_COL32(255,114,125,255);
          draw->AddCircleFilled(point(cx,cy),12*scale,IM_COL32(7,13,16,255),32);
          draw->AddCircle(point(cx,cy),12*scale,color,32,scale);
          if(ps && confirm) {
            draw->AddLine(point(cx-4,cy-4),point(cx+4,cy+4),color,2*scale);
            draw->AddLine(point(cx-4,cy+4),point(cx+4,cy-4),color,2*scale);
          } else if(ps) {
            draw->AddCircle(point(cx,cy),5*scale,color,24,2*scale);
          } else {
            label(confirm?"A":"B",15,cx,cy-8,color,true);
          }
        }
        label(confirm?"SELECT":"BACK",22,x+(width+30)*.5f,y+9,white,true);
      };
      if(hit("back",130,621,165,41))close=true;
      polygon(130,621,165,41,10,panel,line,1);
      prompt(false,130,621,165);
      const bool confirm=tile_clicked || hit("apply",941,621,209,41) || (pressed&0x1000) ||
          key(ImGuiKey_Enter) || key(ImGuiKey_Space);
      polygon(941,621,209,41,10,panel,values_!=saved_?selected:line,2);
      prompt(true,941,621,209);
      if(confirm && !close) {
        if(is_hub) {
          hub_selection_=selected_;
          hub::pending=unsigned(selected_+1);
        } else if(is_sound) {
          if(!sound::pending.load() && values_!=saved_) {
            unsigned bits=0;
            for(int i=0;i<kVolumeRows;++i)bits|=unsigned(values_[i])<<(i*5);
            display_busy_=true;
            sound::pending=sound::apply_flag|bits;
          }
        } else if(!is_gameplay)Apply();
        else if(!gameplay::pending.load()) {
          if(confirm_wipe_)gameplay::pending=gameplay::wipe;
          else if(selected_==controls_row_)controls_editor_.Open(host->user_data_root());
          else if(selected_==wipe_row_)confirm_wipe_=true;
          else if(values_!=saved_) {
            unsigned bits=0;
            for(int i=0;i<controls_row_;++i)bits|=unsigned(values_[i])<<i;
            display_busy_=true;
            gameplay::pending=gameplay::apply_flag|bits;
          }
        }
      }
      if(!is_hub)label(is_gameplay?(confirm_wipe_?"Reset saved progress? Backup kept.":"Left / Right to change  |  Select to apply"):
            (!is_sound && selected_>=5 && selected_<10?"Select to save  |  Applies after restart":"Left / Right to change  |  Select to apply"),
            17,640,633,white,true);
      draw->Flags=draw_flags;
    }
    ImGui::End();
    if(font_)ImGui::PopFont();
    ImGui::PopStyleVar();
    ImGui::PopStyleColor();
    if(close && is_hub) {
      hub_selection_=0;
      hub::pending=hub::Back;
    } else if(close && is_sound) {
      if(!sound::pending.load())sound::pending=sound::back;
    } else if(close && is_gameplay) {
      if(confirm_wipe_)confirm_wipe_=false;
      else if(!gameplay::pending.load())gameplay::pending=gameplay::back;
    } else if(close && !display_busy_){
      release_guard=true;visible=false;loaded_=false;
      REXLOG_INFO("Cosmic Options preview: Video closed");
    }
  }
};
}
