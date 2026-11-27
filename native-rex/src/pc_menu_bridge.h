#pragma once
#include "photo_mode.h"
// Original-menu integration, enabled by the launcher's handoff event or an
// explicit private diagnostic. No host popup replaces the game's menu.
// Registration uses the existing game script registry and SDK thunk allocator.
#include "language_setting.h"
#include "text_overlay.h"
#include "ben_upgrade_arc.h"
#include "ben_upgrade_frame.h"
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/thread_state.h>
#include <rex/system/xmemory.h>
#include <rex/ui/window.h>
#include <rex/ppc.h>
#include <atomic>
#include <bit>
#include <thread>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <Windows.h>
#include <mmsystem.h>
#include "pc_video_menu.h"
#include "all_aliens_paging.h"
#include "performance_visibility.h"
#include "discord_presence.h"
#include "ultimate_hud_palette.h"
#include "albedo_hud.h"
#include "albedo_textures.h"
#include <vector>
#include <set>
#include <tuple>
#include <mutex>
#include <rex/input/input_system.h>
#include "pc_monitors.h"
#include "cosmetics_state.h"
#include "upgrade_economy.h"

extern "C" void sub_821FED60(PPCContext&, uint8_t*);
extern "C" void sub_821C8100(PPCContext&, uint8_t*);

namespace ben10_pc_menu {
inline std::atomic<rex::Runtime*> runtime{nullptr};
inline std::atomic<rex::ui::Window*> window{nullptr};
inline std::atomic<bool> registered{false};
inline ben10::AlienPages alien_pages;
inline bool all_aliens_enabled=false;
// all_aliens_enabled is the backwards-compatible preference, not ownership.
inline std::atomic<bool> master_control_unlocked{false};
inline bool MasterControlActive() {
  return master_control_unlocked.load(std::memory_order_relaxed);
}
inline bool hero_time_enabled=false;
inline std::atomic<bool> transformation_animation_enabled{false};
inline std::atomic<bool> transformation_animation_pending{false};
inline bool hero_button_armed=false;
inline bool hero_input_observed=false;
inline std::mutex video_settings_mutex;
inline std::atomic<bool> background_controller_input{false};
inline std::atomic<bool> mission_active{false};
inline std::atomic<bool> pause_menu_active{false};
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
  if(!MasterControlActive()){alien_pages.Poll(false,false,0,0);ReturnNumber(ctx,base,-1);return;}
  auto* host=runtime.load();
  rex::input::X_INPUT_STATE state{};
  auto* input=host?static_cast<rex::input::InputSystem*>(host->input_system()):nullptr;
  const bool connected=input && ben10::photo::ReadGameState(input,state)==0;
  ReturnNumber(ctx,base,float(alien_pages.Poll(MasterControlActive(),connected,
      state.gamepad.left_trigger,state.gamepad.right_trigger)));
}
inline void AllAliensEnabled(PPCContext& ctx,uint8_t* base) {
  if(std::getenv("BEN10_MENU_AUDIT"))REXLOG_INFO("Cosmic menu audit: Gameplay rows created");
  ReturnNumber(ctx,base,MasterControlActive()?1.0f:0.0f);
}
inline void AllAliensTrace(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  REXLOG_INFO("Cosmic All Aliens: applied page change through original game HUD");
}
inline void ToggleAllAliens(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  // Legacy callback retained for old scripts; ownership is save-only.
}
inline bool HeroTimeDiagnostic() {
  const char* value=std::getenv("BEN10_HERO_TIME_DIAGNOSTIC");
  return value && std::strcmp(value,"1")==0;
}
inline void HeroTimeEnabled(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,hero_time_enabled?1.0f:0.0f);
}
inline void ToggleHeroTime(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
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
    ben10::albedo_textures::ArmWayBigBeamTrace();
    if (ben10::albedo_textures::final_battle_active.load() &&
        ben10::albedo_textures::final_battle_trace_enabled.load())
      ++ben10::albedo_textures::final_battle_trace_epoch;
    REXLOG_INFO("Cosmic Gameplay: Albedo HUD preview {}",next?"ON":"OFF");
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic Albedo HUD settings: {}",error.what());}
}
inline void HeroTimeButton(PPCContext& ctx,uint8_t* base) {
  auto* host=runtime.load();rex::input::X_INPUT_STATE state{};
  auto* input=host?static_cast<rex::input::InputSystem*>(host->input_system()):nullptr;
  const bool connected=input && ben10::photo::ReadGameState(input,state)==0;
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
inline void UltimateCannonboltVoice(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  const DWORD count=GetEnvironmentVariableW(L"BEN10_ULTIMATE_CANNONBOLT_VOICE",nullptr,0);
  if(!count)return;
  std::wstring path(count,L'\0');
  const DWORD length=GetEnvironmentVariableW(L"BEN10_ULTIMATE_CANNONBOLT_VOICE",path.data(),count);
  if(!length || length>=count)return;
  const bool played=PlaySoundW(path.c_str(),nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT)!=FALSE;
  REXLOG_INFO("Ultimate Cannonbolt: host voice playback {}",played?"started":"failed");
}
inline bool ultimate_way_big_pending = false;
inline bool ultimate_way_big_request_observed = false;
inline uint64_t ultimate_way_big_load_deadline = 0;

inline uint32_t ReadWayBigWord(const uint8_t* base,uint32_t address) {
  uint32_t encoded = 0;
  std::memcpy(&encoded,base+address,sizeof(encoded));
  return _byteswap_ulong(encoded);
}

inline void CaptureWayBigPerson(uint8_t* base) {
  const uint32_t arguments = ReadWayBigWord(base,0x826F8688);
  if (arguments && arguments <= UINT32_MAX-16) {
    ben10::ultimate_way_big::player_person.store(ReadWayBigWord(base,arguments+12),std::memory_order_relaxed);
  }
}

inline bool WayBigFormDrawable(const PPCContext& ctx,uint8_t* base,bool albedo) {
  using namespace ben10::ultimate_way_big;
  const auto id=albedo?kAlbedoMesh:kBenMesh;
  PPCContext skin=ctx;
  skin.r3.u64=id;
  sub_821C8100(skin,base);
  const auto weights=skin.r3.u32;
  if (!weights || ReadWayBigWord(base,weights+72)!=kVertices ||
      ReadWayBigWord(base,weights+76)!=kVertices) {
    REXLOG_WARN("Ultimate Way Big: keeping stock fighter, skin {:08X} unavailable or invalid (handle {:08X})",id,weights);
    return false;
  }

  PPCContext model=ctx;
  model.r3.u64=id;
  model.r4.u64=0;
  model.r5.u64=0;
  sub_821FED60(model,base);
  const auto resource=model.r3.u32;
  if (!resource || !ReadWayBigWord(base,resource+20)) {
    REXLOG_WARN("Ultimate Way Big: keeping stock fighter, model {:08X} unavailable (handle {:08X})",id,resource);
    return false;
  }
  REXLOG_INFO("Ultimate Way Big: verified live model and skin {:08X}",id);
  return true;
}

inline void TraceWayBigForm(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  const auto arguments=ReadWayBigWord(base,0x826F8688);
  if (!arguments || arguments>UINT32_MAX-16 ||
      ReadWayBigWord(base,arguments+8)!=0x00020000) return;
  const auto event = std::bit_cast<float>(ReadWayBigWord(base,arguments+12));
  static constexpr const char* events[] = {
      "preload called", "current mission unavailable", "package load requested",
      "package load callback reached", "L3 waiting for package", "form switch already in progress",
      "requesting Ultimate form", "requesting normal form", "switch callback reached",
      "form data missing", "current form is outside the Way Big pair",
  };
  for (unsigned index=0; index<std::size(events); ++index) {
    if (event!=float(index)) continue;
    REXLOG_INFO("Ultimate Way Big: {}", events[index]);
    return;
  }
}

inline void UltimateWayBigRequest(PPCContext& ctx,uint8_t* base) {
  using namespace ben10::ultimate_way_big;
  ReturnNumber(ctx,base,0);
  const auto frame = Ben10SubmittedFrames() + 1;
  const auto seen = player_frame.load(std::memory_order_relaxed);
  if (ben10::albedo_textures::final_battle_active.load(std::memory_order_relaxed) &&
      !ultimate_way_big_request_observed) {
    ultimate_way_big_request_observed = true;
    REXLOG_INFO("Ultimate Way Big: final battle request callback reached");
  }
  if (!ben10::albedo_textures::final_battle_active.load(std::memory_order_relaxed) ||
      pause_menu_active.load(std::memory_order_relaxed) || !seen || frame - seen > 4) {
    request_pressed.store(false,std::memory_order_relaxed);
    return;
  }
  auto* host = runtime.load();
  if (!host) return;
  const bool pressed = request_pressed.exchange(false,std::memory_order_relaxed);
  if (pressed && !transformation_animation_pending.load(std::memory_order_relaxed)) REXLOG_INFO("Ultimate Way Big: request callback observed L3");
  if (separate_form) {
    if (!pressed) return;
    if (!active.load(std::memory_order_relaxed) && !transformation_animation_pending.load(std::memory_order_relaxed)) {
      const bool albedo=ben10::albedo_hud::enabled.load(std::memory_order_relaxed);
      // Keep the alternate drawable for live palette switching.
      if (!WayBigFormDrawable(ctx,base,albedo) || !WayBigFormDrawable(ctx,base,!albedo)) return;
      form_albedo.store(albedo,std::memory_order_relaxed);
    }
    if (!transformation_animation_pending.load(std::memory_order_relaxed)) CaptureWayBigPerson(base);
    ReturnNumber(ctx,base,1);
    return;
  }
  const bool albedo = ben10::albedo_hud::enabled.load(std::memory_order_relaxed);
  if (pressed && active.exchange(false,std::memory_order_relaxed)) {
    player_person.store(0,std::memory_order_relaxed);
    REXLOG_INFO("Ultimate Way Big: returned to normal Way Big");
    ReturnNumber(ctx,base,1);
    return;
  }
  if (pressed && !ultimate_way_big_pending) {
    const auto ready = ready_frame[albedo].load(std::memory_order_relaxed);
    if (!ready) {
      // The stock loader resolves registered resident resources by mesh checksum.
      const uint32_t mesh = albedo ? kAlbedoMesh : kBenMesh;
      PPCContext load = ctx;
      load.r3.u64 = mesh;
      load.r4.u64 = 0;
      load.r5.u64 = 0;
      sub_821FED60(load,base);
      REXLOG_INFO("Ultimate Way Big: model load {:08X} returned {:08X}",mesh,load.r3.u32);
      if (!load.r3.u32) return;
    }
    ultimate_way_big_pending = true;
    checking_model.store(true,std::memory_order_relaxed);
    ultimate_way_big_load_deadline = frame + 180;
  }
  if (!ultimate_way_big_pending) return;
  const auto ready = ready_frame[albedo].load(std::memory_order_relaxed);
  if (!ready || frame - ready > 4) {
    if (frame >= ultimate_way_big_load_deadline) {
      ultimate_way_big_pending = false;
      checking_model.store(false,std::memory_order_relaxed);
      REXLOG_WARN("Ultimate Way Big: model load did not become drawable");
    }
    return;
  }
  ultimate_way_big_pending = false;
  checking_model.store(false,std::memory_order_relaxed);
  CaptureWayBigPerson(base);
  active.store(true,std::memory_order_relaxed);
  const auto voice = host->user_data_root() / "Ultimate_Way_Big_Clean.wav";
  PlaySoundW(voice.c_str(),nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);
  REXLOG_INFO("Ultimate Way Big: final battle transformation");
  ReturnNumber(ctx,base,1);
}
inline void UltimateWayBigReset(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  ben10::ultimate_way_big::active.store(false,std::memory_order_relaxed);
  ben10::ultimate_way_big::checking_model.store(false,std::memory_order_relaxed);
  ben10::ultimate_way_big::request_pressed.store(false,std::memory_order_relaxed);
  ben10::ultimate_way_big::l3_armed.store(false,std::memory_order_relaxed);
  for (auto& ready : ben10::ultimate_way_big::ready_frame)
    ready.store(0,std::memory_order_relaxed);
  ben10::ultimate_way_big::player_frame.store(0,std::memory_order_relaxed);
  ben10::ultimate_way_big::player_person.store(0,std::memory_order_relaxed);
  ultimate_way_big_pending = false;
  ultimate_way_big_request_observed = false;
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
  mission_active.store(Level != 0);
  pause_menu_active.store(false);
  const char* levels[]={"menus","l_chin","l_mili","l_pari","l_romd","l_romn","l_rush","l_tokd","l_tokn"};
  ben10::albedo_textures::final_battle_active.store(Level == 7);
  ben10::ultimate_way_big::preload_requested.store(false,std::memory_order_relaxed);
  UltimateWayBigReset(ctx,base);
  if constexpr (Level == 7) {
    if (ben10::albedo_textures::final_battle_trace_enabled.load())
      ++ben10::albedo_textures::final_battle_trace_epoch;
  }
  ben10_presence::Publish(levels[Level]);
}
template<bool Paused> void PauseMenuCursor(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  pause_menu_active.store(Paused);
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
// The pause menu's PHOTO MODE row: its script resumes the game, then calls this to start Photo Mode once play is live.
inline void PhotoModeFromPause(PPCContext& ctx, uint8_t* base) {
  REXLOG_INFO("Cosmic PC menu: PHOTO MODE selected");
  ReturnVoid(ctx,base);
  ben10::photo::RequestFromPauseMenu();
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
    if constexpr(Rate>=0) {
      // The launcher starts the guest at 120 Hz only for the 120 FPS limit; follow the same
      // rule live (the SDK's vblank timer re-reads this value a few times per second).
      rex::cvar::SetFlagByName("video_mode_refresh_rate",Rate==120?"120":"60");
      if(!ben10_pacing_probe::pacer.SetRate(Rate))throw std::runtime_error("Could not apply frame limit");
    }
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
inline void ApplyPresentation(rex::ui::Window* active,int mode,int resolution,
                              const std::string* selected_monitor=nullptr) {
  using Configure=int(*)(void*,int,int,int,char*,size_t);
  auto configure=reinterpret_cast<Configure>(GetProcAddress(GetModuleHandleW(L"rexruntime.dll"),"Ben10ConfigurePresentation"));
  if(!configure)throw std::runtime_error("Matching SDK presentation extension is required");
  const int widths[]={1280,1920,2560,3840},heights[]={720,1080,1440,2160};
  const bool previous=active->IsFullscreen();active->SetFullscreen(false);
  auto* host=runtime.load();
  std::string monitor;
  if(selected_monitor)monitor=*selected_monitor;
  else if(host) {
    std::ifstream file(host->user_data_root()/"monitor.txt");
    std::getline(file,monitor);
  }
  if(!ben10::monitors::Move(static_cast<HWND>(active->GetNativeWindowHandle()),monitor)) {
    active->SetFullscreen(previous);
    throw std::runtime_error("Could not move the game to the selected monitor");
  }
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
// Asked by the Options "Back" script: after a language change the title menu is rebuilt (the pause menu
// is built fresh each time it opens, and a running level is never touched).
inline void LanguageDirty(PPCContext& ctx,uint8_t* base) {
  // The title menu is rebuilt from the new text, so wait for the rewrite to finish.
  for(int i=0;i<400 && ben10::language::swapping.load();++i)Sleep(5);
  const bool dirty=ben10::language::menus_dirty.exchange(false);
  ReturnNumber(ctx,base,dirty && !mission_active.load() && !pause_menu_active.load()?1.0f:0.0f);
}
inline void ReadLanguage(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,float(ben10::language::current.load()));
}
inline void CycleLanguage(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  auto* host=runtime.load();
  const int next=(ben10::language::current.load()+1)%ben10::language::kCount;
  ben10::language::current=next;
  if(!host)return;
  try {
    std::lock_guard guard(video_settings_mutex);
    SaveVideoKey(host->user_data_root()/"pc-video.ini","language",ben10::language::kCodes[next]);
    REXLOG_INFO("Cosmic native VIDEO: language={}",ben10::language::kCodes[next]);
  }catch(const std::exception& error){REXLOG_ERROR("Cosmic language failed: {}",error.what());}
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
// Bit 7 belongs to Transformation Animation itself; the apply command
// must not force that preference ON when the user explicitly selects OFF.
constexpr unsigned apply_flag=1u<<10;
constexpr unsigned back=1u<<8;
constexpr unsigned wipe=1u<<9;
static_assert((apply_flag & 0xffu)==0 && (apply_flag & (back|wipe))==0);

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
  snapshot=(snapshot.load()&7u)|
      (ben10::albedo_hud::enabled.load()?32u:0u)|(background_controller_input.load()?64u:0u)|
      (transformation_animation_enabled.load()?128u:0u);
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
    if(bool(request&32u)!=ben10::albedo_hud::enabled.load())ToggleAlbedoHud(ctx,base);
    if(bool(request&64u)!=background_controller_input.load()) {
      auto* host=runtime.load();
      try {
        if(host) {
          std::lock_guard guard(video_settings_mutex);
          SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","background_controller_input",
              request&64u?"on":"off");
          background_controller_input=bool(request&64u);
        }
      }catch(const std::exception& error){REXLOG_ERROR("Could not save background controller input: {}",error.what());}
    }
    if(bool(request&128u)!=transformation_animation_enabled.load()) {
      if(auto* host=runtime.load())try {
        std::lock_guard guard(video_settings_mutex);
        SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","transformation_animation",request&128u?"on":"off");
        transformation_animation_enabled=bool(request&128u);
      }catch(const std::exception& error){REXLOG_ERROR("Could not save Transformation Animation: {}",error.what());}
    }
    snapshot=(snapshot.load()&7u)|
        (ben10::albedo_hud::enabled.load()?32u:0u)|(background_controller_input.load()?64u:0u)|
        (transformation_animation_enabled.load()?128u:0u);
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
namespace menu_mouse {
// Called from the stock menu input routine (menu.ds 0x4226eb33) each frame.
// Menu_AddOption centres row N at anchor-(N-1)*.075 in the overlay's y-up
// space; AlignPauseMenu compacts the pause menu to .066 per row.
inline std::atomic<uint64_t> last_poll{0};
inline POINT last_cursor{}; // Guest script thread only.
inline bool button_down=false;
inline bool click=false;
inline uint64_t wheel_last_poll=0;
inline int pending_row=0; // Clicked row still waiting for the glow to arrive.
inline uint64_t pending_since=0;
inline bool Active() { return GetTickCount64()-last_poll.load(std::memory_order_relaxed)<600; }
inline bool Argument(uint8_t* base,unsigned index,float& value) {
  // Same argument block as sound_preview::Capture: receiver first, 8 bytes each.
  uint32_t encoded;
  std::memcpy(&encoded,base+0x826F8688,sizeof(encoded));
  const auto arguments=_byteswap_ulong(encoded);
  if(!arguments || arguments>UINT32_MAX-64)return false;
  const uint32_t slot=arguments+index*8;
  if(base[slot]!=0 || base[slot+1]!=2)return false;
  std::memcpy(&encoded,base+slot+4,sizeof(encoded));
  const auto bits=_byteswap_ulong(encoded);
  std::memcpy(&value,&bits,sizeof(value));
  return std::isfinite(value);
}
inline bool CursorInClient(rex::ui::Window* current,POINT& cursor,RECT& client) {
  const auto handle=static_cast<HWND>(current->GetNativeWindowHandle());
  return GetForegroundWindow()==handle && GetCursorPos(&cursor) && ScreenToClient(handle,&cursor) &&
      GetClientRect(handle,&client) && PtInRect(&client,cursor) && client.right>0 && client.bottom>0;
}
inline bool PrimaryButtonDown() {
  return (GetAsyncKeyState(GetSystemMetrics(SM_SWAPBUTTON)?VK_RBUTTON:VK_LBUTTON)&0x8000)!=0;
}
inline int Row(uint8_t* base) {
  // Longer than the glow slide, which pauses these polls while it locks input.
  const bool resumed=GetTickCount64()-last_poll.load(std::memory_order_relaxed)>1000;
  last_poll=GetTickCount64();
  click=false;
  const bool down=PrimaryButtonDown();
  const bool pressed=down && !button_down;
  button_down=down;
  // Wheel screens keep a stock list menu updating underneath them; it is not
  // on screen, so it must not follow the pointer.
  if(GetTickCount64()-wheel_last_poll<250)return 0;
  float count=0,selected=0,anchor=0;
  auto* current=window.load();
  if(resumed || GetTickCount64()-pending_since>1000)pending_row=0;
  if(!current || ben10_pc_video::CapturesGameInput() || !Argument(base,1,count) ||
      !Argument(base,2,selected) || !Argument(base,3,anchor))return 0;
  // The stock glow locks input while it slides; the script polls again once it lands.
  if(pending_row && pending_row==int(selected)) {
    pending_row=0;
    click=true;
    return 0;
  }
  POINT cursor{};
  RECT client{};
  if(!CursorInClient(current,cursor,client))return 0;
  // A menu that just opened keeps its stock selection until the mouse moves.
  const bool moved=!resumed && (cursor.x!=last_cursor.x || cursor.y!=last_cursor.y);
  last_cursor=cursor;
  if(!moved && !pressed)return 0;
  // Overlay x spans a centred 4:3 frame; y spans the full height, upward.
  const float aspect=float(client.right)/float(client.bottom);
  const float x=.5f+(float(cursor.x)/float(client.right)-.5f)*aspect*.75f;
  const float y=1.0f-float(cursor.y)/float(client.bottom);
  const float pitch=std::fabs(anchor-.546875f)<1e-4f?.060f:.075f;   // compact pause menu (seven rows with Photo Mode)
  const int row=int(std::lround((anchor-y)/pitch))+1;
  if(pressed)REXLOG_INFO("Cosmic menu mouse: client {}x{} cursor {},{} overlay {:.3f},{:.3f} anchor {:.3f} row {}/{}",
      client.right,client.bottom,cursor.x,cursor.y,x,y,anchor,row,int(count));
  if(x<.15f || x>.85f)return 0;
  if(row<1 || row>int(count))return 0;
  if(row==int(selected)) {
    click=pressed;
    return 0;
  }
  if(pressed) {
    pending_row=row;
    pending_since=GetTickCount64();
  }
  return row;
}
inline void Poll(PPCContext& ctx,uint8_t* base) { ReturnNumber(ctx,base,float(Row(base))); }
inline void Click(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,click?1.0f:0.0f);
  click=false;
}

// Level Select wheel (misscr.ds 0x05cd2401): slots are placed by angle around
// the wheel centre, 90 degrees = up, the same convention as the stick angle.
inline POINT wheel_cursor{};
inline bool wheel_button=false;
inline bool wheel_click=false;
inline uint64_t button_seen=0;
// Radius 0: Level Select passes only its centre (radius .225).
// True while an alien wheel screen (R3 roster, Upgrade Forms, Level Select) is on screen: it polls every frame.
inline bool WheelOpen() { return GetTickCount64()-wheel_last_poll<400; }
inline float WheelAngle(uint8_t* base,bool has_radius) {
  const auto now=GetTickCount64();
  const bool resumed=now-wheel_last_poll>1000;
  wheel_last_poll=now;
  last_poll=now;
  const bool down=PrimaryButtonDown();
  const bool pressed=down && !wheel_button;
  wheel_button=down;
  if(down)button_seen=now;
  float center_x=0,center_y=0;
  auto* current=window.load();
  POINT cursor{};
  RECT client{};
  float radius=.225f;
  if(!current || ben10_pc_video::CapturesGameInput() || !Argument(base,1,center_x) ||
      !Argument(base,2,center_y) || (has_radius && !Argument(base,3,radius)) ||
      !CursorInClient(current,cursor,client))return -1;
  const bool moved=!resumed && (cursor.x!=wheel_cursor.x || cursor.y!=wheel_cursor.y);
  wheel_cursor=cursor;
  if(!moved && !pressed)return -1;
  // Overlay x spans the full width here; measure in height units so the ring is round.
  const float aspect=float(client.right)/float(client.bottom);
  const float dx=(float(cursor.x)/float(client.right)-center_x)*aspect;
  const float dy=1.0f-float(cursor.y)/float(client.bottom)-center_y;
  const float distance=std::hypot(dx,dy);
  float angle=std::atan2(dy,dx)*57.29578f;
  if(angle<0)angle+=360;
  if(pressed)REXLOG_INFO("Cosmic wheel mouse: client {}x{} cursor {},{} angle {:.1f} distance {:.3f}",
      client.right,client.bottom,cursor.x,cursor.y,angle,distance);
  if(distance<radius*.5f || distance>radius*1.8f)return -1;
  wheel_click|=pressed;
  return angle;
}
inline void WheelPoll(PPCContext& ctx,uint8_t* base) { ReturnNumber(ctx,base,WheelAngle(base,false)); }
inline void RingPoll(PPCContext& ctx,uint8_t* base) { ReturnNumber(ctx,base,WheelAngle(base,true)); }
// Left click doubles as a bound pad button; menus that act on it skip it
// while the button is down (and briefly after a click shorter than a frame).
inline void ButtonHeld(PPCContext& ctx,uint8_t* base) {
  const auto now=GetTickCount64();
  if(PrimaryButtonDown())button_seen=now;
  ReturnNumber(ctx,base,now-button_seen<250?1.0f:0.0f);
}
inline void WheelClick(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,wheel_click?1.0f:0.0f);
  wheel_click=false;
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
namespace ben_upgrades {
inline void SyncMasterControl(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  float tier,purchased;
  if(!menu_mouse::Argument(base,1,tier) || !menu_mouse::Argument(base,2,purchased) ||
      tier<0 || tier>ben10::upgrade_economy::matrix_max || tier!=std::floor(tier))return;
  const bool unlocked=tier>=ben10::upgrade_economy::master_control_tier;
  const bool hero_unlocked=tier>=4;
  if(hero_time_enabled!=hero_unlocked)hero_button_armed=false;
  hero_time_enabled=hero_unlocked;
  master_control_unlocked.store(unlocked,std::memory_order_relaxed);
}
// Which roster slots the wheels and Upgrade Forms ask about (slot as asked, form ID checked, purchased tier required).
inline void RosterTrace(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  float asked,form,tier,allowed;
  if(!menu_mouse::Argument(base,1,asked) || !menu_mouse::Argument(base,2,form) || !menu_mouse::Argument(base,3,tier) ||
     !menu_mouse::Argument(base,4,allowed))return;
  static int logged=0;
  if(logged++>400)return;
  REXLOG_INFO("Roster check: slot/form {} -> form ID {}, purchased level {}, allowed {}",int(asked),int(form),int(tier),int(allowed));
}
inline void TransformAnimationEnabled(PPCContext& ctx,uint8_t* base) {
  ReturnNumber(ctx,base,transformation_animation_enabled.load()?1.f:0.f);
}
inline void TransformAnimationPending(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  float value;
  if(menu_mouse::Argument(base,1,value) && (value==0 || value==1)) {
    const bool was=transformation_animation_pending.exchange(value==1,std::memory_order_relaxed);
    if(value==1 && !was) {
      if(auto* host=runtime.load()) {
        const auto path=host->user_data_root()/"ben-transform-select.wav";
        PlaySoundW(path.c_str(),nullptr,SND_FILENAME|SND_ASYNC|SND_NODEFAULT);
      }
    }
  }
}
inline std::atomic<uint64_t> last_tick{0};
inline std::atomic<unsigned> points{0}, health{0}, energy{0}, matrix{0}, purchase{0};
inline std::atomic<bool> open_request{false}, active{false};
// Set by the Cosmetics page; applied on the guest thread in Tick (same path as the old Gameplay switch).
inline std::atomic<bool> cosmetic_albedo_toggle{false};
inline bool y_held = false;
inline bool InUpgradeForms() {
  const auto time = last_tick.load();
  return time && GetTickCount64()-time < 300;
}
inline void Close() {
  purchase=0;
  active=false;
  y_held=true;
  ben10::text_overlay::upgrade_page_owns_text=false;
  {std::lock_guard guard(ben10::text_overlay::Lock());ben10::text_overlay::Entries().clear();}
  ben10_pc_video::release_guard=true;
  ben10_pc_video::visible=false;
}
// Same checked receiver conversion as the original CircularElement methods.
inline void ResizeHudArc(PPCContext& ctx,uint8_t* base) {
 ReturnNumber(ctx,base,0);
 float tier,energy;
 if(!menu_mouse::Argument(base,1,tier) || !menu_mouse::Argument(base,2,energy) ||
    tier<0 || tier>3 || tier!=std::floor(tier) || (energy!=0 && energy!=1))return;
 auto* host=runtime.load();if(!host)return;
 auto* resolve=host->function_dispatcher()->GetFunction(0x82237B00);if(!resolve)return;
 PPCContext local=ctx;local.r3.u64=0x1e90b321;resolve(local,base);
 const uint32_t object=local.r3.u32;
 if(!object || object>UINT32_MAX-116)return;
 if(ben10::text_overlay::Word(base,object)!=0x8201A02C)return;
 const auto vertices=ben10::text_overlay::Word(base,object+108);
 if(!vertices || vertices>UINT32_MAX-528)return;
 std::array<float,132> strip{};
 for(unsigned i=0;i<strip.size();++i)strip[i]=ben10::text_overlay::Real(base,vertices+i*4);
 if(!ben10::upgrade_arc::Rebuild(strip,ben10::text_overlay::Real(base,object+8),
       ben10::text_overlay::Real(base,object+12),unsigned(tier),energy==1))return;
 if(energy==1){ben10::upgrade_frame::energy=unsigned(tier);ben10::upgrade_arc::energy_object=object;}
 else {ben10::upgrade_frame::health=unsigned(tier);ben10::upgrade_arc::health_object=object;}
 // Guest-thread only, once on creation or a successful purchase; no polling.
 for(unsigned i=0;i<strip.size();++i){uint32_t bits;std::memcpy(&bits,&strip[i],4);
  bits=_byteswap_ulong(bits);std::memcpy(base+vertices+i*4,&bits,4);}
 ReturnNumber(ctx,base,ben10::upgrade_frame::ready?1.f:0.f);
}
inline void ShowHudFrame(PPCContext& ctx,uint8_t* base) {
 ReturnVoid(ctx,base);
 ben10::upgrade_frame::enabled=ben10::upgrade_frame::ready.load();
}
// The cosmetics the save owns (bit per item, in the order of ben10::cosmetics::Item). Anything not owned is switched off;
// one that has just been bought starts OFF.
inline bool albedo_preference=false, transform_preference=false;
inline void ApplyCosmetics(unsigned mask) {
  namespace cosmetics=ben10::cosmetics;
  auto* host=runtime.load();
  bool save=false;
  static bool first_sync=true;
  if(first_sync && mask) {
    // First report of this session: what the save owns gets back what the player had switched on.
    first_sync=false;
    for(unsigned i=0;i<cosmetics::Count;++i)cosmetics::owned[i]=(mask>>i)&1u;
    if(cosmetics::owned[cosmetics::Albedo])ben10::albedo_hud::enabled=albedo_preference;
    if(cosmetics::owned[cosmetics::Transform])transformation_animation_enabled=transform_preference;
    return;
  }
  for(unsigned i=0;i<cosmetics::Count;++i) {
    const bool own=(mask>>i)&1u;
    const bool was=cosmetics::owned[i].exchange(own);
    if(own==was)continue;
    if(own) {
      if(i==cosmetics::Realistic){cosmetics::realistic_on=false;save=true;}
      else if(i==cosmetics::Bolts){cosmetics::bolts_on=false;save=true;}
      else if(i==cosmetics::Transform){
        transformation_animation_enabled=false;
        if(host){std::lock_guard guard(video_settings_mutex);SaveVideoKey(host->user_data_root()/"pc-gameplay.ini","transformation_animation","off");}
      } else if(i==cosmetics::Albedo)ben10::albedo_hud::enabled=false;
    }
  }
  if(!cosmetics::owned[cosmetics::Albedo].load())ben10::albedo_hud::enabled=false;
  if(!cosmetics::owned[cosmetics::Transform].load())transformation_animation_enabled=false;
  if(save && host)ben10::cosmetics::Save(host->user_data_root());
}
inline void CosmeticsSync(PPCContext& ctx,uint8_t* base) {
  ReturnVoid(ctx,base);
  float mask;
  if(menu_mouse::Argument(base,1,mask) && mask>=0 && mask<16)ApplyCosmetics(unsigned(mask));
}
inline void Tick(PPCContext& ctx, uint8_t* base) {
  ReturnNumber(ctx,base,0);
  float balance,h,e,m,cosmetic_mask=-1;
  if(!menu_mouse::Argument(base,1,balance) || !menu_mouse::Argument(base,2,h) ||
     !menu_mouse::Argument(base,3,e) || !menu_mouse::Argument(base,4,m))return;
  if(menu_mouse::Argument(base,5,cosmetic_mask) && cosmetic_mask>=0 && cosmetic_mask<16)ApplyCosmetics(unsigned(cosmetic_mask));
  if(!(balance>=0 && balance<=16777216 && h>=0 && h<=3 && e>=0 && e<=3 &&
      m>=0 && m<=ben10::upgrade_economy::matrix_max))return;
  const bool continuing=InUpgradeForms();
  last_tick=GetTickCount64();
  static unsigned last_logged[4]={~0u,~0u,~0u,~0u};
  const unsigned now[4]={unsigned(balance),unsigned(h),unsigned(e),unsigned(m)};
  if(std::memcmp(last_logged,now,sizeof now)) {
    std::memcpy(last_logged,now,sizeof now);
    REXLOG_INFO("Upgrade state: points={}, health tier={}, energy tier={}, Ultimatrix level={}",now[0],now[1],now[2],now[3]);
  }
  points=unsigned(balance);
  health=unsigned(h);
  energy=unsigned(e);
  matrix=unsigned(m);
  master_control_unlocked.store(m>=ben10::upgrade_economy::master_control_tier,std::memory_order_relaxed);
  if(hero_time_enabled!=(m>=4))hero_button_armed=false;
  hero_time_enabled=m>=4;
  if(active.load()) {
    if(cosmetic_albedo_toggle.exchange(false))ToggleAlbedoHud(ctx,base);
    const auto action=purchase.exchange(0);
    if(action==64) {
      Close();
      ReturnNumber(ctx,base,1); // Consume Back here; do not pop the stock menu.
      return;
    }
    ReturnNumber(ctx,base,action?float(action):1.0f);
    return;
  }
  auto* host=runtime.load();
  auto* input=host?static_cast<rex::input::InputSystem*>(host->input_system()):nullptr;
  rex::input::X_INPUT_STATE state{};
  const bool down=input && ben10::photo::ReadGameState(input,state)==0 && (state.gamepad.buttons&0x8000);
  const bool open=open_request.exchange(false) || (continuing && down && !y_held);
  y_held=down;
  if(!open || ben10_pc_video::CapturesGameInput())return;
  active=true;
  ben10::text_overlay::upgrade_page_owns_text=true;
  {std::lock_guard guard(ben10::text_overlay::Lock());ben10::text_overlay::Entries().clear();}
  ben10_pc_video::controller_sample=0;
  ben10_pc_video::opening_guard=true;
  ben10_pc_video::visible=true;
  ReturnNumber(ctx,base,1);
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
  add("cosmic_photo_mode",PhotoModeFromPause);
  add("cosmic_preview_video",OpenVideoPreview);
  add("cosmic_options_open",options_hub::Open<false>);
  add("cosmic_options_open_credits",options_hub::Open<true>);
  add("cosmic_options_poll",options_hub::Poll);
  add("cosmic_ben_upgrade_menu_tick",ben_upgrades::Tick);
  add("cosmic_cosmetics_sync",ben_upgrades::CosmeticsSync,2);
  add("cosmic_master_control_sync",ben_upgrades::SyncMasterControl,3);
  add("cosmic_ben_transform_enabled",ben_upgrades::TransformAnimationEnabled);
  add("cosmic_ben_transform_pending",ben_upgrades::TransformAnimationPending,2);
  add("cosmic_ben_transform_delta",HeroTimeDelta);
  add("cosmic_ben_resize_hud_arc",ben_upgrades::ResizeHudArc,3);
  add("cosmic_ben_hud_frame_ready",ben_upgrades::ShowHudFrame);
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
  add("cosmic_index_language",ReadLanguage);
  add("cosmic_language_dirty",LanguageDirty);
  add("cosmic_cycle_language",CycleLanguage);
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
  ben10::text_overlay::UserDirectory()=host->user_data_root();
  // Temporary: Big Chill's glide landing calls a virtual function at 0x8211A5B8 that code discovery missed.
  // Log its original instructions (and its neighbours) from the loaded image.
  std::thread([host] {
    Sleep(15000);
    uint8_t* guest=host->memory()->virtual_membase();
    for(uint32_t at=0x8211A5A8;at<0x8211A5E8;at+=16) {
      uint32_t w[4];std::memcpy(w,guest+at,16);
      REXLOG_INFO("Guest code {:08X}: {:08X} {:08X} {:08X} {:08X}",at,_byteswap_ulong(w[0]),_byteswap_ulong(w[1]),_byteswap_ulong(w[2]),_byteswap_ulong(w[3]));
    }
  }).detach();
  ben10::language::current=ben10::language::IndexOf(ReadVideoSetting(host->user_data_root()/"pc-video.ini","language","en"));
  add("cosmic_wipe_progress",WipeProgress);
  add("cosmic_wipe_prompt",WipePrompt);
  {std::ifstream settings(host->user_data_root()/"pc-video.ini");std::string line;
    while(std::getline(settings,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();
      if(line=="performance_overlay=off")ben10::performance_visible=false;
      if(line=="performance_overlay=on")ben10::performance_visible=true;}}
  {std::ifstream settings(host->user_data_root()/"pc-gameplay.ini");std::string line;
    while(std::getline(settings,line)) {
      if(!line.empty() && line.back()=='\r')line.pop_back();
      if(line=="transformation_animation=on")transformation_animation_enabled=true;
      if(line=="transformation_animation=off")transformation_animation_enabled=false;
      if(line=="albedo_hud_preview=on")ben10::albedo_hud::enabled=true;
      if(line=="albedo_hud_preview=off")ben10::albedo_hud::enabled=false;
      if(line=="background_controller_input=on")background_controller_input=true;
      if(line=="background_controller_input=off")background_controller_input=false;
      if(line=="show_hud=off")ben10::photo::show_hud=false;
      if(line=="show_hud=on")ben10::photo::show_hud=true;
    }}
  // Cosmetics are bought in the Upgrades menu: Albedo and the transformation animation stay off until owned.
  ben10::cosmetics::Load(host->user_data_root());
  // What the player had switched on is kept; ownership comes from the save and is applied by the first script sync.
  ben10_pc_menu::ben_upgrades::albedo_preference=ben10::albedo_hud::enabled.load();
  ben10_pc_menu::ben_upgrades::transform_preference=transformation_animation_enabled.load();
  ben10::albedo_hud::enabled=false;
  transformation_animation_enabled=false;
  std::error_code trace_marker_error;
  if (std::filesystem::is_regular_file(host->user_data_root()/"way-big-texture-trace.txt", trace_marker_error)) {
    ben10::albedo_textures::final_battle_trace_enabled.store(true);
    REXLOG_INFO("Way Big texture trace enabled");
  }
  ben10::albedo_textures::way_big_launch_albedo.store(ben10::albedo_hud::enabled.load());
  if (std::filesystem::is_regular_file(host->user_data_root()/"way-big-beam-trace.txt", trace_marker_error)) {
    ben10::albedo_textures::way_big_beam_trace_enabled.store(true);
    REXLOG_INFO("Way Big beam trace enabled");
  }
  add("cosmic_all_aliens_page",AllAliensPage);
  add("cosmic_mouse_pause_menu",PauseMenuCursor<true>);
  add("cosmic_mouse_resume_game",PauseMenuCursor<false>);
  add("cosmic_mouse_menu_poll",menu_mouse::Poll,4);
  add("cosmic_mouse_menu_click",menu_mouse::Click);
  add("cosmic_mouse_wheel_poll",menu_mouse::WheelPoll,3);
  add("cosmic_mouse_wheel_click",menu_mouse::WheelClick);
  add("cosmic_mouse_ring_poll",menu_mouse::RingPoll,4);
  add("cosmic_mouse_button_held",menu_mouse::ButtonHeld);
  if(std::getenv("BEN10_DISCORD_STATUS_FILE") || ben10::albedo_textures::final_battle_trace_enabled.load() ||
     ben10::albedo_textures::way_big_beam_trace_enabled.load()) {
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
  add("cosmic_roster_trace",ben_upgrades::RosterTrace,5);
  if(HeroTimeDiagnostic()) {
    add("cosmic_hero_enabled",HeroTimeEnabled);
    add("cosmic_toggle_hero_time",ToggleHeroTime);
    add("cosmic_hero_button",HeroTimeButton);
    add("cosmic_hero_delta",HeroTimeDelta);
    add("cosmic_hero_loaded",HeroTimeTrace<0>);
    add("cosmic_hero_active",HeroTimeTrace<1>);
    add("cosmic_ultimate_cannonbolt_voice",UltimateCannonboltVoice);
 add("cosmic_ultimate_way_big_request",UltimateWayBigRequest,2);
 if (ben10::ultimate_way_big::separate_form)
   add("cosmic_ultimate_way_big_form_trace",TraceWayBigForm,2);
 add("cosmic_ultimate_way_big_reset",UltimateWayBigReset);
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
