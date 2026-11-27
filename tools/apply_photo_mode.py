"""Apply the Photo Mode hooks to locally generated game code, idempotently.

Contains patch locations and authored calls, never original function bodies.
Run after rexglue codegen (apply_game_integration.py calls it) and before compiling the consumer.

  sub_821A5898  projection builder: Photo Mode's camera, once per projection
  sub_821B6DC0  UI layer draw: skips the HUD layer while Photo Mode hides it, and records which layer is being drawn
  sub_8221BA60  UI layer item loop: skips the scene-light item while Photo Mode hides effects (T)
"""
import argparse
from pathlib import Path
from generated_functions import locate_functions

HEADER = '#include "../../src/photo_mode.h"\n'


def _body(text, name):
    start = text.index(f'DEFINE_REX_FUNC({name}) {{')
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    return start, (len(text) if end < 0 else end)


def _edit(path, name, edits):
    """edits: list of (marker proving it is applied, old text, new text); old must occur exactly once in the body."""
    text = path.read_text()
    start, end = _body(text, name)
    body = text[start:end]
    changed = 0
    for marker, old, new in edits:
        if marker in body:
            continue
        if body.count(old) != 1:
            raise RuntimeError(f'Unexpected generated body for {name}: {old.strip()!r} occurs {body.count(old)} times')
        body = body.replace(old, new)
        changed += 1
    if changed:
        text = text[:start] + body + text[end:]
    if HEADER not in text:
        text = HEADER + text
        changed = max(changed, 1)
    if changed:
        path.write_text(text)
    return changed


def apply(generated):
    paths = locate_functions(generated, ['sub_821A5898', 'sub_821B6DC0', 'sub_8221BA60'])
    changes = 0
    changes += _edit(paths['sub_821A5898'], 'sub_821A5898', [
        ('ben10::photo::OnCamera', 'REX_FUNC_PROLOGUE();\n',
         'REX_FUNC_PROLOGUE();\n\tben10::photo::OnCamera(ctx.r3.u32, base);\n')])
    changes += _edit(paths['sub_821B6DC0'], 'sub_821B6DC0', [
        ('HudLayerHidden', 'REX_FUNC_PROLOGUE();\n',
         'REX_FUNC_PROLOGUE();\n\tconst uint32_t layer_index = ctx.r4.u32;\n\tif (ben10::photo::HudLayerHidden(layer_index)) return;\n'),
        ('current_layer', '\tsub_8221BA60(ctx, base);\n\treturn;\n',
         '\tconst uint32_t outer_layer = ben10::photo::current_layer;\n\tben10::photo::current_layer = layer_index;\n'
         '\tsub_8221BA60(ctx, base);\n\tben10::photo::current_layer = outer_layer;\n\treturn;\n')])
    changes += _edit(paths['sub_8221BA60'], 'sub_8221BA60', [
        ('NoteItem', 'loc_8221BB70:\n',
         'loc_8221BB70:\n\tif (ben10::photo::NoteItem(ctx.r31.u32, base)) goto loc_8221BC20;\n')])
    return changes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generated', type=Path, required=True)
    print('Photo Mode hooks applied to', apply(parser.parse_args().generated), 'locally generated functions.')
