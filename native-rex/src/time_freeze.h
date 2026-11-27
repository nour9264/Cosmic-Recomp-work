#pragma once
// Photo Mode time freeze: the guest asks the runtime for its timebase through rex::chrono::Clock::QueryGuestTickCount
// (imported from rexruntime.dll). While frozen we hand back the same tick count, so every delta the game measures is zero
// and its world stands still; on release the frozen span is subtracted so time resumes without a jump.
#include <windows.h>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <rex/logging.h>

namespace ben10::time_freeze {
inline std::atomic<bool> frozen{false};
inline uint64_t (*real_tick)() = nullptr;
inline std::mutex lock;
inline bool held = false;
inline uint64_t held_real = 0, skipped = 0;
inline std::atomic<unsigned> calls{0};

inline uint64_t HookedTick() {
  const uint64_t real = real_tick ? real_tick() : 0;
  calls.fetch_add(1, std::memory_order_relaxed);
  std::lock_guard guard(lock);
  if (frozen.load(std::memory_order_relaxed)) {
    if (!held) { held = true; held_real = real; }
    return held_real - skipped;
  }
  if (held) { skipped += real - held_real; held = false; }
  return real - skipped;
}

inline bool Install() {
  HMODULE exe = GetModuleHandleW(nullptr);
  auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(exe);
  auto* nt = reinterpret_cast<IMAGE_NT_HEADERS*>(reinterpret_cast<uint8_t*>(exe) + dos->e_lfanew);
  const auto dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
  if (!dir.VirtualAddress) return false;
  auto* desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(reinterpret_cast<uint8_t*>(exe) + dir.VirtualAddress);
  for (; desc->Name; ++desc) {
    auto* first = reinterpret_cast<IMAGE_THUNK_DATA*>(reinterpret_cast<uint8_t*>(exe) + (desc->OriginalFirstThunk ? desc->OriginalFirstThunk : desc->FirstThunk));
    auto* thunk = reinterpret_cast<IMAGE_THUNK_DATA*>(reinterpret_cast<uint8_t*>(exe) + desc->FirstThunk);
    for (; first->u1.AddressOfData; ++first, ++thunk) {
      if (IMAGE_SNAP_BY_ORDINAL(first->u1.Ordinal)) continue;
      auto* by_name = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(reinterpret_cast<uint8_t*>(exe) + first->u1.AddressOfData);
      if (!std::strstr(by_name->Name, "QueryGuestTickCount")) continue;
      DWORD old = 0;
      if (!VirtualProtect(&thunk->u1.Function, sizeof(void*), PAGE_READWRITE, &old)) return false;
      real_tick = reinterpret_cast<uint64_t (*)()>(thunk->u1.Function);
      thunk->u1.Function = reinterpret_cast<ULONGLONG>(&HookedTick);
      VirtualProtect(&thunk->u1.Function, sizeof(void*), old, &old);
      REXLOG_INFO("Photo mode: guest time hook installed ({})", by_name->Name);
      return true;
    }
  }
  REXLOG_INFO("Photo mode: guest time hook NOT installed");
  return false;
}
}  // namespace ben10::time_freeze
