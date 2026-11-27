"""Apply the clip-play trace hooks (native-rex/src/anim_trace.h) to locally generated game code, idempotently.

Diagnostic only: one logging call at the start of sub_821335C8 (play a role) and of sub_821DE370 (the animation
controller's start-a-clip routine). Run after tools/apply_game_integration.py.
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generated', type=Path, required=True)
args = parser.parse_args()

HOOKS = (
    ('sub_821335C8', 'ben10::anim_trace::Play(base, uint32_t(ctx.lr), ctx.r3.u32, ctx.r4.u32, ctx.f1.f64);'),
    ('sub_821DE370', 'ben10::anim_trace::Controller(0x370, base, uint32_t(ctx.lr), ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, '
                     'ctx.r6.u32, ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32);'),
    ('sub_821DE588', 'ben10::anim_trace::Controller(0x588, base, uint32_t(ctx.lr), ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, '
                     'ctx.r6.u32, ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32);'),
    ('sub_821DE738', 'ben10::anim_trace::Controller(0x738, base, uint32_t(ctx.lr), ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, '
                     'ctx.r6.u32, ctx.r7.u32, ctx.r8.u32, ctx.r9.u32, ctx.r10.u32);'),
)
INCLUDE = '#include "../../src/anim_trace.h"\n'
for name, call in HOOKS:
    marker = 'DEFINE_REX_FUNC(' + name + ') {'
    found = [p for p in args.generated.glob('*.cpp') if marker in p.read_text()]
    if len(found) != 1:
        raise RuntimeError('Expected exactly one generated ' + name)
    path = found[0]
    text = path.read_text()
    if call in text:
        print(name, 'trace hook already applied.')
        continue
    start = text.index(marker)
    prologue = 'REX_FUNC_PROLOGUE();'
    at = text.index(prologue, start) + len(prologue)
    text = text[:at] + '\n\t' + call + text[at:]
    if INCLUDE not in text:
        first = text.index('\n') + 1
        text = text[:first] + INCLUDE + text[first:]
    path.write_text(text)
    print(name, 'trace hook applied.')
