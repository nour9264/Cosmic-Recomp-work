"""Apply the HUD arc observer hook to locally generated game code, idempotently.

  sub_82227C58  HUD arc draw (CircularElement): reports the arc's fill ratio and fill-texture key to
                ben10::upgrade_arc::ObserveArc, which the Ben upgrade overlay uses to paint the green track under the
                extended part of the health and energy arcs.

Contains the patch location and the authored call, never an original function body.
Run after rexglue codegen (apply_game_integration.py calls it) and before compiling the consumer.
"""
from generated_functions import locate_functions

HEADER = '#include "../../src/ben_upgrade_arc.h"\n'
NAME = 'sub_82227C58'
HOOK = '\tben10::upgrade_arc::ObserveArc(ctx.r3.u32, base);\n'


def apply(generated):
    path = locate_functions(generated, [NAME])[NAME]
    text = path.read_text()
    start = text.index(f'DEFINE_REX_FUNC({NAME}) {{')
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    end = len(text) if end < 0 else end
    body = text[start:end]
    changed = 0
    if HOOK not in body:
        marker = 'REX_FUNC_PROLOGUE();\n'
        if body.count(marker) != 1:
            raise RuntimeError(f'Unexpected generated body for {NAME}')
        text = text[:start] + body.replace(marker, marker + HOOK) + text[end:]
        changed = 1
    if HEADER not in text:
        text = HEADER + text
        changed = 1
    if changed:
        path.write_text(text)
    return changed
