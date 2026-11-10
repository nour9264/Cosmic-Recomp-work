#pragma once

#include "albedo_hud.h"
#include "albedo_textures.h"
#include <rex/logging.h>

DECLARE_REX_FUNC(sub_821C3878);
DECLARE_REX_FUNC(sub_821C8100);

namespace ben10::way_big {

inline bool DrawReplacement(PPCContext& ctx, uint8_t* base, uint32_t source) {
  using namespace albedo_textures;
  // Query the stock resource registry without creating or owning a resource.
  // Geometry and its weighted vertex stream must come from the same model.
  // Keep the current fighter's pose buffer and the rest of the draw inputs.
  constexpr uint32_t ben = 0x288341a8, evil = 0x83cd783e;
  auto report = [](unsigned check, uint32_t observed, uint32_t expected) {
    static thread_local unsigned epoch = 0, checks = 0;
    const auto current = final_battle_trace_epoch.load(std::memory_order_relaxed);
    if (current != epoch) {
      epoch = current;
      checks = 0;
    }
    if (checks & (1u << check)) return;
    checks |= 1u << check;
    REXLOG_INFO("Way Big paired draw: pass={} check={} observed={:08X} expected={:08X}",
                current, check, observed, expected);
  };
  const auto target = source == ben ? evil : ben;
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
  if (!alternate || REX_LOAD_U32(alternate + 8) != target ||
      !(REX_LOAD_U8(alternate + 6) & 0x20)) {
    report(2, alternate, target);
    return false;
  }
  const auto model = REX_LOAD_U32(alternate + 20);
  if (!model || model == ctx.r3.u32) return false;
  PPCContext call = ctx;
  call.r3.u64 = target;
  sub_821C8100(call, base);
  const auto skin = call.r3.u32;
  const auto target_count = target == ben ? 2842u : 2914u;
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

inline void DrawModel(PPCContext& ctx, uint8_t* base) {
  using namespace albedo_textures;
  if (!ctx.r3.u32 || !ctx.r4.u32 ||
      !final_battle_active.load(std::memory_order_relaxed)) return;
  const auto count = REX_LOAD_U32(ctx.r4.u32 + 72);
  if (count != 2842u && count != 2914u) return;
  const auto source = count == 2842u ? 0x288341a8u : 0x83cd783eu;
  const bool launch_swapped = way_big_launch_albedo.load(std::memory_order_relaxed);
  const bool requested = albedo_hud::enabled.load(std::memory_order_relaxed) != launch_swapped;
  const bool substituted = requested && DrawReplacement(ctx, base, source);
  // The original roles own the attack effects. Select each role's palette
  // from the model we actually drew, including a rejected live substitution.
  const bool player = (source == 0x288341a8u) != launch_swapped;
  SetWayBigBeamAppearance(player, launch_swapped != substituted);
}

}  // namespace ben10::way_big
