"""Apply the Chromastone/Goop special-attack effect hooks to locally generated game code, idempotently.

Run after tools/apply_game_integration.py. Locates functions by name. Adds only authored calls into
native-rex/src/orb_hands.h and slot_freeze.h; no original function bodies are stored here.
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generated', type=Path, required=True)
args = parser.parse_args()

STATICS = '''DECLARE_REX_FUNC(sub_82132F40);
DECLARE_REX_FUNC(sub_821A0760);
DECLARE_REX_FUNC(sub_821A0240);
// Cosmic: Energy Outburst orbs follow Chromastone's hands (native-rex/src/orb_hands.h).
static void CosmicOrbHands(PPCContext& ctx, uint8_t* base) {
	uint32_t nodes[2];
	const uint32_t character = ctx.r3.u32;
	uint32_t count = 2, first_bone = 97;  // Goop sprays with bone 98 (reaches 2.4 m forward in the log; bone 97 stays by his side)
	if (!ben10::orb_hands::Find(character, base, nodes)) {
		// Goop: the Acid Hose emitter rides his hand (bone 97).
		const bool found_goop = ben10::orb_hands::FindGoop(character, base, nodes[0]);
		if (!found_goop) return;
		count = 1;
		first_bone = 98;
	}
	const PPCRegister saved_gpr[9] = {ctx.r4, ctx.r5, ctx.r6, ctx.r7, ctx.r8, ctx.r9, ctx.r10, ctx.r11, ctx.r12};
	const PPCRegister saved_fpr[14] = {ctx.f0, ctx.f1, ctx.f2, ctx.f3, ctx.f4, ctx.f5, ctx.f6, ctx.f7, ctx.f8, ctx.f9, ctx.f10, ctx.f11, ctx.f12, ctx.f13};
	const auto saved_cr = std::array{ctx.cr0, ctx.cr1, ctx.cr6, ctx.cr7};
	const auto saved_ctr = ctx.ctr, saved_xer_ca = PPCRegister{};
	(void)saved_xer_ca;
	const uint32_t saved_r1 = ctx.r1.u32, saved_r3 = ctx.r3.u32;
	const uint64_t saved_lr = ctx.lr;
	for (uint32_t i = 0; i < count; ++i) {
		ctx.r1.u32 = saved_r1 - 160;
		const uint32_t out = ctx.r1.u32 + 32;
		ctx.r3.u32 = character;
		ctx.r4.u32 = first_bone + i;
		ctx.lr = 0x82148DF8;
		sub_82132F40(ctx, base);
		if (ctx.r3.u32 != 0) {
			ctx.r4.u32 = ctx.r3.u32;
			ctx.r5.u32 = character + 144;
			ctx.r3.u32 = out;
			ctx.lr = 0x82148DF8;
			sub_821A0760(ctx, base);
			float relative[16];
			ben10::orb_hands::Relative(base, out, character + 144, relative);
			if (!ben10::orb_hands::Sane(relative)) continue;
			for (int k = 0; k < 16; ++k) ben10::orb_hands::StoreF(base, nodes[i] + 16 + 4 * k, relative[k]);
			ben10::orb_hands::StoreF(base, nodes[i] + 16 + 60, 1.0f);
			const uint32_t flags = REX_LOAD_U32(nodes[i] + 160);
			REX_STORE_U32(nodes[i] + 160, flags | 256);
			if (count == 2) ben10::orb_hands::Log(i, relative, base, character + 144);
		}
	}
	ctx.r1.u32 = saved_r1;
	ctx.r3.u32 = saved_r3;
	ctx.lr = saved_lr;
	ctx.r4 = saved_gpr[0]; ctx.r5 = saved_gpr[1]; ctx.r6 = saved_gpr[2]; ctx.r7 = saved_gpr[3]; ctx.r8 = saved_gpr[4];
	ctx.r9 = saved_gpr[5]; ctx.r10 = saved_gpr[6]; ctx.r11 = saved_gpr[7]; ctx.r12 = saved_gpr[8];
	ctx.f0 = saved_fpr[0]; ctx.f1 = saved_fpr[1]; ctx.f2 = saved_fpr[2]; ctx.f3 = saved_fpr[3]; ctx.f4 = saved_fpr[4]; ctx.f5 = saved_fpr[5]; ctx.f6 = saved_fpr[6];
	ctx.f7 = saved_fpr[7]; ctx.f8 = saved_fpr[8]; ctx.f9 = saved_fpr[9]; ctx.f10 = saved_fpr[10]; ctx.f11 = saved_fpr[11]; ctx.f12 = saved_fpr[12]; ctx.f13 = saved_fpr[13];
	ctx.cr0 = saved_cr[0]; ctx.cr1 = saved_cr[1]; ctx.cr6 = saved_cr[2]; ctx.cr7 = saved_cr[3];
	ctx.ctr = saved_ctr;
}

DECLARE_REX_FUNC(sub_821E2680);
// Cosmic: a new gatling attack first sends each crystal group its stop event, so
// crystals of the previous attack still in the world are cleared before it starts.
static void CosmicClearCrystals(PPCContext& ctx, uint8_t* base) {
	const uint32_t node = REX_LOAD_U32(ctx.r29.u32 + 792);
	if (node < 0x10000) return;
	const uint32_t saved_r1 = ctx.r1.u32, saved_r3 = ctx.r3.u32, saved_r4 = ctx.r4.u32, saved_r5 = ctx.r5.u32;
	const uint64_t saved_lr = ctx.lr;
	for (uint32_t event : {0xE95FBF78u, 0x9E588FEEu, 0x0751DE54u, 0x773B2ADBu}) {
		ctx.r3.u32 = node;
		ctx.r4.u32 = event;
		ctx.r5.u32 = 1;
		ctx.lr = 0x82148E9C;
		sub_821E2680(ctx, base);
	}
	ctx.r1.u32 = saved_r1;
	ctx.r3.u32 = saved_r3;
	ctx.r4.u32 = saved_r4;
	ctx.r5.u32 = saved_r5;
	ctx.lr = saved_lr;
}

'''


def unit(name):
    marker = 'DEFINE_REX_FUNC(' + name + ') {'
    found = [p for p in args.generated.glob('*.cpp') if marker in p.read_text()]
    if len(found) != 1:
        raise RuntimeError('Expected exactly one generated ' + name)
    return found[0], marker


def add_include(text, header):
    line = '#include "../../src/' + header + '"\n'
    if line in text:
        return text
    first = text.index('\n') + 1
    return text[:first] + line + text[first:]


def replace_once(body, old, new, what):
    if body.count(old) != 1:
        raise RuntimeError('Unexpected generated body for ' + what)
    return body.replace(old, new)


# sub_8213A9A0: the specials root's matrix copy is skipped while the effects stay where they were.
path, marker = unit('sub_8213A9A0')
text = path.read_text()
if 'ben10::slot_freeze::Skip' not in text:
    start = text.index(marker)
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    end = len(text) if end < 0 else end
    body = text[start:end]
    body = replace_once(body, 'loc_8213ADD8:\n',
                        'loc_8213ADD8:\n\tben10::slot_freeze::Probe(ctx.r30.u32, ctx.r31.u32, base);\n'
                        '\tif (ben10::slot_freeze::Skip(ctx.r30.u32, base)) goto loc_8213ADEC;\n', 'sub_8213A9A0')
    body = replace_once(body, 'loc_8213ADEC:\n',
                        '\tben10::slot_freeze::RefreshGoop(base, REX_LOAD_U32(ctx.r31.u32 + 792));\nloc_8213ADEC:\n', 'sub_8213A9A0')
    text = add_include(text[:start] + body + text[end:], 'slot_freeze.h')
    path.write_text(text)

# sub_82148DF0: attack start/stop events for the character's weapon slots.
path, marker = unit('sub_82148DF0')
text = path.read_text()
if 'CosmicOrbHands' not in text:
    start = text.index(marker)
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    end = len(text) if end < 0 else end
    body = text[start:end]
    body = replace_once(body, '\tctx.r29.u64 = ctx.r3.u64;\n',
                        '\tctx.r29.u64 = ctx.r3.u64;\n\tCosmicOrbHands(ctx, base);\n', 'sub_82148DF0')
    body = replace_once(body, 'loc_82148E90:\n',
                        'loc_82148E90:\n\tif (ben10::slot_freeze::Event(ctx.r29.u32, ctx.r30.u32, ctx.r27.u32, true, base)) CosmicClearCrystals(ctx, base);\n',
                        'sub_82148DF0')
    body = replace_once(body, 'loc_82148EA8:\n',
                        'loc_82148EA8:\n\tben10::slot_freeze::Event(ctx.r29.u32, ctx.r30.u32, ctx.r27.u32, false, base);\n', 'sub_82148DF0')
    text = text[:start] + STATICS + body + text[end:]
    text = add_include(add_include(text, 'slot_freeze.h'), 'orb_hands.h')
    path.write_text(text)
print('Form effect hooks applied.')

# Ultimate Cannonbolt side intake uses the live ball bone pose, not the
# character-facing effect root. Keep this independently idempotent.
path, marker = unit('sub_8213A9A0')
text = path.read_text()
if 'ben10::ucb_suction::Refresh' not in text:
    start = text.index(marker)
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    end = len(text) if end < 0 else end
    body = text[start:end]
    body = replace_once(body, 'loc_8213ADEC:\n',
                        'loc_8213ADEC:\n\tben10::ucb_suction::Refresh(ctx, base, ctx.r31.u32, ctx.r26.u32);\n', 'UCB live ball attachment')
    path.write_text(add_include(text[:start] + body + text[end:], 'ucb_suction.h'))
