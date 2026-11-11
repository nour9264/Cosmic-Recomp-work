#include "frame_cadence_audit.h"
#include "frame_metrics.h"
#include "frame_pacing_probe.h"
#include "pc_menu_bridge.h"
#include "keyboard_mouse_runtime.h"
#include "fov_runtime.h"
#include "music_session.h"
#include <rex/input/mnk/mnk_input_driver.h>
#include <atomic>
#include <algorithm>
#include <optional>
namespace {
std::atomic<uint64_t> submitted_frames{0};
std::mutex frame_mutex;
std::array<float,240> history{};
size_t next=0,count=0;
using Clock=std::chrono::steady_clock;
Clock::time_point previous{};
}
extern "C" void Ben10FilterGameInput(uint32_t status,uint32_t guest_state,uint8_t* base) {
  // X_INPUT_STATE: packet[4], buttons[2], LT[1], RT[1]. Keep the SDK's
  // raw controller state intact: the page selector must still see RT edges.
  if(status==0 && guest_state && ben10_pc_menu::all_aliens_enabled &&
     base[guest_state+6]>30)base[guest_state+7]=0;
  // Quick Music Overlay: View / Share (0x20), big-endian buttons at +4. During
  // gameplay the button belongs to the overlay and is hidden from the game; the
  // open overlay reads its own close press from the UI controller snapshot.
  static bool view_held=false;
  if(status==0 && guest_state) {
    const uint16_t buttons=uint16_t(base[guest_state+4]<<8|base[guest_state+5]);
    const bool view=(buttons&0x20)!=0;
    const bool gameplay=ben10_pc_menu::mission_active.load() && !ben10_pc_menu::pause_menu_active.load() &&
        !ben10_pc_video::visible.load();
    const bool owned=gameplay && ben10::music::CurrentSettings().integration;
    if(!view)ben10::music_overlay::view_latch=false;
    if(view && !view_held && owned && !ben10_pc_video::music_overlay.load() &&
       !ben10::music_overlay::view_latch.load())
      ben10::music_overlay::toggle_request=true;
    view_held=view;
    if(view && owned) {
      const uint16_t kept=buttons&~0x20;
      base[guest_state+4]=uint8_t(kept>>8);
      base[guest_state+5]=uint8_t(kept);
    }
  }
}
extern "C" int Ben10MouseCameraStick(double* x,double* y) {
  // The camera turns at stick x its own top speed for the frame. Supplying
  // pixels / frame time makes the turn proportional to the distance moved,
  // as with a PC mouse, independent of frame rate. The poll applies it
  // without the stick dead zone.
  static auto last=Clock::now();
  const auto now=Clock::now();
  const double seconds=std::clamp(std::chrono::duration<double>(now-last).count(),1.0/240,1.0/10);
  last=now;
  float dx=0,dy=0;
  if(!rex::input::mnk::ConsumeDirectMouseLook(dx,dy))return 0;
  const auto settings=ben10::controls::active_custom.load();
  constexpr double kStickSecondsPerPixel=0.0008;
  const double scale=(settings?settings->sensitivity:1.0)*kStickSecondsPerPixel/seconds;
  *x=dx*scale;
  *y=dy*scale;
  static bool logged=false;
  if(!logged){logged=true;REXLOG_INFO("Direct mouse look active: {:.1f},{:.1f} px -> stick {:.3f},{:.3f}",dx,dy,*x,*y);}
  return 1;
}
namespace { thread_local std::optional<ben10::fov::Scope> fov_scope; }
extern "C" void Ben10FovBegin(uint8_t* base,uint32_t source,uint32_t vectors) {
  fov_scope.emplace(base,source,vectors);
}
extern "C" void Ben10FovEnd() {
  fov_scope.reset();
}
extern "C" void Ben10FrameSubmitted() {
  auto& audit=ben10_cadence::audit;
  const auto entry=audit.output?ben10_cadence::Clock::now():ben10_cadence::Clock::time_point{};
  ben10_pc_menu::OnFrame();
  const auto before_wait=audit.output?ben10_cadence::Clock::now():entry;
  ben10_pacing_probe::pacer.Wait();
  if(audit.output)audit.Record(entry,before_wait,ben10_cadence::Clock::now(),ben10_pacing_probe::pacer.rate());
  const auto now=Clock::now();
  std::lock_guard guard(frame_mutex);
  if(previous!=Clock::time_point{}) {
    history[next]=std::chrono::duration<float,std::milli>(now-previous).count();
    next=(next+1)%history.size();
    count=std::min(count+1,history.size());
  }
  previous=now;
  submitted_frames.fetch_add(1,std::memory_order_relaxed);
}
Ben10FrameStats Ben10ReadFrameStats() {
  Ben10FrameStats result;
  Clock::time_point latest;
  {
    std::lock_guard guard(frame_mutex);
    result.count=count;latest=previous;
    result.submitted_frames=submitted_frames.load(std::memory_order_relaxed);
    const size_t begin=(next+history.size()-count)%history.size();
    for(size_t i=0;i<count;++i)result.frame_times_ms[i]=history[(begin+i)%history.size()];
  }
  if(!result.count)return result;
  result.latest_ms=result.frame_times_ms[result.count-1];
  double duration=0;size_t samples=0;
  for(size_t i=result.count;i>0 && duration<1000;--i) {
    duration+=result.frame_times_ms[i-1];++samples;
  }
  if(duration>0 && Clock::now()-latest<std::chrono::seconds(1))result.fps=samples*1000.0/duration;
  auto sorted=result.frame_times_ms;
  std::sort(sorted.begin(),sorted.begin()+result.count);
  result.p95_ms=sorted[(result.count-1)*95/100];
  return result;
}
uint64_t Ben10SubmittedFrames() {
  return submitted_frames.load(std::memory_order_relaxed);
}
