#pragma once

#include "orb_hands.h"
#include "slot_freeze.h"
#include <cmath>

// Preserve the authored side air ribbons and their height animation.
// Resolve the current pose exactly like the engine's ordinary weapon bones,
// without changing the fifth weapon root (the ground effects use that root).
namespace ben10::ucb_suction {
inline void Refresh(PPCContext& ctx, uint8_t* base, uint32_t person, uint32_t actor_matrix) {
    if (!orb_hands::Ok(person) || !orb_hands::Ok(actor_matrix)) return;
    const uint32_t root = orb_hands::Load(base, person + 792);
    if (!orb_hands::Ok(root) || orb_hands::Load(base, root + 8) != 0x1b34d861u) return;
    int budget = 64;
    const uint32_t side = slot_freeze::FindKey(base, root, 0xc8ad2107u, 0, budget);
    if (!orb_hands::Ok(side)) return;

    PPCContext pose = ctx;
    pose.r1.u32 = ctx.r1.u32 - 160;
    const uint32_t world = pose.r1.u32 + 32;
    pose.r3.u32 = person;
    pose.r4.u32 = 0xc1; // Cannonbolt skeleton bone tag, not its array index.
    sub_82132F40(pose, base);
    if (!orb_hands::Ok(pose.r3.u32)) return;
    pose.r4.u32 = pose.r3.u32;
    pose.r5.u32 = actor_matrix;
    pose.r3.u32 = world;
    sub_821A0760(pose, base);

    float local[16];
    orb_hands::Relative(base, world, root + 16, local);
    if (!orb_hands::Sane(local)) return;
    // Keep the original visible mesh and its animated height. The ball's
    // bind-local Z axis is the lateral spike axis (bind rotates it to X).
    // Ignore rolling pitch and use only the live model's horizontal heading.
    const float axis_len = std::hypot(local[8], local[10]);
    if (axis_len < 0.5f) return;
    const float x = local[8]/axis_len, z = local[10]/axis_len;
    const float py = orb_hands::LoadF(base, side + 16 + 52);
    const float pz = orb_hands::LoadF(base, side + 16 + 56);
    const float px = orb_hands::LoadF(base, side + 16 + 48);
    const float matrix[16] = {x,0,z,0, 0,1,0,0, -z,0,x,0, px,py,pz,1};
    for (int i = 0; i < 16; ++i) {
        orb_hands::StoreF(base, side + 16 + 4*i, matrix[i]);
        float w = 0;
        for (int k = 0; k < 4; ++k)
            w += matrix[(i/4)*4+k] * orb_hands::LoadF(base, root+16+4*(k*4+i%4));
        orb_hands::StoreF(base, side + 80 + 4*i, w);
    }
    const uint32_t flags = orb_hands::Load(base, side + 160);
    const uint32_t be = _byteswap_ulong(flags | 256u);
    std::memcpy(base + side + 160, &be, 4);
    static std::atomic<int> reports{0};
    if (reports.fetch_add(1, std::memory_order_relaxed) < 8)
        REXLOG_INFO("UCB intake: live ball lateral axis {:.3f} {:.3f}, height {:.3f}", x, z, py);
}
}
