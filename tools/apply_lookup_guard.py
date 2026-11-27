"""Apply the released-package lookup guards (native-rex/src/lookup_guard.h) to locally generated game code, idempotently.

Run after tools/apply_game_integration.py. Locates the functions by name; adds one authored early-out before each call into
the package hash-map index routine (sub_821A2E90 / sub_821A2E78).
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generated', type=Path, required=True)
args = parser.parse_args()

INCLUDE = '#include "../../src/lookup_guard.h"\n'
GUARDS = (
    # Lookup of a key: "not found" returns 0 and the caller tries the next package.
    ('sub_8219D398', 'ctx.lr = 0x8219D3C8;',
     'if (ben10::lookup_guard::StaleMap(base, ctx.r3.u32, ctx.r4.u32)) { ctx.r3.s64 = 0; ctx.r1.s64 = ctx.r1.s64 + 128; '
     '__restgprlr_28(ctx, base); return; }\n\t'),
    # Diagnostic: which package answers each lookup (the guard above, around the call into sub_8219B690).
    ('sub_821AD188', 'ctx.lr = 0x821AD1D0;', 'ben10::lookup_guard::Package(ctx.r11.u32);\n\t'),
    ('sub_821AD188', 'loc_821AD1D0:\n', 'ben10::lookup_guard::Result(ctx.r30.u32, ctx.r29.u32, ctx.r3.u32);\n', True),
    # Walk over a package's entries with a callback: a stale package has none, so its entries are skipped.
    ('sub_8219D5A0', 'ctx.lr = 0x8219D5F8;',
     'if (ben10::lookup_guard::StaleMap(base, ctx.r3.u32, ctx.r4.u32)) goto loc_8219D65C;\n\t'),
)
for name, before, guard, *after in GUARDS:
    marker = 'DEFINE_REX_FUNC(' + name + ') {'
    found = [p for p in args.generated.glob('*.cpp') if marker in p.read_text()]
    if len(found) != 1:
        raise RuntimeError('Expected exactly one generated ' + name)
    path = found[0]
    text = path.read_text()
    start = text.index(marker)
    end = text.find('DEFINE_REX_FUNC(', start + 1)
    body = text[start:end if end >= 0 else len(text)]
    if guard in body:
        print(name, 'lookup guard already applied.')
        continue
    at = text.index(before, start) + (len(before) if after else 0)
    text = text[:at] + guard + text[at:]
    if INCLUDE not in text:
        first = text.index('\n') + 1
        text = text[:first] + INCLUDE + text[first:]
    path.write_text(text)
    print(name, 'lookup guard applied.')
