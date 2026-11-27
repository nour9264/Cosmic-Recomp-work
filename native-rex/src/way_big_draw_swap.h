#pragma once

#include "albedo_hud.h"
#include "cosmetics_state.h"
#include "albedo_textures.h"
#include "frame_metrics.h"
#include "ultimate_way_big.h"
#include <rex/logging.h>

DECLARE_REX_FUNC(sub_821C3878);
DECLARE_REX_FUNC(sub_821C8100);
DECLARE_REX_FUNC(sub_82237FA0);

namespace ben10::way_big {

inline bool DrawReplacement(PPCContext& ctx, uint8_t* base, uint32_t source, uint32_t target, uint32_t target_count) {
  using namespace albedo_textures;
  // Query the stock resource registry without creating or owning a resource.
  // Geometry and its weighted vertex stream must come from the same model.
  // Keep the current fighter's pose buffer and the rest of the draw inputs.

  auto report = [target](unsigned check, uint32_t observed, uint32_t expected) {
    static thread_local unsigned epoch = 0, checks[3]{};
    const auto current = final_battle_trace_epoch.load(std::memory_order_relaxed);
    if (current != epoch) {
      epoch = current;
      for (auto& mask : checks) mask = 0;
    }
    auto& mask = checks[target == ultimate_way_big::kBenMesh ? 1 :
                        target == ultimate_way_big::kAlbedoMesh ? 2 : 0];
    if (mask & (1u << check)) return;
    mask |= 1u << check;
    REXLOG_INFO("Way Big paired draw: pass={} check={} observed={:08X} expected={:08X}",
                current, check, observed, expected);
  };

  auto lookup = [&](uint32_t id) {
    PPCContext call = ctx;
    call.r3.u64 = id;
    call.r4.u64 = 1;
    sub_821C3878(call, base);
    return call.r3.u32;
  };
  const auto original = lookup(source);
  if (!original || REX_LOAD_U32(original + 8) != source ||
      REX_LOAD_U32(original + 20) != ctx.r3.u32) {
    report(1, original ? REX_LOAD_U32(original + 20) : 0, ctx.r3.u32);
    return false;
  }
  const auto alternate = lookup(target);
  const bool custom = target == ultimate_way_big::kBenMesh || target == ultimate_way_big::kAlbedoMesh;
  if (!alternate || REX_LOAD_U32(alternate + 8) != target ||
      !(REX_LOAD_U8(alternate + 6) & (custom ? 0x30 : 0x20))) {
    report(2, alternate, target);
    return false;
  }
  const auto model = REX_LOAD_U32(alternate + 20);
  if (!model || model == ctx.r3.u32) return false;
  PPCContext call = ctx;
  call.r3.u64 = target;
  sub_821C8100(call, base);
  const auto skin = call.r3.u32;

  if (!skin || REX_LOAD_U32(skin + 72) != target_count ||
      REX_LOAD_U32(skin + 76) != target_count) {
    report(3, skin ? REX_LOAD_U32(skin + 72) : 0, target_count);
    return false;
  }
  ctx.r3.u64 = model;
  ctx.r4.u64 = skin;
  TraceWayBigDrawSwap(source, target);
  return true;
}

// Ben's mesh carries both wrist devices; its second draw range covers the green one
// (start 22914, 1044 indices) or, when Realistic Ultimatrix is on, the realistic one
// (start 23958, 6696 indices). The range is rewritten in the loaded model each draw.
constexpr uint16_t kGreenStart = 22914, kGreenCount = 1044, kGreenPieceCount = 3882, kRealStart = 26796, kRealCount = 6696, kRealPieceCount = 9534;

// Finds (start, count) of either device range inside [addr, addr + bytes); 0 when absent or unreadable.
inline uint32_t FindDeviceRange(uint8_t* base, uint32_t addr, uint32_t bytes) {
  __try {
    for (uint32_t o = 0; o + 4 <= bytes; o += 2) {
      const uint16_t a = REX_LOAD_U16(addr + o), b = REX_LOAD_U16(addr + o + 2);
      if ((a == kGreenStart && (b == kGreenCount || b == kGreenPieceCount)) || (a == kRealStart && (b == kRealCount || b == kRealPieceCount))) return addr + o;
    }
  } __except (1) {
    return 0;
  }
  return 0;
}

inline bool PlausibleGuestPointer(uint32_t v) { return v >= 0x10000000u && v < 0xE0000000u && !(v & 3); }

// The model object is not the file record: find where the loaded draw range lives once
// (inside the object, or inside a block it points to) and remember it relative to the object.
inline void BenDeviceRange(PPCContext& ctx, uint8_t* base) {
  const uint32_t model = ctx.r3.u32;
  static std::atomic<int> state{0};  // 0 = unknown, 1 = located, 2 = gave up
  static std::atomic<int> via{-1};   // -1 = inside the object, else the pointer's offset in the object
  static std::atomic<uint32_t> field{0};
  static std::atomic<unsigned> attempts{0};
  auto locate = [&]() -> uint32_t {
    uint32_t hit = FindDeviceRange(base, model, 4096);
    if (hit) { via = -1; field = hit - model; return hit; }
    for (uint32_t k = 0; k < 4096; k += 4) {
      const uint32_t target = REX_LOAD_U32(model + k);
      if (!PlausibleGuestPointer(target) || target == model) continue;
      hit = FindDeviceRange(base, target, 2048);
      if (hit) { via = int(k); field = hit - target; return hit; }
    }
    return 0;
  };
  if (state.load() == 2) return;
  if (state.load() == 0) {
    const uint32_t hit = locate();
    if (hit) {
      state = 1;
      REXLOG_INFO("Ben Ultimatrix range: found at {:08X} (model {:08X}, via {}, offset {})", hit, model, via.load(), field.load());
    } else {
      if (attempts.fetch_add(1) == 0) {
        REXLOG_INFO("Ben Ultimatrix range: not found in model {:08X}; first words:", model);
        for (uint32_t k = 0; k < 0x80; k += 16)
          REXLOG_INFO("  +{:03X}: {:08X} {:08X} {:08X} {:08X}", k, REX_LOAD_U32(model + k), REX_LOAD_U32(model + k + 4),
                      REX_LOAD_U32(model + k + 8), REX_LOAD_U32(model + k + 12));
      }
      if (attempts.load() > 40) state = 2;
      return;
    }
  }
  uint32_t address = 0;
  if (via.load() < 0) address = model + field.load();
  else address = REX_LOAD_U32(model + uint32_t(via.load())) + field.load();
  const uint16_t start = REX_LOAD_U16(address), count = REX_LOAD_U16(address + 2);
  const bool known = (start == kGreenStart && (count == kGreenCount || count == kGreenPieceCount)) || (start == kRealStart && (count == kRealCount || count == kRealPieceCount));
  if (!known) return;
  const bool realistic = cosmetics::realistic_on.load(std::memory_order_relaxed) &&
                         cosmetics::owned[cosmetics::Realistic].load(std::memory_order_relaxed);
  const bool bolts = cosmetics::bolts_on.load(std::memory_order_relaxed) &&
                     cosmetics::owned[cosmetics::Bolts].load(std::memory_order_relaxed);
  const uint16_t want_start = realistic ? kRealStart : kGreenStart;
  const uint16_t want_count = realistic ? (bolts ? kRealPieceCount : kRealCount) : (bolts ? kGreenPieceCount : kGreenCount);
  if (start == want_start && count == want_count) return;
  REX_STORE_U16(address, want_start);
  REX_STORE_U16(address + 2, want_count);
  REXLOG_INFO("Ben Ultimatrix range: {} device{}", realistic ? "realistic" : "green", bolts ? " + Bolts Tears" : "");
}

inline void DrawModel(PPCContext& ctx, uint8_t* base) {
  using namespace albedo_textures;
  if (ctx.r3.u32 && ctx.r4.u32 && REX_LOAD_U32(ctx.r4.u32 + 72) == 10089u && REX_LOAD_U32(ctx.r4.u32 + 76) == 10089u) {
    BenDeviceRange(ctx, base);
    return;
  }
  if (!ctx.r3.u32 || !ctx.r4.u32 ||
      !final_battle_active.load(std::memory_order_relaxed)) return;
  const auto count = REX_LOAD_U32(ctx.r4.u32 + 72);
  const bool form_ultimate = ultimate_way_big::separate_form &&
      count == ultimate_way_big::kVertices && REX_LOAD_U32(ctx.r4.u32 + 76) == count;
  if (count != 2842u && count != 2914u && !form_ultimate) return;
  const auto source = count == 2842u ? 0x288341a8u : 0x83cd783eu;
  const bool launch_swapped = way_big_launch_albedo.load(std::memory_order_relaxed);
  constexpr uint32_t ben = 0x288341a8, evil = 0x83cd783e;
  const bool player = form_ultimate || ((source == ben) != launch_swapped);
  const bool albedo = albedo_hud::enabled.load(std::memory_order_relaxed);
  if (player) {
    using namespace ultimate_way_big;
    if (separate_form) Ben10ObserveWayBigForm(form_ultimate);
    const auto frame = Ben10SubmittedFrames() + 1;
    const auto previous = player_frame.exchange(frame,std::memory_order_relaxed);
    const bool pressed = previous != frame && Ben10SampleWayBigL3();
    const bool preload = separate_form && !preload_requested.exchange(true,std::memory_order_relaxed);
    if (preload || (previous != frame && (pressed || checking_model.load(std::memory_order_relaxed)))) {
      // DScriptMgr::DelayedCall runs the VM work after the current game call.
      PPCContext call = ctx;
      call.r3.u64 = preload ? 0x46bf1d36 : 0x170e338a; // CosmicUltimateWayBigPreload / CosmicWayBigUpdate
      call.r4.u64 = 0;
      call.r5.u64 = 0;
      if (preload)
        REXLOG_INFO("Ultimate Way Big: queuing package preload on the first player draw");
      else if (pressed)
        REXLOG_INFO("Ultimate Way Big: submitting L3 request to the script queue");
      sub_82237FA0(call, base);
    }
    if (form_ultimate) {
      const bool loaded_albedo = form_albedo.load(std::memory_order_relaxed);
      if (loaded_albedo != albedo) {
        const auto loaded_mesh = loaded_albedo ? kAlbedoMesh : kBenMesh;
        const auto selected_mesh = albedo ? kAlbedoMesh : kBenMesh;
        DrawReplacement(ctx, base, loaded_mesh, selected_mesh, kVertices);
      }
      SetWayBigBeamAppearance(true, false);
      return;
    }
    const bool ultimate = active.load(std::memory_order_relaxed);
    if (!separate_form && (ultimate || checking_model.load(std::memory_order_relaxed))) {
      const auto mesh = albedo ? kAlbedoMesh : kBenMesh;
      PPCContext candidate = ctx;
      if (DrawReplacement(candidate, base, source, mesh, kVertices)) {
        if (!ready_frame[albedo].exchange(frame,std::memory_order_relaxed))
          REXLOG_INFO("Ultimate Way Big: mesh {:08X} drawable", mesh);
        if (ultimate) {
          ctx.r3 = candidate.r3;
          ctx.r4 = candidate.r4;
          SetWayBigBeamAppearance(true, false);
          return;
        }
      }
    }
  }
  const bool substituted = albedo != launch_swapped &&
      DrawReplacement(ctx, base, source, source == ben ? evil : ben, source == ben ? 2914u : 2842u);
  SetWayBigBeamAppearance(player, launch_swapped != substituted);
}

}  // namespace ben10::way_big
