"""Apply authored PC integration to locally generated game code, idempotently.

Contains patch locations and authored changes, never original function bodies.
Run after rexglue codegen and before compiling the consumer.
"""
import argparse
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
print('PC integration applied to',changes,'locally generated functions.')
