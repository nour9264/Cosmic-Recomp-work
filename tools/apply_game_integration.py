"""Apply authored PC integration to locally generated game code, idempotently.

Contains patch locations and authored changes, never original function bodies.
Run after rexglue codegen and before compiling the consumer.
"""
import argparse
import re
from pathlib import Path
from generated_functions import locate_functions

parser=argparse.ArgumentParser();parser.add_argument('--generated',type=Path,required=True);args=parser.parse_args()
changes=0
for name in ['sub_821ADC40','sub_82473060']:
 matches=[]
 for p in args.generated.glob('*.cpp'):
  text=p.read_text()
  marker='DEFINE_REX_FUNC('+name+') {'
  if marker in text:matches.append((p,text,text.index(marker)))
 if len(matches)!=1:raise RuntimeError('Expected exactly one generated '+name)
 p,text,start=matches[0];end=text.find('\nDEFINE_REX_FUNC(',start+1)
 if end<0:end=len(text)
 body=text[start:end]
 if name=='sub_821ADC40':
  old='ctx.r3.s64 = 41943040;';new='ctx.r3.s64 = 100663296;'
  if new in body:continue
  if 'ctx.r3.s64 = 67108864;' in body:old='ctx.r3.s64 = 67108864;'
 else:
  old='__imp__XamInputGetState(ctx, base);'
  new='const uint32_t cosmic_state=ctx.r5.u32;\n\t'+old+'\n\tBen10FilterGameInput(ctx.r3.u32,cosmic_state,base);'
  if 'Ben10FilterGameInput(' in body:continue
 if body.count(old)!=1:raise RuntimeError('Unexpected generated body for '+name)
 body=body.replace(old,new);p.write_text(text[:start]+body+text[end:]);changes+=1

# The frame hook registers native menus and applies the selected frame cap.
# Fresh codegen does not contain this authored integration automatically.
for p in args.generated.glob('*.cpp'):
    text=p.read_text()
    if 'DEFINE_REX_FUNC(sub_8248B2F0) {' not in text:continue
    start=text.index('DEFINE_REX_FUNC(sub_8248B2F0) {')
    end=text.find('\nDEFINE_REX_FUNC(',start+1)
    if end<0:end=len(text)
    body=text[start:end]
    if 'Ben10FrameSubmitted();' not in body:
        needle='__imp__VdSwap(ctx, base);'
        if body.count(needle)!=1:raise RuntimeError('Unexpected frame submission hook location')
        body=body.replace(needle,needle+'\n\tBen10FrameSubmitted();')
        p.write_text(text[:start]+body+text[end:]);changes+=1
    break
else:raise RuntimeError('Frame submission function missing from generated input')

from apply_callback_capacity import apply as expand_callbacks
from apply_resource_diagnostics import apply as add_diagnostics
changes+=expand_callbacks(args.generated)
changes+=add_diagnostics(args.generated)
p=locate_functions(args.generated,['sub_824868B8'])['sub_824868B8'];text=p.read_text()
start=text.index('DEFINE_REX_FUNC(sub_824868B8) {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'ben10_adaptive_spin::Poll' not in body:
    label='loc_824868D8:'
    assert body.count(label)==1
    if '__builtin_ia32_pause' not in body:
        body=body.replace(label,label+'\n\t__builtin_ia32_pause(); // Original loop and checks retained.')
    needle='ctx.r8.u64 = REX_LOAD_U32(ctx.r11.u32 + 0);'
    assert body.count(needle)==1
    body=body.replace(needle,needle+'\n\tben10_adaptive_spin::Poll(ctx.r31.u32,ctx.r8.u32);')
    text=text[:start]+body+text[end:]
    text='#include "../../src/adaptive_guest_spin.h"\n'+text
    p.write_text(text);changes+=1
p=locate_functions(args.generated,['sub_82156AF0'])['sub_82156AF0']
text=p.read_text()
start=text.index('DEFINE_REX_FUNC(sub_82156AF0) {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'BEN10_SKIP_INTRO' not in body:
    # This call belongs to the five-logo boot sequence. A null movie follows
    # the game's existing advance path and keeps the subsequent init state.
    needle='ctx.lr = 0x82156B94;\n\tsub_821A86B8(ctx, base);'
    if body.count(needle)!=1:raise RuntimeError('Unexpected startup logo playback call')
    replacement=('static const bool skip_intro = std::getenv("BEN10_SKIP_INTRO") != nullptr;\n'
                 '\tif (skip_intro) ctx.r3.u64 = 0;\n'
                 '\telse {\n\t\tctx.lr = 0x82156B94;\n\t\tsub_821A86B8(ctx, base);\n\t}')
    p.write_text('#include <cstdlib>\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1
hud_hooks={
    'sub_82227C58': (
        'ctx.lr = 0x82227D24;\n\tsub_824388E8(ctx, base);',
        '{\n\t\tben10::ultimate_hud::ForegroundBind foreground(ctx.r4.u32);\n'
        '\t\tctx.lr = 0x82227D24;\n\t\tsub_824388E8(ctx, base);\n\t}'),
    'sub_824846E0': (
        'REX_STORE_U32(ctx.r11.u32 + 12, ctx.r23.u32);',
        'REX_STORE_U32(ctx.r11.u32 + 12, ben10::ultimate_hud::FetchWord(ctx.r23.u32));'),
}
for name,p in locate_functions(args.generated,hud_hooks).items():
    text=p.read_text()
    start=text.index('DEFINE_REX_FUNC('+name+') {')
    end=text.find('\nDEFINE_REX_FUNC(',start+1)
    if end<0:end=len(text)
    body=text[start:end]
    if 'ben10::ultimate_hud::' in body:continue
    needle,replacement=hud_hooks[name]
    if body.count(needle)!=1:raise RuntimeError('Unexpected Ultimate HUD bind in '+name)
    p.write_text('#include "../../src/ultimate_hud_palette.h"\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1
albedo_hooks={
    'sub_824388E8': (
        'ctx.lr = 0x8243897C;\n\tsub_82441F48(ctx, base);',
        '{\n\t\tben10::albedo_hud::TextureBind texture(REX_LOAD_U32(ctx.r1.u32 + 140));\n'
        '\t\tctx.lr = 0x8243897C;\n\t\tsub_82441F48(ctx, base);\n\t}'),
    'sub_824846E0': (
        'ben10::ultimate_hud::FetchWord(ctx.r23.u32)',
        'ben10::albedo_hud::FetchWord(ben10::ultimate_hud::FetchWord(ctx.r23.u32))'),
}
for name,p in locate_functions(args.generated,albedo_hooks).items():
    text=p.read_text()
    start=text.index('DEFINE_REX_FUNC('+name+') {')
    end=text.find('\nDEFINE_REX_FUNC(',start+1)
    if end<0:end=len(text)
    body=text[start:end]
    if 'ben10::albedo_hud::' in body:continue
    needle,replacement=albedo_hooks[name]
    if body.count(needle)!=1:raise RuntimeError('Unexpected Albedo HUD bind in '+name)
    p.write_text('#include "../../src/albedo_hud.h"\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1
p=locate_functions(args.generated,['sub_824846E0'])['sub_824846E0']
text=p.read_text()
start=text.index('DEFINE_REX_FUNC(sub_824846E0) {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'ben10::albedo_textures::Apply' not in body:
    needle='REX_STORE_U32(ctx.r11.u32 + 20, ctx.r7.u32);'
    if body.count(needle)!=1:raise RuntimeError('Unexpected texture fetch address write')
    replacement=('{\n\t\tuint32_t texture_base = ctx.r3.u32, texture_mips = ctx.r7.u32;\n'
                 '\t\tben10::albedo_textures::Apply(ctx.r25.u32, ctx.r24.u32, texture_base, texture_mips);\n'
                 '\t\tREX_STORE_U32(ctx.r11.u32 + 4, texture_base);\n'
                 '\t\tREX_STORE_U32(ctx.r11.u32 + 20, texture_mips);\n\t}')
    p.write_text('#include "../../src/albedo_textures.h"\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1
# Trace the game method invoked by the original circdisp text helper.
# Use the game's own computed symbol IDs, without reading guest strings.
name='sub_82237E78'
p=locate_functions(args.generated,[name])[name]
text=p.read_text()
start=text.index('DEFINE_REX_FUNC('+name+') {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'TracePromptRenderer' not in body:
    needle='ctx.r28.u64 = REX_LOAD_U32(ctx.r3.u32 + 0);'
    if body.count(needle)!=1:raise RuntimeError('Unexpected script method registration')
    replacement=needle+'\n\tben10::albedo_textures::TracePromptRenderer(ctx.r23.u32, ctx.r28.u32, ctx.r25.u32);'
    p.write_text('#include "../../src/albedo_textures.h"\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1

# Remove the old preview's text-copy hooks from already generated code.
# The display mode is evaluated at draw time so existing text objects update.
for name, marker, call, next_branch in (
    ('sub_821FA3F0', 'KeyboardPrompt', '8245F9C8', '821fa4dc'),
    ('sub_8221F020', 'RewriteKeyboardPrompt', '8245E6F8', '8221f1bc'),
):
    p=locate_functions(args.generated,[name])[name]
    text=p.read_text()
    start=text.index('DEFINE_REX_FUNC('+name+') {')
    end=text.find('\nDEFINE_REX_FUNC(',start+1)
    if end<0:end=len(text)
    body=text[start:end]
    if marker not in body:continue
    anchor='// bl 0x'+call.lower()+'\n\t'
    left=body.rfind(anchor,0,body.index(marker))+len(anchor)
    right=body.index('\n\t// b 0x'+next_branch,left)
    if left<len(anchor) or not body[left:right].startswith('{'):raise RuntimeError('Unexpected preview text hook')
    resume='821FA45C' if name=='sub_821FA3F0' else '8221F1B4'
    restored='ctx.lr = 0x'+resume+';\n\tsub_'+call+'(ctx, base);'
    p.write_text(text[:start]+body[:left]+restored+body[right:]+text[end:])
    changes+=1

name='sub_8221F328'
p=locate_functions(args.generated,[name])[name]
text=p.read_text()
start=text.index('DEFINE_REX_FUNC('+name+') {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'PromptDraw' not in body:
    needle='REX_FUNC_PROLOGUE();'
    if body.count(needle)!=1:raise RuntimeError('Unexpected original text drawing function')
    replacement=needle+'\n\tben10::albedo_textures::PromptDraw prompt(base + ctx.r3.u32 + 124);'
    p.write_text('#include "../../src/albedo_textures.h"\n'+text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1

name='sub_82229968'
p=locate_functions(args.generated,[name])[name]
text=p.read_text()
start=text.index('DEFINE_REX_FUNC('+name+') {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'PromptSpriteBind' not in body:
    bind='ctx.lr = 0x82229C90;\n\tsub_824388E8(ctx, base);'
    coordinates='ctx.lr = 0x82229CC8;\n\tsub_8243DE58(ctx, base);'
    if body.count(bind)!=1 or body.count(coordinates)!=1:raise RuntimeError('Unexpected prompt sprite draw')
    body=body.replace(bind,'{\n\tben10::albedo_textures::PromptSpriteBind sprite(ctx.r30.u8);\n\t'+bind)
    body=body.replace(coordinates,'ctx.r6.u64 = sprite.Coordinates(ctx.r6.u32);\n\t'+coordinates+'\n\t}')
    p.write_text('#include "../../src/albedo_textures.h"\n'+text[:start]+body+text[end:])
    changes+=1

name='sub_824846E0'
p=locate_functions(args.generated,[name])[name]
text=p.read_text()
start=text.index('DEFINE_REX_FUNC('+name+') {')
end=text.find('\nDEFINE_REX_FUNC(',start+1)
if end<0:end=len(text)
body=text[start:end]
if 'BindPromptSprite' not in body:
    needle='ben10::albedo_textures::Apply(ctx.r25.u32, ctx.r24.u32, texture_base, texture_mips);'
    if body.count(needle)!=1:raise RuntimeError('Unexpected texture override hook')
    replacement=('uint32_t texture_flags = ctx.r25.u32, texture_size = ctx.r24.u32;\n'
                 '\t\tif (ben10::albedo_textures::BindPromptSprite(texture_flags, texture_size, texture_base, texture_mips)) {\n'
                 '\t\t  REX_STORE_U32(ctx.r11.u32, texture_flags);\n'
                 '\t\t  REX_STORE_U32(ctx.r11.u32 + 8, texture_size);\n'
                 '\t\t} else {\n\t\t  '+needle+'\n\t\t}')
    p.write_text(text[:start]+body.replace(needle,replacement)+text[end:])
    changes+=1
# Opt-in lifecycle trace for the PC cinematic player. Observe the stock
# results without changing guest state or substituting a movie.
cinematic_hooks = {
    'sub_821A86B8': {
        'REX_FUNC_PROLOGUE();': 'const uint32_t cinematic_caller = ctx.lr;',
        'sub_821A8268(ctx, base);': 'ben10::cinematic_trace::Open(cinematic_caller, ctx.r3.u32);',
    },
    # The New Game traces resolve to this frontend caller, not the
    # in-mission movie loop below.
    'sub_82156CD0': {
        'ctx.lr = 0x82157018;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'static thread_local uint32_t intro_state_site = 0, intro_state_value = 0;\n'
            '\tben10::cinematic_trace::State("intro state", 0x82157018, ctx.r3.u32, intro_state_site, intro_state_value);',
        'ctx.lr = 0x82157098;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'static thread_local uint32_t intro_done_site = 0, intro_done_value = 0;\n'
            '\tben10::cinematic_trace::State("intro completion", 0x82157098, ctx.r3.u32, intro_done_site, intro_done_value);',
        'ctx.lr = 0x821570DC;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'ben10::cinematic_trace::Closing(ctx.ctr.u32);',
    },
    'sub_821C2510': {
        'ctx.lr = 0x821C263C;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'static thread_local uint32_t movie_state_target = 0, movie_state_value = 0;\n'
            '\tben10::cinematic_trace::State("story state", 0x821C263C, ctx.r3.u32, movie_state_target, movie_state_value);',
        'ctx.lr = 0x821C26D8;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'static thread_local uint32_t movie_done_target = 0, movie_done_value = 0;\n'
            '\tben10::cinematic_trace::State("story completion", 0x821C26D8, ctx.r3.u32, movie_done_target, movie_done_value);',
        'ctx.lr = 0x821C2710;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'ben10::cinematic_trace::Closing(ctx.ctr.u32);',
    },
}
for name, hooks in cinematic_hooks.items():
    p = locate_functions(args.generated, [name])[name]
    text = p.read_text()
    start = text.index(f'DEFINE_REX_FUNC({name}) {{')
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    if end < 0:
        end = len(text)
    body = text[start:end]
    if 'ben10::cinematic_trace::' in body:
        continue
    for target, trace in hooks.items():
        if body.count(target) != 1:
            raise RuntimeError(f'Unexpected cinematic trace site in {name}: {target}')
        if trace.startswith('ben10::cinematic_trace::Closing'):
            body = body.replace(target, trace + '\n\t' + target)
        else:
            body = body.replace(target, target + '\n\t' + trace)
    p.write_text('#include "../../src/cinematic_trace.h"\n' + text[:start] + body + text[end:])
    changes += 1

# The frontend keeps the original movie object for the stock destructor.
# Match the original path and keep each supported playback loop paired with its destructor.
intro_player_hooks = {
    'sub_821A9490': {
        'ctx.lr = 0x821A959C;\n\tsub_821AA990(ctx, base);':
            'char source[260]{};\n'
            '\tfor (uint32_t i = 0; i < sizeof(source) - 1; ++i) {\n'
            '\t\tsource[i] = static_cast<char>(REX_LOAD_U8(ctx.r3.u32 + i));\n'
            '\t\tif (!source[i]) break;\n'
            '\t}\n'
            '\tben10::cinematic_player::CaptureSource(source);\n'
            '\tctx.lr = 0x821A959C;\n\tsub_821AA990(ctx, base);',
    },
    'sub_821A86B8': {
        'const uint32_t cinematic_caller = ctx.lr;':
            'const uint32_t cinematic_caller = ctx.lr;\n'
            '\tben10::cinematic_player::ResetSource();',
        'ben10::cinematic_trace::Open(cinematic_caller, ctx.r3.u32);':
            'ben10::cinematic_trace::Open(cinematic_caller, ctx.r3.u32);\n'
            '\tben10::cinematic_player::Begin(cinematic_caller, ctx.r3.u32);',
    },
    'sub_82156CD0': {
        'ctx.lr = 0x82157018;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'ctx.lr = 0x82157018;\n'
            '\tif (ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32 != 0;\n'
            '\telse { REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }',
        'ctx.lr = 0x8215707C;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'ctx.lr = 0x8215707C;\n'
            '\tif (!ben10::cinematic_player::Update(ctx.r3.u32)) { REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }',
        'ctx.lr = 0x82157098;\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);':
            'ctx.lr = 0x82157098;\n'
            '\tif (!ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) { REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }',
        'ctx.lr = 0x821570DC;':
            'ben10::cinematic_player::Close(ctx.r3.u32);\n\tctx.lr = 0x821570DC;',
    },
}
for name, (poll, update, complete, close) in {
    'sub_82158018': ('82158438', '8215841C', '821584D4', '8215854C'),
    'sub_821C2510': ('821C263C', '821C26C0', '821C26D8', '821C2710'),
}.items():
    for site, statement in (
        (poll, 'if (ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32 != 0;'),
        (update, 'if (!ben10::cinematic_player::Update(ctx.r3.u32)) { REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }'),
        (complete, 'if (!ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) { REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }'),
        (close, 'ben10::cinematic_player::Close(ctx.r3.u32);'),
    ):
        target = f'ctx.lr = 0x{site};\n\tREX_CALL_INDIRECT_FUNC(ctx.ctr.u32);'
        if site == poll:
            replacement = f'ctx.lr = 0x{site};\n\t{statement}\n\telse {{ REX_CALL_INDIRECT_FUNC(ctx.ctr.u32); }}'
        elif site == close:
            replacement = f'{statement}\n\t{target}'
        else:
            replacement = f'ctx.lr = 0x{site};\n\t{statement}'
        intro_player_hooks.setdefault(name, {})[target] = replacement

subtitle_parser = locate_functions(args.generated, ['sub_821E7EA0'])['sub_821E7EA0']
subtitle_text = subtitle_parser.read_text()
old_capture = re.compile(
    r'(loc_821E8128:)\n\tif \(\(subtitle_caller == 0x82157048.*?'
    r'\n\t}\n(?=\t// addi r1,r1,272)', re.DOTALL)
subtitle_updated = old_capture.sub(r'\1\n', subtitle_text).replace(
    '\n\tconst uint32_t subtitle_caller = ctx.lr;', '')
if subtitle_updated != subtitle_text:
    subtitle_parser.write_text(subtitle_updated)
    changes += 1

for name, hooks in intro_player_hooks.items():
    p = locate_functions(args.generated, [name])[name]
    text = p.read_text()
    start = text.index(f'DEFINE_REX_FUNC({name}) {{')
    end = text.find('\nDEFINE_REX_FUNC(', start + 1)
    if end < 0:
        end = len(text)
    body = text[start:end]
    original = body
    body = body.replace('if (ben10::cinematic_player::Ready(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32;', 'if (ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32 != 0;')
    for target, replacement in hooks.items():
        if replacement in body:
            continue
        if body.count(target) != 1:
            raise RuntimeError(f'Unexpected cinematic player site in {name}: {target}')
        body = body.replace(target, replacement)
    body = body.replace('if (ben10::cinematic_player::Result(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32 != 0;', 'if (ben10::cinematic_player::Ready(ctx.r3.u32, ctx.r3.u32)) ctx.r3.u64 = ctx.r3.u32;')
    if body == original:
        continue
    header = '#include "../../src/cinematic_player.h"\n'
    p.write_text((header if header not in text else "") + text[:start] + body + text[end:])
    changes += 1

print('PC integration applied to',changes,'locally generated functions.')
