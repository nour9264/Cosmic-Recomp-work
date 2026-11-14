"""Apply the Arabic/Russian/Japanese text overlay hooks to locally generated game code, idempotently.

Run after tools/apply_game_integration.py. Locates the reviewed functions by name (generated unit numbers differ
between generations) and adds only authored calls into native-rex/src/text_overlay.h; no original bodies are stored.
"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--generated', type=Path, required=True)
args = parser.parse_args()
INCLUDE = '#include "../../src/text_overlay.h"\n'


def function_file(name):
    marker = 'DEFINE_REX_FUNC(' + name + ') {'
    found = [p for p in args.generated.glob('*.cpp') if marker in p.read_text()]
    if len(found) != 1:
        raise RuntimeError('Expected exactly one generated ' + name)
    return found[0], marker


def patch(name, edit):
    path, marker = function_file(name)
    text = path.read_text()
    start = text.index(marker)
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    if end < 0:
        end = len(text)
    body = edit(text[start:end])
    if body is None:
        return
    text = text[:start] + body + text[end:]
    if INCLUDE not in text:
        first = text.index('\n') + 1
        text = text[:first] + INCLUDE + text[first:]
    path.write_text(text)


def menu_text(body):  # sub_8221F328: every menu text object
    if 'ben10::text_overlay::Blank' in body:
        return None
    needle = 'ben10::albedo_textures::PromptDraw prompt(base + ctx.r3.u32 + 124);'
    if body.count(needle) != 1:
        raise RuntimeError('Unexpected sub_8221F328 body')
    return body.replace(needle, needle + '\n\tben10::text_overlay::Blank og_text(base, ctx.r3.u32);')


def title_text(body):  # sub_821C0120: the title screen's prompt
    if 'ben10::text_overlay::TitleDraw' in body:
        return None
    needle = '\tsub_821C6B20(ctx, base);'
    if body.count(needle) != 1:
        raise RuntimeError('Unexpected sub_821C0120 body')
    call = ('\tben10::text_overlay::TitleDraw(base, ctx.r1.u32 + 100, ctx.f1.f64, ctx.f2.f64, ctx.f3.f64, ctx.f4.f64, '
            'ctx.f5.f64, ctx.f6.f64, ctx.f7.f64, ctx.f8.f64);\n')
    return body.replace(needle, call + needle)


def dialogue(body):  # sub_821E81D8: dialogue and tip boxes
    if 'ben10::text_overlay::DialogueBlank' in body:
        return None
    needle = '\tsub_821C6C80(ctx, base);'
    if body.count(needle) != 1:
        raise RuntimeError('Unexpected sub_821E81D8 body')
    block = ('\t{\n\t\tben10::text_overlay::DialogueBlank og_dialogue(base, ctx.r27.u32, ctx.f1.f64, ctx.f2.f64, ctx.f3.f64);\n'
             '\t\tsub_821C6C80(ctx, base);\n\t}')
    return body.replace(needle, block)


def primitive(body):  # sub_821C62D8: the low-level string draw (HUD banners)
    if 'ben10::text_overlay::PrimitiveBlank' in body:
        return None
    needle = 'REX_FUNC_PROLOGUE();'
    if body.count(needle) != 1:
        raise RuntimeError('Unexpected sub_821C62D8 body')
    call = ('\n\tben10::text_overlay::PrimitiveBlank og_primitive(base, ctx.r1.u32, ctx.r9.u32, ctx.f1.f64, ctx.f2.f64, '
            'ctx.f3.f64, ctx.f4.f64, ctx.f5.f64, ctx.f6.f64);')
    return body.replace(needle, needle + call)


for name, edit in (('sub_8221F328', menu_text), ('sub_821C0120', title_text), ('sub_821E81D8', dialogue),
                   ('sub_821C62D8', primitive)):
    patch(name, edit)
print('Text overlay hooks applied.')
