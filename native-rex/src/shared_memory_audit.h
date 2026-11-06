#pragma once
// Opt-in attribution. Upload subtotals overlap request upload_inclusive.
#include <array>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <filesystem>
#include <fstream>
#ifdef _WIN32
#include <Windows.h>
#endif

namespace ben10_shared_audit {
using Clock = std::chrono::steady_clock;
enum Phase {ValidateMerge, Allocation, ScanSetup, LockWait, PageScan, Finish,
            UploadInclusive, PhaseCount};
enum Upload {PrepareCopy, RequestBuffer, MakeValid, Memcpy, Observe,
             RecordCopies, UploadCount};
inline constexpr const char* phase_names[] = {"validate_merge", "ensure_allocation",
    "scan_setup", "lock_wait", "page_scan", "finish", "upload_inclusive"};
inline constexpr const char* upload_names[] = {"prepare_copy", "request_buffer",
    "make_range_valid", "memcpy", "reuse_comparison", "record_copies"};
inline uint64_t ThreadCycles() {
#ifdef _WIN32
  ULONG64 cycles = 0;
  if (QueryThreadCycleTime(GetCurrentThread(), &cycles)) return cycles;
#endif
  return 0;
}
struct Totals {
  std::filesystem::path output;
  std::array<double, PhaseCount> phase_ms{};
  std::array<double, UploadCount> upload_ms{};
  uint64_t requests=0, ranges=0, requested_bytes=0, scanned_blocks=0;
  uint64_t upload_ranges=0, uploaded_bytes=0, valid_without_upload=0;
  uint64_t failed=0, thread_cycles=0, cycle_samples=0;
  double request_ms=0;
  Clock::time_point start=Clock::now();
  Totals() {
    if (const char* explicit_path=std::getenv("BEN10_SHARED_MEMORY_AUDIT")) {
      output=explicit_path;
    } else if (const char* phases=std::getenv("BEN10_CPU_DRAW_PHASES")) {
      const std::filesystem::path parent(phases);
      output=parent.parent_path()/("shared-memory-"+parent.filename().string());
    }
  }
  bool enabled() const {return !output.empty();}
  void Flush(Clock::time_point now) {
    if (!enabled() || now-start<std::chrono::seconds(5)) return;
    const auto timestamp=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    std::ofstream file(output,std::ios::app);
    file<<"{\"time_ms\":"<<timestamp<<",\"seconds\":"
        <<std::chrono::duration<double>(now-start).count()
        <<",\"requests\":"<<requests<<",\"input_ranges\":"<<ranges
        <<",\"requested_bytes\":"<<requested_bytes
        <<",\"scanned_64page_blocks\":"<<scanned_blocks
        <<",\"upload_ranges\":"<<upload_ranges<<",\"uploaded_bytes\":"<<uploaded_bytes
        <<",\"valid_without_upload\":"<<valid_without_upload<<",\"failed\":"<<failed
        <<",\"request_wall_ms\":"<<request_ms<<",\"request_thread_cycles\":"<<thread_cycles
        <<",\"cycle_samples\":"<<cycle_samples<<",\"request_phase_wall_ms\":{";
    for (unsigned i=0;i<PhaseCount;++i) {
      if(i)file<<',';file<<'"'<<phase_names[i]<<"\":"<<phase_ms[i];
    }
    file<<"},\"upload_subtotal_wall_ms\":{";
    for (unsigned i=0;i<UploadCount;++i) {
      if(i)file<<',';file<<'"'<<upload_names[i]<<"\":"<<upload_ms[i];
    }
    file<<"},\"scope\":\"Request phases are sequential wall times. Upload subtotals overlap upload_inclusive; do not add them. Cycles are thread cycles, not milliseconds. Timers and cycle queries add overhead.\"}\n";
    phase_ms.fill(0);upload_ms.fill(0);
    requests=ranges=requested_bytes=scanned_blocks=upload_ranges=uploaded_bytes=0;
    valid_without_upload=failed=thread_cycles=cycle_samples=0;request_ms=0;start=now;
  }
};
inline thread_local Totals totals;
struct Request {
  bool enabled=totals.enabled(), succeeded=false;
  Phase phase=ValidateMerge;
  Clock::time_point start{}, previous{};
  uint64_t cycles=0;
  explicit Request(size_t count) {
    if(enabled){start=previous=Clock::now();cycles=ThreadCycles();++totals.requests;totals.ranges+=count;}
  }
  void Mark(Phase next) {
    if(!enabled)return;
    const auto now=Clock::now();
    totals.phase_ms[phase]+=std::chrono::duration<double,std::milli>(now-previous).count();
    previous=now;phase=next;
  }
  ~Request() {
    if(!enabled)return;
    Mark(phase);const auto after=ThreadCycles();
    if(cycles && after>=cycles){totals.thread_cycles+=after-cycles;++totals.cycle_samples;}
    totals.request_ms+=std::chrono::duration<double,std::milli>(previous-start).count();
    if(!succeeded)++totals.failed;
    totals.Flush(previous);
  }
};
struct UploadSpan {
  Upload phase;bool enabled=totals.enabled();Clock::time_point start{};
  explicit UploadSpan(Upload value):phase(value){if(enabled)start=Clock::now();}
  ~UploadSpan(){if(enabled)totals.upload_ms[phase]+=std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
};
}
