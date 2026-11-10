#pragma once
// Original-menu integration, enabled by the launcher's handoff event or an
// explicit private diagnostic. No host popup replaces the game's menu.
// Registration uses the existing game script registry and SDK thunk allocator.
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/thread_state.h>
#include <rex/system/xmemory.h>
#include <rex/ui/window.h>
#include <rex/ppc.h>
#include <atomic>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <Windows.h>
#include "pc_video_menu.h"
#include "all_aliens_paging.h"
#include "performance_visibility.h"
#include "discord_presence.h"
#include "ultimate_hud_palette.h"
#include "albedo_hud.h"
#include "albedo_textures.h"
#include <vector>
#include <mutex>
#include <rex/input/input_system.h>

namespace ben10_pc_menu {
inline std::atomic<rex::Runtime*> runtime{nullptr};
inline std::atomic<rex::ui::Window*> window{nullptr};
inline std::atomic<bool> registered{false};
inline ben10::AlienPages alien_pages;
inline bool all_aliens_enabled=false;
inline bool hero_time_enabled=false;
inline bool hero_button_armed=false;
inline bool hero_input_observed=false;
inline std::mutex video_settings_mutex;
inline void ReturnVoid(PPCContext& ctx,uint8_t* base);
inline void SaveVideoKey(const std::filesystem::path& path,const std::string& key,const std::string& value);
inline void ReturnNumber(PPCContext& ctx,uint8_t* base,float value) {
  // Original sub_820F9090: BE u16 type=2, u16 flags=0, f32 payload.
  // Native script return slots are distinct from the PPC integer return value.
  if(ctx.r4.s32<0 || ctx.r4.u32>=1024)return;
  const uint32_t slot=0x826F8718+ctx.r4.u32*8;
  uint32_t bits;std::memcpy(&bits,&value,4);
  const uint32_t encoded_type=_byteswap_ulong(0x00020000);
  bits=_byteswap_ulong(bits);
  std::memcpy(base+slot,&encoded_type,4);std::memcpy(base+slot+4,&bits,4);
}
inline void AllAliensPage(PPCContext& ctx,uint8_t* base) {
  if(!all_aliens_enabled){alien_pages.Poll(false,false,0,0);ReturnNumber(ctx,base,-1);return;}
  auto* host=runtime.load();
  rex::input::X_INPUT_STATE state{};
  auto* input=host?static_cast<rex::input::InputSystem*>(host->input_system()):nullptr;
  const bool connected=input && input->GetState(0,&state)==0;
  ReturnNumber(ctx,base,float(alien_pages.Poll(all_aliens_enabled,connected,
      state.gamepad.left_trigger,state.gamepad.right_trigger)));
}
inline void AllAliensEnabled(PPCContext& ctx,uint8_t* base) {
  if(std::getenv("BEN10_MENU_AUDIT"))REXLOG_INFO("Cosmic menu audit: Gameplay rows created");
  ReturnNumber(ctx,base,all_aliens_enabled?1.0f:0.0f);
}
inline void AllAliensTrace(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  REXLOG_INFO("Cosmic All Aliens: applied page change through original game HUD");
}
inline void ToggleAllAliens(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();if(!host)return;
  const bool next=!all_aliens_enabled;
  try {
    std::lock_guard guard(video_settings_mutex);
    SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","all_aliens",next?"on":"off");
    all_aliens_enabled=next;
    REXLOG_INFO("Cosmic Gameplay: All Aliens {}",next?"ON":"OFF");
  }catch(const std::exception& e){REXLOG_ERROR("Cosmic Gameplay settings: {}",e.what());}
}
inline bool HeroTimeDiagnostic() {
  const char* value=std::getenv("BEN10_HERO_TIME_DIAGNOSTIC");
  return value && std::strcmp(value,"1")==0;
}
inline void HeroTimeEnabled(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,hero_time_enabled?1.0f:0.0f);
}
inline void ToggleHeroTime(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);auto* host=runtime.load();if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    const bool next=!hero_time_enabled;
    SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","hero_time",next?"on":"off");
    hero_time_enabled=next;hero_button_armed=false;
    REXLOG_INFO("Cosmic private Hero Time: {}",next?"ON":"OFF");
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic Hero Time settings: {}",error.what());}
}
inline void AlbedoHudEnabled(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,ben10::albedo_hud::enabled.load(std::memory_order_relaxed)?1.0f:0.0f);
}
inline void ToggleAlbedoHud(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    const bool next=!ben10::albedo_hud::enabled.load(std::memory_order_relaxed);
    SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","albedo_hud_preview",next?"on":"off");
    ben10::albedo_hud::enabled.store(next,std::memory_order_relaxed);
    REXLOG_INFO("Cosmic Gameplay: Albedo HUD preview {}",next?"ON":"OFF");
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic Albedo HUD settings: {}",error.what());}
}
inline void HeroTimeButton(PPCContext& ctx,uint8_t* base) {
  auto* host=runtime.load();rex::input::X_INPUT_STATE state{};
  auto* input=host?static_cast<rex::input::InputSystem*>(host->input_system()):nullptr;
  const bool connected=input && input->GetState(0,&state)==0;
  if(!hero_input_observed) {
    hero_input_observed=true;
    REXLOG_INFO("Cosmic private Hero Time: input callback observed; enabled={}, connected={}",hero_time_enabled,connected);
  }
  if(!hero_time_enabled || !connected){hero_button_armed=false;ReturnNumber(ctx,base,0);return;}
  const bool down=(state.gamepad.buttons & 0x0040)!=0; // L3; preserve R3/LT/RT.
  const bool pressed=down && hero_button_armed;
  hero_button_armed=!down;
  if(pressed)REXLOG_INFO("Cosmic private Hero Time: L3 edge observed");
  ReturnNumber(ctx,base,pressed?1.0f:0.0f);
}
inline void HeroTimeDelta(PPCContext& ctx,uint8_t* base) {
  // Original guest simulation delta. The authored gameplay update must gate
  // pauses/cutscenes/loading; presentation callbacks must never advance it.
  uint32_t encoded;std::memcpy(&encoded,base+0x826EBFC0,4);
  const uint32_t bits=_byteswap_ulong(encoded);float seconds;
  std::memcpy(&seconds,&bits,4);
  ReturnNumber(ctx,base,std::isfinite(seconds) && seconds>0?seconds:0.0f);
}
template<int Event> void HeroTimeTrace(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  const char* events[]={"resources ready","Ultimate confirmed","return requested","Ben confirmed; recharge started","recharge complete"};
  REXLOG_INFO("Cosmic private Hero Time: {}",events[Event]);
}
template<bool Active> void UltimateHudPalette(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  ben10::ultimate_hud::active.store(Active,std::memory_order_relaxed);
}
inline bool enabled() {
  if(std::getenv("BEN10_RETURN_TO_LAUNCHER_EVENT"))return true;
  const char* value=std::getenv("BEN10_PC_MENU_DIAGNOSTIC");
  return value && std::strcmp(value,"1")==0;
}
inline void ReturnVoid(PPCContext& ctx,uint8_t* base) {
  // The game's native callback ABI returns through an indexed VM value,
  // not the PPC r3 integer return register (see original clearfunctions).
  if(ctx.r4.s32>=0 && ctx.r4.u32<1024) {
    uint32_t empty=0;
    std::memcpy(base+0x826F8718+ctx.r4.u32*8,&empty,sizeof(empty));
  }
}
template<int Level> void PresenceLevel(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  const char* levels[]={"menus","l_chin","l_mili","l_pari","l_romd","l_romn","l_rush","l_tokd","l_tokn"};
  ben10_presence::Publish(levels[Level]);
}
inline void QuitToLauncher(PPCContext& ctx, uint8_t* base) {
  REXLOG_INFO("Cosmic PC menu: QUIT TO LAUNCHER selected");
  ReturnVoid(ctx,base);
  auto* current=window.load();
  if(!current)return;
  current->app_context().CallInUIThreadDeferred([] {
    auto* current=window.load();
    if(!current)return;
    wchar_t name[256]{};
    DWORD size=GetEnvironmentVariableW(L"BEN10_RETURN_TO_LAUNCHER_EVENT",name,256);
    if(size && size<256) {
      HANDLE event=OpenEventW(EVENT_MODIFY_STATE,FALSE,name);
      if(event){SetEvent(event);CloseHandle(event);}
    }
    current->RequestClose();
  });
}
inline void WipeProgress(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  wchar_t name[256]{};
  DWORD size=GetEnvironmentVariableW(L"BEN10_RESET_PROGRESS_EVENT",name,256);
  if(!size || size>=256){REXLOG_ERROR("Cosmic reset requires the matching launcher");return;}
  HANDLE event=OpenEventW(EVENT_MODIFY_STATE,FALSE,name);
  if(!event){REXLOG_ERROR("Cosmic reset event unavailable; progress preserved");return;}
  SetEvent(event);CloseHandle(event);
  REXLOG_INFO("Cosmic Gameplay: confirmed progress reset; archive deferred until game exits");
  QuitToLauncher(ctx,base);
}
inline void WipePrompt(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  if(std::getenv("BEN10_MENU_AUDIT"))REXLOG_INFO("Cosmic menu audit: Wipe Data confirmation opened");
}
template<int Resolution,int Rate> void SetVideo(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    auto path=host->user_data_root()/"pc-video.ini";
    std::string resolution="720p",rate="30",line;std::vector<std::string> other;
    {std::ifstream file(path);while(std::getline(file,line)) {
      if(!line.empty() && line.back()=='\r')line.pop_back();
      if(line=="resolution=1080p")resolution="1080p";
      if(line=="resolution=1440p")resolution="1440p";
      if(line=="resolution=4k")resolution="4k";
      if(line=="frame_limit=60")rate="60";
      if(line=="frame_limit=120")rate="120";
      if(line=="frame_limit=unlimited")rate="unlimited";
      if(line.rfind("resolution=",0)!=0 && line.rfind("frame_limit=",0)!=0)other.push_back(line);
    }}
    if constexpr(Resolution>=0){const char* choices[]={"720p","1080p","1440p","4k"};resolution=choices[Resolution];}
    if constexpr(Rate>=0)rate=Rate==0?"unlimited":std::to_string(Rate);
    std::filesystem::create_directories(path.parent_path());auto temporary=path;temporary+=L".native.tmp";
    {std::ofstream file(temporary,std::ios::binary|std::ios::trunc);file<<"resolution="<<resolution<<"\nframe_limit="<<rate<<"\n";for(const auto& extra:other)file<<extra<<'\n';file.flush();if(!file)throw std::runtime_error("Could not write video settings");}
    if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))throw std::runtime_error("Could not commit video settings");
    if constexpr(Rate>=0)if(!ben10_pacing_probe::pacer.SetRate(Rate))throw std::runtime_error("Could not apply frame limit");
    REXLOG_INFO("Cosmic native VIDEO: resolution={}, frame_limit={}, saved=true",resolution,rate);
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic native VIDEO failed: {}",error.what());}
}
inline std::string ReadVideoSetting(const std::filesystem::path& path,const std::string& key,const char* fallback) {
  std::ifstream input(path);std::string line,value=fallback;
  while(std::getline(input,line)) {
    if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line.rfind(key+"=",0)==0)value=line.substr(key.size()+1);
  }
  return value;
}
inline void SaveVideoKey(const std::filesystem::path& path,const std::string& key,const std::string& value) {
  std::vector<std::string> lines;std::string line;
  {std::ifstream input(path);while(std::getline(input,line)) {
    if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line.rfind(key+"=",0)!=0)lines.push_back(line);
  }}
  auto temporary=path;temporary+=L".presentation.tmp";
  {std::ofstream output(temporary,std::ios::trunc);for(const auto& extra:lines)output<<extra<<'\n';
    output<<key<<'='<<value<<'\n';output.flush();
    if(!output)throw std::runtime_error("Could not save presentation settings");}
  if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
    throw std::runtime_error("Could not commit presentation settings");
}
inline int DisplayMode(const std::filesystem::path& path) {
  const auto mode=ReadVideoSetting(path,"display_mode","windowed");
  return mode=="exclusive"?2:mode=="borderless"?1:0;
}
inline int ResolutionIndex(const std::filesystem::path& path) {
  const auto value=ReadVideoSetting(path,"resolution","720p");
  return value=="4k"?3:value=="1440p"?2:value=="1080p"?1:0;
}
inline void ApplyPresentation(rex::ui::Window* active,int mode,int resolution) {
  using Configure=int(*)(void*,int,int,int,char*,size_t);
  auto configure=reinterpret_cast<Configure>(GetProcAddress(GetModuleHandleW(L"rexruntime.dll"),"Ben10ConfigurePresentation"));
  if(!configure)throw std::runtime_error("Matching SDK presentation extension is required");
  const int widths[]={1280,1920,2560,3840},heights[]={720,1080,1440,2160};
  const bool previous=active->IsFullscreen();active->SetFullscreen(false);
  char error[512]{};
  if(!configure(active->GetNativeWindowHandle(),mode,widths[resolution],heights[resolution],error,sizeof(error))) {
    active->SetFullscreen(previous);throw std::runtime_error(error);
  }
  active->SetFullscreen(mode!=0);
  REXLOG_INFO("Cosmic presentation: mode={}, requested output={}x{}, desktop size retained in borderless",mode,widths[resolution],heights[resolution]);
}
template<int Resolution> void SetResolution(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);auto* host=runtime.load();auto* current=window.load();if(!host || !current)return;
  auto path=host->user_data_root()/"pc-video.ini";
  current->app_context().CallInUIThreadDeferred([path] {
    auto* active=window.load();if(!active)return;
    try {
      std::lock_guard guard(video_settings_mutex);
      const int mode=DisplayMode(path);
      if(mode!=1)ApplyPresentation(active,mode,Resolution);
      const char* choices[]={"720p","1080p","1440p","4k"};
      SaveVideoKey(path,"resolution",choices[Resolution]);
      REXLOG_INFO("Cosmic native VIDEO: output_resolution={}, applied_without_restart=true",choices[Resolution]);
    }catch(const std::exception& error){REXLOG_ERROR("Cosmic resolution failed: {}",error.what());}
  });
}
template<int Mode> void SetDisplayMode(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);auto* host=runtime.load();auto* current=window.load();
  if(!host || !current)return;
  const auto path=host->user_data_root()/"pc-video.ini";
  current->app_context().CallInUIThreadDeferred([path] {
    auto* active=window.load();if(!active)return;
    try {
      std::lock_guard guard(video_settings_mutex);
      ApplyPresentation(active,Mode,ResolutionIndex(path));
      const char* names[]={"windowed","borderless","exclusive"};
      SaveVideoKey(path,"display_mode",names[Mode]);
      REXLOG_INFO("Cosmic native VIDEO: display_mode={}, applied=true",names[Mode]);
    }catch(const std::exception& error){REXLOG_ERROR("Cosmic display mode failed: {}",error.what());}
  });
}
inline constexpr const char* ButtonIconNames[]={"auto","xbox","playstation","keyboard"};
template<ben10::albedo_textures::ButtonIcons Mode> void SetButtonIcons(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();
  if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    const char* mode=ButtonIconNames[static_cast<int>(Mode)];
    SaveVideoKey(host->user_data_root()/"pc-video.ini","button_icons",mode);
    ben10::albedo_textures::button_icons=Mode;
    REXLOG_INFO("Cosmic native VIDEO: button_icons={}",mode);
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic button icons failed: {}",error.what());}
}
struct GraphicsSetting {
  const char* key;
  const char* values[5];
  int count;
};
inline constexpr GraphicsSetting GraphicsSettings[]={
  {"internal_resolution",{"original","1","2"},3},
  {"anti_aliasing",{"original","none","fxaa","fxaa_extreme"},4},
  {"texture_filtering",{"original","2","4","8","16"},5},
  {"sharpening",{"original","low","medium","high"},4},
  {"screen_bloom",{"original","low","medium","high"},4},
};
template<int Setting> int GraphicsChoice(const std::filesystem::path& path) {
  const auto preset=ReadVideoSetting(path,"graphics_preset","default");
  const char* defaults[]={
    preset=="high"?"2":"original",
    preset=="medium" || preset=="high"?"fxaa":"original",
    preset=="low"?"2":preset=="medium"?"8":preset=="high"?"16":"original",
    "original","original"
  };
  constexpr auto option=GraphicsSettings[Setting];
  const auto value=ReadVideoSetting(path,option.key,defaults[Setting]);
  for(int i=0;i<option.count;++i)if(value==option.values[i])return i;
  return 0;
}
template<int Setting> void ReadGraphics(PPCContext& ctx,uint8_t* base) {
  auto* host=runtime.load();
  ReturnNumber(ctx,base,host?float(GraphicsChoice<Setting>(host->user_data_root()/"pc-video.ini")):0.0f);
}
template<int Setting> void ChangeGraphics(int direction) {
  auto* host=runtime.load();
  if(!host)return;
  constexpr auto option=GraphicsSettings[Setting];
  const auto path=host->user_data_root()/"pc-video.ini";
  try {
    std::lock_guard guard(video_settings_mutex);
    const int next=(GraphicsChoice<Setting>(path)+direction+option.count)%option.count;
    SaveVideoKey(path,option.key,option.values[next]);
    REXLOG_INFO("Graphics {}={} saved",option.key,option.values[next]);
  }catch(const std::exception& error){REXLOG_ERROR("Could not save graphics option: {}",error.what());}
}
template<int Setting> void CycleGraphics(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  ChangeGraphics<Setting>(1);
}
namespace gameplay_preview {
inline std::atomic<bool> active{false};
inline std::atomic<unsigned> snapshot{0};
inline std::atomic<unsigned> pending{0};
inline unsigned tick_request=0; // Read and written only by the game script thread.
inline bool tick_stock_changed=false;
constexpr unsigned apply_flag=1u<<6;
constexpr unsigned back=1u<<7;
constexpr unsigned wipe=1u<<8;

template<unsigned Row,bool On> void Capture(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  if constexpr(On)snapshot.fetch_or(1u<<Row);
  else snapshot.fetch_and(~(1u<<Row));
}
inline constexpr const char* stock_keys[]={"invert_pitch","invert_yaw","vibration"};
template<unsigned Row> void StockPreference(PPCContext& ctx,uint8_t* base) {
  auto* host=runtime.load();
  const auto value=host?ReadVideoSetting(host->user_data_root()/"pc-gameplay.ini",stock_keys[Row],""):"";
  ReturnNumber(ctx,base,value=="on"?1.0f:value=="off"?0.0f:-1.0f);
}
inline void SaveStockPreferences(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();
  if(!host)return;
  const unsigned bits=snapshot.load();
  try {
    std::lock_guard guard(video_settings_mutex);
    const auto path=host->user_data_root()/"pc-gameplay.ini";
    for(unsigned row=0;row<std::size(stock_keys);++row)
      SaveVideoKey(path,stock_keys[row],(bits&(1u<<row))?"on":"off");
  } catch(const std::exception& error) {
    REXLOG_ERROR("Cosmic Gameplay: could not save controller preferences: {}",error.what());
  }
}
inline void Open(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  pending=0;
  snapshot=(snapshot.load()&7u)|(all_aliens_enabled?8u:0u)|(hero_time_enabled?16u:0u)|
      (ben10::albedo_hud::enabled.load()?32u:0u);
  ben10_pc_video::controller_sample=0;
  ben10_pc_video::opening_guard=true;
  active=true;
  ben10_pc_video::visible=true;
}
inline void BeginTick(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  tick_request=pending.load();
  tick_stock_changed=bool(tick_request&apply_flag) && bool((tick_request^snapshot.load())&7u);
}
template<unsigned Row> void Desired(PPCContext& ctx,uint8_t* base) {
  const auto request=tick_request;
  const auto bit=1u<<Row;
  ReturnNumber(ctx,base,(request&apply_flag) && ((request^snapshot.load())&bit)?
      ((request&bit)?1.0f:0.0f):-1.0f);
}
inline void Finish(PPCContext& ctx,uint8_t* base) {
  const auto request=tick_request;
  if(request&apply_flag) {
    if(tick_stock_changed)SaveStockPreferences(ctx,base);
    if(bool(request&8u)!=all_aliens_enabled)ToggleAllAliens(ctx,base);
    if(bool(request&16u)!=hero_time_enabled)ToggleHeroTime(ctx,base);
    if(bool(request&32u)!=ben10::albedo_hud::enabled.load())ToggleAlbedoHud(ctx,base);
    snapshot=(snapshot.load()&7u)|(all_aliens_enabled?8u:0u)|(hero_time_enabled?16u:0u)|
        (ben10::albedo_hud::enabled.load()?32u:0u);
    pending=0;
  }
  if(request&(back|wipe)) {
    if(request&wipe)WipeProgress(ctx,base);
    ben10_pc_video::release_guard=true;
    ben10_pc_video::visible=false;
    active=false;
    pending=0;
    ReturnNumber(ctx,base,1);
    return;
  }
  ReturnNumber(ctx,base,0);
}
}
namespace sound_preview {
inline std::atomic<bool> active{false};
inline std::atomic<unsigned> snapshot{0};
inline std::atomic<unsigned> pending{0};
inline unsigned tick_request=0; // Guest script thread only.
constexpr unsigned step_count=20;
constexpr unsigned apply_flag=1u<<15;
constexpr unsigned back=1u<<16;

template<unsigned Row> void Capture(PPCContext& ctx,uint8_t* base) {
  // The VM stores the method receiver first, followed by the float value.
  // Original sub_821B75A0 reads its first explicit argument at offset 12.
  uint32_t encoded_pointer;
  std::memcpy(&encoded_pointer,base+0x826F8688,sizeof(encoded_pointer));
  const auto arguments=_byteswap_ulong(encoded_pointer);
  if(arguments && arguments<=UINT32_MAX-16 && base[arguments+8]==0 && base[arguments+9]==2) {
    uint32_t encoded_value;
    std::memcpy(&encoded_value,base+arguments+12,sizeof(encoded_value));
    const auto bits=_byteswap_ulong(encoded_value);
    float value;
    std::memcpy(&value,&bits,sizeof(value));
    if(std::isfinite(value)) {
      const auto step=unsigned(std::lround(std::clamp(value,0.0f,1.0f)*step_count));
      const auto shift=Row*5;
      snapshot=(snapshot.load()&~(31u<<shift))|(step<<shift);
    }
  }
  ReturnVoid(ctx,base);
}
inline void Open(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  pending=0;
  ben10_pc_video::controller_sample=0;
  ben10_pc_video::opening_guard=true;
  active=true;
  ben10_pc_video::visible=true;
}
inline void BeginTick(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  tick_request=pending.load();
}
template<unsigned Row> void Desired(PPCContext& ctx,uint8_t* base) {
  constexpr unsigned shift=Row*5;
  const auto requested=(tick_request>>shift)&31u;
  const auto saved=(snapshot.load()>>shift)&31u;
  ReturnNumber(ctx,base,(tick_request&apply_flag) && requested!=saved?
      float(requested)/step_count:-1.0f);
}
inline void Finish(PPCContext& ctx,uint8_t* base) {
  if(tick_request&back) {
    ben10_pc_video::release_guard=true;
    ben10_pc_video::visible=false;
    active=false;
  }
  if(tick_request)pending=0;
  ReturnNumber(ctx,base,(tick_request&back)?1.0f:0.0f);
}
}
namespace options_hub {
inline std::atomic<bool> active{false};
inline std::atomic<bool> credits{false};
inline std::atomic<unsigned> pending{0};
inline bool returning=false; // Guest script thread only.
enum Action : unsigned { Gameplay=1, Sound, Video, Credits, Back };

inline void Show() {
  ben10_pc_video::controller_sample=0;
  ben10_pc_video::opening_guard=true;
  active=true;
  ben10_pc_video::visible=true;
}
template<bool CreditsAvailable> void Open(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  credits=CreditsAvailable;
  pending=0;
  returning=false;
  Show();
}
inline void Poll(PPCContext& ctx,uint8_t* base) {
  if(returning && !ben10_pc_video::CapturesGameInput()) {
    returning=false;
    Show();
  }
  const auto action=pending.exchange(0);
  if(action) {
    active=false;
    returning=action>=Gameplay && action<=Video;
    if(!returning) {
      ben10_pc_video::release_guard=true;
      ben10_pc_video::visible=false;
    }
  }
  ReturnNumber(ctx,base,float(action));
}
}
inline void OpenVideoPreview(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  ben10_pc_video::controller_sample=0;
  ben10_pc_video::opening_guard=true;
  ben10_pc_video::visible=true;
}
template<bool Visible> void SetPerformanceOverlay(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);auto* host=runtime.load();if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    auto path=host->user_data_root()/"pc-video.ini";auto temporary=path;temporary+=L".overlay.tmp";
    std::vector<std::string> lines;std::string line;
    {std::ifstream input(path);while(std::getline(input,line)) {
      if(!line.empty()&&line.back()=='\r')line.pop_back();
      if(line.rfind("performance_overlay=",0)!=0)lines.push_back(line);
    }}
    {std::ofstream output(temporary,std::ios::trunc);for(const auto& extra:lines)output<<extra<<'\n';
      output<<"performance_overlay="<<(Visible?"on":"off")<<'\n';output.flush();
      if(!output)throw std::runtime_error("Could not save overlay visibility");}
    if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
      throw std::runtime_error("Could not commit overlay visibility");
    ben10::performance_visible.store(Visible,std::memory_order_relaxed);
    REXLOG_INFO("Cosmic native VIDEO: performance_overlay={}",Visible?"on":"off");
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic overlay setting failed: {}",error.what());}
}
inline void OnFrame() {
  auto* host=runtime.load();
  if(!host)return;
  auto* thread=rex::runtime::ThreadState::Get();
  if(!thread)return;
  // InputSystem refreshes its device vectors during GetState. The UI must
  // consume a snapshot rather than entering that code alongside guest input.
  if(ben10_pc_video::CapturesGameInput()) {
    auto* input=static_cast<rex::input::InputSystem*>(host->input_system());
    rex::input::X_INPUT_STATE state{};
    ben10_pc_video::polling_options=true;
    if(input)input->GetState(0,&state);
    ben10_pc_video::polling_options=false;
    uint32_t sample=ben10_pc_video::sample_valid|state.gamepad.buttons;
    if(state.gamepad.thumb_lx<-16000)sample|=4;
    if(state.gamepad.thumb_lx>16000)sample|=8;
    if(state.gamepad.thumb_ly>16000)sample|=1;
    if(state.gamepad.thumb_ly<-16000)sample|=2;
    ben10_pc_video::controller_sample.store(sample,std::memory_order_relaxed);
  }
  if(registered.load())return;
  auto* base=host->memory()->virtual_membase();
  // sub_821C1140 stores the script registry here, before registering overlays.
  uint32_t encoded_registry;
  std::memcpy(&encoded_registry,base+0x826EC6A0,sizeof(encoded_registry));
  const uint32_t registry=_byteswap_ulong(encoded_registry);
  if(!registry)return;
  bool expected=false;
  if(!registered.compare_exchange_strong(expected,true))return;
  auto* registration=host->function_dispatcher()->GetFunction(0x82237E78);
  if(!registration) {
    REXLOG_ERROR("Cosmic PC menu: native registration unavailable");return;
  }
  auto add=[&](const char* name,PPCFunc* function,uint32_t arguments=1) {
    const uint32_t callback=host->function_dispatcher()->AllocateThunk(function,0);
    const uint32_t text=host->memory()->SystemHeapAlloc(uint32_t(std::strlen(name)+1));
    if(!callback || !text)throw std::runtime_error("PC menu callback allocation failed");
    std::memcpy(base+text,name,std::strlen(name)+1);
    // A local context keeps all live guest registers intact across the nested call.
    PPCContext context=*thread->context();
    context.r3.u64=registry;context.r4.u64=text;context.r5.u64=text;
    context.r6.u64=arguments;context.r7.u64=callback;context.r8.u64=0;
    registration(context,base);
    REXLOG_INFO("Cosmic PC menu: registered {} callback {:08X}, registry {:08X}",name,callback,registry);
  };
  add("cosmic_quit_to_launcher",QuitToLauncher);
  add("cosmic_preview_video",OpenVideoPreview);
  add("cosmic_options_open",options_hub::Open<false>);
  add("cosmic_options_open_credits",options_hub::Open<true>);
  add("cosmic_options_poll",options_hub::Poll);
  add("cosmic_sound_open",sound_preview::Open);
  add("cosmic_sound_begin_tick",sound_preview::BeginTick);
  add("cosmic_sound_finish",sound_preview::Finish);
  add("cosmic_sound_music_read",sound_preview::Capture<0>,2);
  add("cosmic_sound_sfx_read",sound_preview::Capture<1>,2);
  add("cosmic_sound_voice_read",sound_preview::Capture<2>,2);
  add("cosmic_sound_music_value",sound_preview::Desired<0>);
  add("cosmic_sound_sfx_value",sound_preview::Desired<1>);
  add("cosmic_sound_voice_value",sound_preview::Desired<2>);
  add("cosmic_gameplay_open",gameplay_preview::Open);
  add("cosmic_gameplay_finish",gameplay_preview::Finish);
  add("cosmic_gameplay_begin_tick",gameplay_preview::BeginTick);
  add("cosmic_gameplay_pitch_preference",gameplay_preview::StockPreference<0>);
  add("cosmic_gameplay_yaw_preference",gameplay_preview::StockPreference<1>);
  add("cosmic_gameplay_vibration_preference",gameplay_preview::StockPreference<2>);
  add("cosmic_gameplay_save_stock",gameplay_preview::SaveStockPreferences);
  add("cosmic_gameplay_pitch_off",gameplay_preview::Capture<0,false>);
  add("cosmic_gameplay_pitch_on",gameplay_preview::Capture<0,true>);
  add("cosmic_gameplay_yaw_off",gameplay_preview::Capture<1,false>);
  add("cosmic_gameplay_yaw_on",gameplay_preview::Capture<1,true>);
  add("cosmic_gameplay_vibration_off",gameplay_preview::Capture<2,false>);
  add("cosmic_gameplay_vibration_on",gameplay_preview::Capture<2,true>);
  add("cosmic_gameplay_pitch_value",gameplay_preview::Desired<0>);
  add("cosmic_gameplay_yaw_value",gameplay_preview::Desired<1>);
  add("cosmic_gameplay_vibration_value",gameplay_preview::Desired<2>);
  add("cosmic_set_720",SetResolution<0>);
  add("cosmic_set_1080",SetResolution<1>);
  add("cosmic_set_1440",SetResolution<2>);
  add("cosmic_set_4k",SetResolution<3>);
  add("cosmic_set_30",SetVideo<-1,30>);
  add("cosmic_set_60",SetVideo<-1,60>);
  add("cosmic_set_120",SetVideo<-1,120>);
  add("cosmic_index_scale",ReadGraphics<0>);
  add("cosmic_index_aa",ReadGraphics<1>);
  add("cosmic_index_filter",ReadGraphics<2>);
  add("cosmic_index_sharpen",ReadGraphics<3>);
  add("cosmic_index_bloom",ReadGraphics<4>);
  add("cosmic_cycle_scale",CycleGraphics<0>);
  add("cosmic_cycle_aa",CycleGraphics<1>);
  add("cosmic_cycle_filter",CycleGraphics<2>);
  add("cosmic_cycle_sharpen",CycleGraphics<3>);
  add("cosmic_cycle_bloom",CycleGraphics<4>);
  add("cosmic_set_unlimited",SetVideo<-1,0>);
  add("cosmic_overlay_on",SetPerformanceOverlay<true>);
  add("cosmic_overlay_off",SetPerformanceOverlay<false>);
  add("cosmic_windowed",SetDisplayMode<0>);
  add("cosmic_borderless",SetDisplayMode<1>);
  add("cosmic_exclusive",SetDisplayMode<2>);
  using ben10::albedo_textures::ButtonIcons;
  add("cosmic_icons_auto",SetButtonIcons<ButtonIcons::Auto>);
  add("cosmic_icons_xbox",SetButtonIcons<ButtonIcons::Xbox>);
  add("cosmic_icons_playstation",SetButtonIcons<ButtonIcons::PlayStation>);
  add("cosmic_icons_keyboard",SetButtonIcons<ButtonIcons::Keyboard>);
  const auto iconMode=ReadVideoSetting(host->user_data_root()/"pc-video.ini","button_icons","xbox");
  for(int i=0;i<4;++i)
    if(iconMode==ButtonIconNames[i])ben10::albedo_textures::button_icons=static_cast<ButtonIcons>(i);
  add("cosmic_wipe_progress",WipeProgress);
  add("cosmic_wipe_prompt",WipePrompt);
  {std::ifstream settings(host->user_data_root()/"pc-video.ini");std::string line;
    while(std::getline(settings,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();
      if(line=="performance_overlay=off")ben10::performance_visible=false;
      if(line=="performance_overlay=on")ben10::performance_visible=true;}}
  {std::ifstream settings(host->user_data_root()/"pc-gameplay.ini");std::string line;
    while(std::getline(settings,line)) {
      if(!line.empty() && line.back()=='\r')line.pop_back();
      if(line=="all_aliens=on")all_aliens_enabled=true;
      if(line=="all_aliens=off")all_aliens_enabled=false;
      if(HeroTimeDiagnostic() && line=="hero_time=on")hero_time_enabled=true;
      if(line=="hero_time=off")hero_time_enabled=false;
      if(line=="albedo_hud_preview=on")ben10::albedo_hud::enabled=true;
      if(line=="albedo_hud_preview=off")ben10::albedo_hud::enabled=false;
    }}
  add("cosmic_all_aliens_page",AllAliensPage);
  if(std::getenv("BEN10_DISCORD_STATUS_FILE")) {
    add("cosmic_presence_menus",PresenceLevel<0>);
    add("cosmic_presence_l_chin",PresenceLevel<1>);
    add("cosmic_presence_l_mili",PresenceLevel<2>);
    add("cosmic_presence_l_pari",PresenceLevel<3>);
    add("cosmic_presence_l_romd",PresenceLevel<4>);
    add("cosmic_presence_l_romn",PresenceLevel<5>);
    add("cosmic_presence_l_rush",PresenceLevel<6>);
    add("cosmic_presence_l_tokd",PresenceLevel<7>);
    add("cosmic_presence_l_tokn",PresenceLevel<8>);
  }
  add("cosmic_toggle_all_aliens",ToggleAllAliens);
  add("cosmic_all_aliens_enabled",AllAliensEnabled);
  add("cosmic_all_aliens_trace",AllAliensTrace);
  if(HeroTimeDiagnostic()) {
    add("cosmic_hero_enabled",HeroTimeEnabled);
    add("cosmic_toggle_hero_time",ToggleHeroTime);
    add("cosmic_hero_button",HeroTimeButton);
    add("cosmic_hero_delta",HeroTimeDelta);
    add("cosmic_hero_loaded",HeroTimeTrace<0>);
    add("cosmic_hero_active",HeroTimeTrace<1>);
    add("cosmic_hero_return",HeroTimeTrace<2>);
    add("cosmic_hero_recharge",HeroTimeTrace<3>);
    add("cosmic_hero_ready",HeroTimeTrace<4>);
    add("cosmic_ultimate_hud_on",UltimateHudPalette<true>);
    add("cosmic_ultimate_hud_off",UltimateHudPalette<false>);
    add("cosmic_albedo_hud_enabled",AlbedoHudEnabled);
    add("cosmic_toggle_albedo_hud",ToggleAlbedoHud);
  }
}
}
