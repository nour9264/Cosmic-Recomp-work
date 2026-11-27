"""Apply the Goop bone-pose dump (diagnostic) to locally generated game code, idempotently.

Run after tools/apply_form_effects.py. While Goop is the player's form, every 90th call of sub_82148DF0 scans the character
for its array of bone matrices and logs it (native-rex/src/pose_scan.h), at most 3 times, so his real poses can be compared
with the animation clip data.
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generated', type=Path, required=True)
args = parser.parse_args()

IDS = [31, 32, 33, 1, 18, 19, 173, 174, 179, 180, 37, 38, 39, 136, 40, 41, 42, 44, 45, 47, 48, 50, 51, 135, 197, 56, 57,
       58, 152, 59, 60, 61, 63, 64, 66, 67, 69, 70, 151, 203, 204, 75, 76, 140, 77, 78, 139, 93, 94, 156, 95, 96, 155,
       193, 16774901]
assert len(IDS) == 55

STATIC = '''// Cosmic (diagnostic): finds and logs Goop's array of bone matrices (native-rex/src/pose_scan.h).
static void CosmicBoneDump(PPCContext& ctx, uint8_t* base) {
	static uint32_t calls = 0;
	const uint32_t character = ctx.r3.u32;
	if (!ben10::orb_hands::Ok(character)) return;
	const uint32_t weapon = REX_LOAD_U32(character + 776 + 16);
	if (!ben10::orb_hands::Ok(weapon) || REX_LOAD_U32(weapon + 8) != 0xF9DFC8A3u) return;
	ben10::pose_scan::Override(base, character);
	if (++calls % 90 != 1) return;
	ben10::pose_scan::Scan(base, character);
}

'''

marker = 'DEFINE_REX_FUNC(sub_82148DF0) {'
found = [p for p in args.generated.glob('*.cpp') if marker in p.read_text()]
if len(found) != 1:
    raise RuntimeError('Expected exactly one generated sub_82148DF0')
path = found[0]
text = path.read_text()
if 'CosmicBoneDump' in text:
    print('Bone dump already applied.')
else:
    anchor = '\tCosmicOrbHands(ctx, base);\n'
    if text.count(anchor) != 1:
        raise RuntimeError('Run tools/apply_form_effects.py first')
    text = text.replace(anchor, anchor + '\tCosmicBoneDump(ctx, base);\n')
    start = text.index(marker)
    text = text[:start] + STATIC + text[start:]
    inc = '#include "../../src/pose_scan.h"
'
    if inc not in text:
        text = text[:text.index('
') + 1] + inc + text[text.index('
') + 1:]
    path.write_text(text)
    print('Bone dump applied.')
