#pragma once
#include <Windows.h>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <intrin.h>
#include <rex/logging.h>
#include <rex/system/thread_state.h>

namespace ben10_fault_probe {
inline LONG CALLBACK Handler(EXCEPTION_POINTERS* exception) {
  if(exception->ExceptionRecord->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION ||
     exception->ExceptionRecord->NumberParameters<2)return EXCEPTION_CONTINUE_SEARCH;
  const auto address=exception->ExceptionRecord->ExceptionInformation[1];
  // The experiment's bad guest pointers fall in an unmapped virtual interval.
  // Do not report the SDK's ordinary protected physical-page notifications.
  const bool low_guest=(address>=0x100000000ULL && address<0x100010000ULL) ||
      (address>=0x200000000ULL && address<0x200010000ULL);
  const bool invalid_guest=address>=0x130000000ULL && address<0x180000000ULL;
  if(!low_guest && !invalid_guest)return EXCEPTION_CONTINUE_SEARCH;
  static thread_local bool reporting=false;if(reporting)return EXCEPTION_CONTINUE_SEARCH;
  reporting=true;
  auto report=[](void* pc,const char* label) {
    HMODULE module=nullptr;char name[MAX_PATH]{};
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                      reinterpret_cast<const char*>(pc),&module);
    if(module)GetModuleFileNameA(module,name,MAX_PATH);
    const char* file=std::strrchr(name,'\\');file=file?file+1:name;
    REXLOG_ERROR("Cosmic fault probe {}: {}+0x{:X}",label,file,
        reinterpret_cast<uintptr_t>(pc)-reinterpret_cast<uintptr_t>(module));
  };
  REXLOG_ERROR("Cosmic fault probe: invalid host access {:016X}",address);
  report(exception->ExceptionRecord->ExceptionAddress,"PC");
  if(auto* state=rex::runtime::ThreadState::Get()) {
    auto* c=state->context();
    REXLOG_ERROR("Cosmic fault PPC: LR={:08X}, CTR={:08X}, r1={:08X}, r3={:08X}, r4={:08X}, r5={:08X}, r6={:08X}, r7={:08X}, r8={:08X}",
      uint32_t(c->lr),c->ctr.u32,c->r1.u32,c->r3.u32,c->r4.u32,c->r5.u32,c->r6.u32,c->r7.u32,c->r8.u32);
    REXLOG_ERROR("Cosmic fault PPC: r9={:08X}, r10={:08X}, r11={:08X}, r12={:08X}, r27={:08X}, r28={:08X}, r29={:08X}, r30={:08X}, r31={:08X}",
      c->r9.u32,c->r10.u32,c->r11.u32,c->r12.u32,c->r27.u32,c->r28.u32,c->r29.u32,c->r30.u32,c->r31.u32);
    // The game's own call chain: each frame's back chain at [sp], the return address saved at [caller sp - 8].
    const auto* guest=reinterpret_cast<const uint8_t*>(0x100000000ULL);
    auto word=[&](uint32_t at) { uint32_t v;std::memcpy(&v,guest+at,4);return _byteswap_ulong(v); };
    char chain[400]{};size_t used=0;uint32_t sp=c->r1.u32;
    for(int i=0;i<18 && sp>=0x70000000u && sp<0x80000000u && used+12<sizeof(chain);++i) {
      const uint32_t next=word(sp);
      if(next<=sp || next>=0x80000000u)break;
      used+=std::snprintf(chain+used,sizeof(chain)-used,"%08X ",word(next-8));
      sp=next;
    }
    REXLOG_ERROR("Cosmic fault guest callers (innermost first): {}",chain);
    // The object the failing loop walks (r29 in the container iterator) and its data table.
    auto dump=[&](const char* label,uint32_t at,int words) {
      MEMORY_BASIC_INFORMATION info{};
      if(at<0x10000||!VirtualQuery(guest+at,&info,sizeof(info))||info.State!=MEM_COMMIT||(info.Protect&(PAGE_NOACCESS|PAGE_GUARD)) ||
         reinterpret_cast<uintptr_t>(guest+at)+words*4>reinterpret_cast<uintptr_t>(info.BaseAddress)+info.RegionSize)return;
      char text[600]{};size_t n=0;
      for(int i=0;i<words && n+12<sizeof(text);++i)n+=std::snprintf(text+n,sizeof(text)-n,"%08X ",word(at+4*i));
      REXLOG_ERROR("Cosmic fault memory {} {:08X}: {}",label,at,text);
    };
    dump("r29",c->r29.u32,24);
    {MEMORY_BASIC_INFORMATION info{};const uint32_t table=c->r29.u32>=0x10000&&VirtualQuery(guest+c->r29.u32,&info,sizeof(info))&&info.State==MEM_COMMIT?word(c->r29.u32+28):0;
     if(table)dump("r29+28 table",table,16);}
  }
  void* frames[24]{};const auto count=CaptureStackBackTrace(0,24,frames,nullptr);
  for(USHORT i=0;i<count;i++)report(frames[i],"stack");
  reporting=false;return EXCEPTION_CONTINUE_SEARCH;
}
inline void Install() {
  // Keep production crashes actionable too. This observer only reports invalid
  // guest pointers and always continues the normal exception dispatch; it does
  // not hide faults or intercept the SDK's protected physical-page tracking.
  static const auto installed=AddVectoredExceptionHandler(1,Handler);
  (void)installed;
}
}
