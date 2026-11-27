#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <intrin.h>
namespace ben10::upgrade_arc {
inline std::atomic<uint32_t> health_object{0},energy_object{0};
inline std::atomic<float> health_fill{1.f},energy_fill{1.f};
inline void Observe(uint32_t object,float fill) {
 if(object==health_object.load(std::memory_order_relaxed))health_fill.store(fill,std::memory_order_relaxed);
 else if(object==energy_object.load(std::memory_order_relaxed))energy_fill.store(fill,std::memory_order_relaxed);
}
inline float Fraction(float value){return std::isfinite(value)?std::clamp(value,0.f,1.f):0.f;}
// Called from the HUD arc's draw with its guest object: the fill ratio at +88 (the float the game turns into a vertex count)
// feeds the overlay that paints the green track under the extended part of the bar. The fill texture key at +100
// identifies the health (orange) and energy (cyan) arcs.
inline void ObserveArc(uint32_t object,const uint8_t* base) {
 uint32_t raw=0,key=0;float fill=1.f;
 std::memcpy(&raw,base+object+88,4);raw=_byteswap_ulong(raw);std::memcpy(&fill,&raw,4);
 std::memcpy(&key,base+object+100,4);key=_byteswap_ulong(key);
 if(object==health_object.load(std::memory_order_relaxed) || key==0x8BAF8B68u)health_fill.store(fill,std::memory_order_relaxed);
 else if(object==energy_object.load(std::memory_order_relaxed) || key==0x747D478Cu)energy_fill.store(fill,std::memory_order_relaxed);
}
// CircularElement's existing strip has 33 pairs. Rebuild only positions:
// its radii, texture coordinates, fill ratio and all surrounding art stay intact.
inline bool Rebuild(std::array<float,132>& strip,float cx,float cy,unsigned tier,bool energy) {
 if(tier>3 || !std::isfinite(cx) || !std::isfinite(cy))return false;
 const float outer=std::hypot(strip[0]-cx,strip[1]-cy);
 const float inner=std::hypot(strip[2]-cx,strip[3]-cy);
 if(!std::isfinite(outer) || !std::isfinite(inner) || inner<=0 || outer<=0 || std::fabs(outer-inner)<1e-6f)return false;
 // Slightly tuck the fill under the diagonal silver caps. The inner
 // cap edge is about two degrees beyond its centre at higher tiers.
 const float extension=8.f*tier+(tier?2.f:0.f);
 const float start=energy?-53.f-extension:233.f+extension;
 const float end=energy?53.f+extension:127.f-extension;
 for(unsigned i=0;i<=32;++i){const float angle=(start+(end-start)*i/32.f)*3.14159265358979323846f/180.f;
  const float c=std::cos(angle),s=std::sin(angle);
  strip[i*4]=cx+outer*c;strip[i*4+1]=cy+outer*s;
  strip[i*4+2]=cx+inner*c;strip[i*4+3]=cy+inner*s;
 }
 return true;
}
}
