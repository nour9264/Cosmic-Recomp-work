"""Guard the effect set-up that crashes when an effect instance could not be created.

  sub_821EA860  builds an effect instance (sub_822313C8) and initialises it with sub_821EDF18, which reads the instance's
                flag byte at +6. A null instance (seen on the double jump of Ultimate Swampfire) reads guest address 6 and
                the game dies. The code after the call already handles a null instance, so the call is skipped and
                ben10::effect_guard::Skipped logs it.

Contains the patch location and the authored call, never an original function body. apply_game_integration.py calls it.
"""
from generated_functions import locate_functions

HEADER = '#include "../../src/effect_guard.h"\n'
NAME = 'sub_821EA860'
OLD = 'ctx.lr = 0x821EA928;\n\tsub_821EDF18(ctx, base);'
NEW = ('ctx.lr = 0x821EA928;\n\tif (ctx.r3.u32 != 0) { sub_821EDF18(ctx, base); } '
       'else { ben10::effect_guard::Skipped(ctx.r29.u32); }')


def apply(generated):
    path = locate_functions(generated, [NAME])[NAME]
    text = path.read_text()
    start = text.index(f'DEFINE_REX_FUNC({NAME}) {{')
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    end = len(text) if end < 0 else end
    body = text[start:end]
    changed = 0
    if NEW not in body:
        if body.count(OLD) != 1:
            raise RuntimeError(f'Unexpected generated body for {NAME}')
        text = text[:start] + body.replace(OLD, NEW) + text[end:]
        changed = 1
    if HEADER not in text:
        text = HEADER + text
        changed = 1
    if changed:
        path.write_text(text)
    return changed
