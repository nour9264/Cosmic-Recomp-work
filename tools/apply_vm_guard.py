"""Apply the script-VM object guard to locally generated game code, idempotently.

  sub_82239928  VM member-access opcode: the call to sub_82239138 gets the object reference from a script variable. When
                that variable holds a plain number (Ampfibian's weapon event) the call reads guest memory at number + 8 and
                the game dies. ben10::vm_guard::BadObject treats such a reference as "no object", as the VM already does
                for null, and logs it.

Contains the patch location and the authored call, never an original function body. apply_game_integration.py calls it.
"""
from generated_functions import locate_functions

HEADER = '#include "../../src/vm_guard.h"\n'
NAME = 'sub_82239928'
OLD = 'ctx.lr = 0x8223A320;\n\tsub_82239138(ctx, base);'
NEW = ('ctx.lr = 0x8223A320;\n\tif (ben10::vm_guard::BadObject(ctx.r3.u32, ctx.r4.u32, ctx.r31.u32)) { ctx.r3.u64 = 0; } '
       'else { sub_82239138(ctx, base); }')


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
