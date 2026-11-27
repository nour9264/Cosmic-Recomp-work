"""Build a private alien package from a locally extracted Vilgax Attacks Xbox 360 folder.

Vilgax Attacks (same engine, one generation older) keeps each alien's body
mesh, skin, skeleton and textures inside every level's streaming files and its
animations in a_<code>.xbx. This assembles them into one package in this
game's g_<code>.xbx layout. Only the user's own files are read; no game data
enters Git. The result is unverified until it is tested in game.
"""
import argparse
import math
import os
from pathlib import Path
import re
import struct
import zlib

from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import table
from merge_alien_streams import animation_time_range, channel_records, entries, streamed_clip
from prepare_all_aliens_candidate import Code, decode, encode
from prepare_pause_menu_extension import records
from wheel_icon_texture import icon_texture

ALIENS = {'chromastone': 'cs', 'jetray': 'jr', 'brainstorm': 'bs', 'goop': 'gp', 'cannonbolt': 'cb'}
LEVEL = 'l_anur'

# Vilgax Attacks material commands are {kind, texture, value}; this game uses
# {kind, 0, texture, value} with renumbered kinds.
MATERIAL_KINDS = {1: 1, 2: 5, 7: 9, 8: 10}


def character_record(char_ddf, name):
    """The 384-byte character_<name> record from Vilgax Attacks' char.ddf."""
    cursor = 4
    while cursor + 24 <= len(char_ddf):
        size, = struct.unpack_from('>I', char_ddf, cursor + 20)
        body = char_ddf[cursor + 24:cursor + 24 + size]
        if re.match(rb'character_' + name.encode() + rb'\0', body):
            return body
        cursor += 24 + size
    raise ValueError('Vilgax Attacks has no character_' + name)


def referenced(record, keys):
    found = [key for key in keys if struct.pack('>I', key) in record]
    if len(found) != 1:
        raise ValueError('Expected exactly one referenced resource')
    return found[0]


def mesh_parts(record):
    """Split a Vilgax Attacks mesh into metadata, buffers and material trailer."""
    # Counts are big-endian; buffer addresses are little-endian pointers.
    layout, vertex_count = struct.unpack_from('>II', record)
    index_count, = struct.unpack_from('>I', record, 12)
    vertex_address, index_address = (struct.unpack_from('<I', record, at)[0] for at in (8, 16))
    stride = {9: 20, 11: 44}[layout & 15]
    vertex_at = 372
    index_at = vertex_at + index_address - vertex_address
    vertex_end = vertex_at + vertex_count * stride
    index_end = index_at + 2 * index_count
    if not vertex_end <= index_at < index_end <= len(record) or any(record[vertex_end:index_at]):
        raise ValueError('Unexpected Vilgax Attacks mesh layout')
    indices = record[index_at:index_end]
    if max(struct.unpack(f'>{index_count}H', indices)) >= vertex_count:
        raise ValueError('Mesh index out of range')
    return layout, vertex_count, index_count, record[vertex_at:vertex_end], indices, record[index_end:]


CHARACTER_SHADER = 0x622


def convert_mesh(record, xbox_reference, shader=None):
    """shader: the draw's first word. Characters use this game's skinned
    shader; effect meshes keep Vilgax Attacks' own value (2, the unlit
    blended effect shader both games share)."""
    layout, vertex_count, index_count, vertices, indices, trailer = mesh_parts(record)
    if trailer[:4] != bytes(4):
        raise ValueError('Unexpected mesh trailer')
    draw_count = record[21]
    if not draw_count:
        raise ValueError('Missing mesh draws')
    commands = bytearray()
    textures = []
    cursor = 4
    for _ in range(draw_count):
        descriptor = struct.unpack_from('>6I', trailer, cursor)
        if descriptor[2] & 0xffff or descriptor[5] & 0xffff:
            raise ValueError('Unexpected draw descriptor')
        commands += struct.pack('>5I', descriptor[0] if shader is None else shader, descriptor[1],
                                descriptor[2] | descriptor[5] >> 16, descriptor[3], descriptor[4])
        cursor += 24
        material_count = (descriptor[5] >> 16) & 0xff
        for _ in range(material_count):
            kind, texture, value = struct.unpack_from('>3I', trailer, cursor)
            if kind not in MATERIAL_KINDS:
                raise ValueError(f'Unknown material command {kind}')
            commands += struct.pack('>4I', MATERIAL_KINDS[kind], 0, texture,
                                    0xffffffff if kind == 1 else value)
            if kind != 2:
                textures.append(texture)
            cursor += 12
    if any(trailer[cursor:]):
        raise ValueError('Unexpected bytes after material commands')
    # No terminator: the draw's command count is in its third word, and the
    # engine takes vertex data from the first 32-byte boundary after the
    # commands. A 16-byte terminator moved one-command effect meshes from
    # 416 to 448, so every effect mesh drew from 32 bytes too early.

    metadata_address, = struct.unpack_from('<I', xbox_reference, 28)
    metadata = record[36:372] + commands
    vertex_at = (40 + len(metadata) + 31) & ~31
    index_at = (vertex_at + len(vertices) + 31) & ~31
    # Xbox records use one vertex stream for all draw ranges.
    header = struct.pack('>III', layout, vertex_count, 1)
    header += struct.pack('<I', metadata_address + vertex_at - 376)
    header += struct.pack('>I', index_count)
    header += struct.pack('<I', metadata_address + index_at - 376)
    header += record[20:24] + struct.pack('<I', metadata_address) + record[28:36]
    result = header + metadata
    result += bytes(vertex_at - len(result)) + vertices
    result += bytes(index_at - len(result)) + indices
    if mesh_buffers(result, xbox=True)[1:] != (vertices, indices):
        raise ValueError('Converted mesh failed round-trip validation')
    return result, textures


def convert_skin(record, vertex_count, xbox_reference):
    # Vilgax Attacks adds four words after the vertex counts.
    count, repeated = struct.unpack_from('>II', record, 72)
    if count != repeated or count != vertex_count or len(record) != 96 + count * 52:
        raise ValueError('Unexpected Vilgax Attacks skin')
    if xbox_reference[68:70] != b'\x07\x01':
        raise ValueError('Unexpected Xbox skin header')
    return record[:64] + xbox_reference[64:72] + record[72:80] + record[96:]


def convert_texture(record):
    # Same tiled DXT data; older header with no mip chain. Character formats
    # 0x13c/0x13a are this game's 0x11c (DXT1) and 0x11a (DXT5); interface
    # formats 0x124/0x122 are 0x104 and 0x102.
    flag, fmt, width, height = struct.unpack_from('>IHHH', record)
    compression = {0x13c: (0x90434000, 0x11c, 8192), 0x13a: (0xa0848000, 0x11a, 16384),
                   0x124: (0x90434000, 0x104, 8192), 0x122: (0xa0848000, 0x102, 16384)}.get(fmt)
    if flag not in (1, 2) or compression is None:
        raise ValueError(f'Unsupported Vilgax Attacks texture format {fmt:#x}')
    word, our_format, page = compression
    base = ((width + 127) // 128) * ((height + 127) // 128) * page
    if len(record) != 128 + base:
        raise ValueError('Unexpected texture size')
    header = bytearray(record[:128])
    struct.pack_into('>IH', header, 0, word, our_format)
    struct.pack_into('>I', header, 28, 1)  # Base level only.
    return bytes(header) + record[128:]


def bank(section_id, align_log2, records, flags=lambda record: 0):
    """A nested vaps table in the layout this game's packages use."""
    keys = sorted(records)
    count = len(keys)
    buckets = (count + 3) // 4 * 4
    ordered = sorted(keys, key=lambda key: (key % buckets, key))
    alignment = 1 << align_log2
    directory = bytearray(struct.pack('>5I', buckets, count, 32, 32 + buckets * 4, 12) + bytes(12))
    cursor = 0
    for index in range(buckets):
        while cursor < count and ordered[cursor] % buckets < index:
            cursor += 1
        directory += struct.pack('>I', cursor)
    payload = bytearray()
    for key in ordered:
        payload += bytes((-len(payload)) % alignment)
        directory += struct.pack('>3I', key, flags(records[key]) << 24 | len(records[key]), len(payload))
        payload += records[key]
    payload += bytes((-len(payload)) % alignment)
    base = (32 + len(directory) + alignment - 1) // alignment * alignment
    header = b'vaps' + struct.pack('>IIHHIIII', 0x10003, count, align_log2, 0x1c00,
                                   len(payload), section_id, 0, base)
    result = header + directory + bytes(base - 32 - len(directory)) + payload
    if table(result) != records:
        raise ValueError('Bank failed round-trip validation')
    return bytes(result)


def package(template, sections, payload_order=None):
    """Outer package: same container as table banks, sections keyed by number."""
    keys = sorted(sections)
    alignment = 1 << struct.unpack_from('>H', template, 12)[0]
    buckets = (len(keys) + 3) // 4 * 4
    directory = bytearray(struct.pack('>5I', buckets, len(keys), 32, 32 + buckets * 4, 12) + bytes(12))
    ordered = sorted(keys, key=lambda key: (key % buckets, key))
    cursor = 0
    for index in range(buckets):
        while cursor < len(ordered) and ordered[cursor] % buckets < index:
            cursor += 1
        directory += struct.pack('>I', cursor)
    payload = bytearray()
    offsets = {}
    for key in (ordered if payload_order is None else payload_order):
        payload += bytes((-len(payload)) % alignment)
        offsets[key] = len(payload)
        payload += sections[key]
    for key in ordered:
        directory += struct.pack('>3I', key, len(sections[key]), offsets[key])
    payload += bytes((-len(payload)) % alignment)
    base = (32 + len(directory) + alignment - 1) // alignment * alignment
    header = bytearray(template[:32])
    struct.pack_into('>I', header, 8, len(keys))
    struct.pack_into('>I', header, 16, len(payload))
    struct.pack_into('>I', header, 28, base)
    result = bytes(header + directory + bytes(base - 32 - len(directory)) + payload)
    if entries(result) != sections:
        raise ValueError('Package failed round-trip validation')
    return result


def prepare(vilgax, cosmic, name):
    code = ALIENS[name]
    level = vilgax / LEVEL
    character = character_record((vilgax / 'global/scripts/char.ddf').read_bytes(), name)
    level_data = entries((level / (LEVEL + '_d.xbx')).read_bytes(), True)
    level_main = entries((level / (LEVEL + '.xbx')).read_bytes())
    level_textures = entries((level / (LEVEL + '_t.xbx')).read_bytes(), True)
    skins, skeletons = table(level_main[22]), table(level_main[12])
    mesh_key = referenced(character, [k for k in skins if k in level_data])
    skeleton_key = referenced(character, skeletons)

    # Four Arms' package is copied into the game folder when the game first starts with him; before that the
    # launcher's own prepared copy (installation/four-arms) holds the same file.
    four_arms = cosmic / 'global/g_fa.xbx'
    if not four_arms.is_file():
        four_arms = cosmic.parent / 'four-arms' / 'g_fa.xbx'
    native = entries(four_arms.read_bytes())
    template = four_arms.read_bytes()
    mesh_reference = next(iter(table(native[4]).values()))
    skin_reference = next(iter(table(native[22]).values()))
    color_reference = table(native[3])[0x63147ce1]

    mesh, textures = convert_mesh(level_data[mesh_key], mesh_reference, CHARACTER_SHADER)
    vertex_count, = struct.unpack_from('>I', mesh, 4)
    skin = convert_skin(skins[mesh_key], vertex_count, skin_reference)
    colors = bytes(8) + struct.pack('>I', mesh_key) + color_reference[12:16] + bytes(16)
    images = {key: convert_texture(level_textures[key]) for key in textures}

    animation = entries((vilgax / 'global' / f'a_{code}.xbx').read_bytes())
    channels = channel_records(animation[9])
    bones, = struct.unpack_from('>H', skeletons[skeleton_key])
    for clip in entries(animation[13], True).values():
        if name == 'cannonbolt':
            source_ids = {struct.unpack_from('>I', skeletons[skeleton_key], 52 + i * 44)[0] & 0xffffff
                          for i in range(bones)}
            if not set(bone_ids(clip)) <= source_ids:
                raise ValueError('Cannonbolt animation references an unknown bone')
        elif struct.unpack_from('>I', clip, 76)[0] != bones:
            raise ValueError('Animation does not match the skeleton')
        streamed_clip(clip, channels)

    # The selection wheel's picture of the alien, from Vilgax Attacks' HUD.
    icon = WHEEL_ICONS[name]
    images[icon] = convert_texture(entries((vilgax / 'global/gtex_s.xbx').read_bytes(), True)[icon])
    # Pictures of the aliens like the other aliens' (rendered figures), cut from screenshots the
    # owner made; they are private game art, so the folder comes from the environment.
    picture = Path(os.environ.get('COSMIC_WHEEL_ICON_DIR', '.')) / f'{name}.png'
    if os.environ.get('COSMIC_WHEEL_ICON_DIR') and picture.exists():
        images[icon] = icon_texture(picture, images[icon][:128])
    meshes, color_records = {mesh_key: mesh}, {mesh_key: colors}
    effects = special_effects(vilgax, name, mesh_reference, color_reference,
                              {key: data for key, _, data in vaps_rows(native[14])})
    images.update(effects['textures'])
    meshes.update(effects['meshes'])
    color_records.update(effects['colors'])
    special_clips = {crc(f'{name}_{clip}') for clip in SPECIAL_CLIPS[name].values()}
    flag_bank, flag_clips, flag_rows = remap_animation_flags(animation[9], animation[13], special_clips)
    channel_bank, clip_bank = merge_channels(flag_bank, flag_clips, effects['curves'] + flag_rows,
                                             len(flag_rows), lunge_clip(cosmic, name, flag_clips))
    if name == 'cannonbolt':
        channel_bank, clip_bank = cannonbolt_visibility(channel_bank, clip_bank)
    sections = {
        0: bank(0, 7, images, lambda record: 4),
        3: bank(3, 7, color_records, lambda record: 1 if record[:4] == b'\0\1\0\0' else 0),
        4: bank(4, 7, meshes, lambda record: mesh_buffers(record, xbox=True)[0] // 32),
        9: channel_bank,
        12: bank(12, 4, {skeleton_key: skeletons[skeleton_key]}),
        13: clip_bank,
        14: build_vaps(14, 4, bucket_sorted([(key, 0, node) for key, node in effects['nodes'].items()])),
        22: bank(22, 5, {mesh_key: skin}),
    }
    sound_lines = b''
    if name in SPECIAL_SOUNDS_ENABLED:
        sections[24], sound_lines = sound_project(vilgax, vaps_rows(native[24]), name)
    return package(template, sections, sorted(sections) if name == 'cannonbolt' else None), dict(
        mesh=f'{mesh_key:08x}', skeleton=f'{skeleton_key:08x}', bones=bones,
        vertices=vertex_count, textures=[f'{key:08x}' for key in textures],
        clips=len(entries(animation[13], True)), effect_nodes=len(effects['nodes']),
        effect_meshes=len(effects['meshes']), effect_curves=len(effects['curves']),
        sounds=sound_lines.decode('ascii'))


# Special-attack effects. Vilgax Attacks keeps them in e_<code>.xbx: effect
# nodes (section 14) in the same tagged-property format as this game at a
# newer revision, plus their meshes, textures, colors and curves. As with
# Four Arms, the fifth effect root attached at creation holds one trigger
# node per ability. A trigger turns the ability's attack events (words 36/37)
# into the events its effect tree already listens for and starts that tree,
# which stays unattached until then.
# Vilgax Attacks' trees: e2719479 crystal shard (gatling), 1474749e laser
# beam, 56290b79 crystals bursting from the body (energy outburst), 7ad38f32
# prismatic explosion. (a5c2704c is the block shield, not a special.)
# Jetray and Goop: Vilgax Attacks' special visuals are not converted yet, so
# their specials keep the animation and the hit only.
EFFECT_TREES = {'jetray': {}, 'goop': {},
                'chromastone': {0x549d5666: 0xe2719479, 0x239a66f0: 0x1474749e,
                                0xba93374a: 0xe3dade88, 0xcaf9c3c5: 0xe2719479}}
# The gatling gun's coloured bolts are projectiles (archetype fde917db) and
# are not converted yet. Its visual is the crystal volley e3dade88 (24 spikes
# flying 10 m forward; the group under Vilgax Attacks' fifth weapon 56290b79,
# which has no event forwarding of its own, so the group is used directly).
# Energy outburst's rainbow trail is the unconverted hand weapon: hit only.
EFFECT_TREES['chromastone'][0x549d5666] = 0xe3dade88
del EFFECT_TREES['chromastone'][0xba93374a]
# Node types are archetypes (global/scripts/archetyp.at) that supply each
# property group's defaults. Vilgax Attacks' beam archetype d08eabe2 (groups
# crc32 "laser" + "mesh") is absent here, so the laser beam node 8d7d2524
# lost its width, taper and reach defaults. Way Big's beam (g_ewayb 312d76f1)
# is a plain node listing its whole "laser" group, so the beam does the same:
# Way Big's keys with d08eabe2's default values (0.4, 0.4, 0.07, 0.15, 75 and
# 370021c8 match its order); the node's own values (range 7, beammesh
# f404a61f, damage 5, events) override them.
ARCHETYPE_DEFAULTS = {0xd08eabe2: {0xe94ca4cc: [
    (0x8ddaf3ee, 0x0201000c, 0), (0x8541406c, 0x0201000c, 0x9f79558f),
    (0xf7be9018, 0x0201000c, 0xb95616b6), (0x93875a49, 0x0101000c, 0x41280000),
    (0x4c4391a4, 0x0201000c, 0), (0x9884e60e, 0x0201000c, 0),
    (0x8c3d8164, 0x0101000c, 0x3ecccccd), (0xfa8175f9, 0x0101000c, 0x3ecccccd),
    (0xcc55397a, 0x0201000c, 0), (0x4ec40395, 0x0201000c, 0),
    (0xa45759f1, 0x0101000c, 0x3d8f5c29), (0x685a22fe, 0x0101000c, 0x3e19999a),
    (0x24d9b7ce, 0x0101000c, 0x42960000), (0x11c8546c, 0x0101000c, 0),
    (0xd2b16b66, 0x0201000c, 0), (0xb823fe47, 0x0201000c, 0x370021c8)]}}
# Jetray's Tail Zap bolts: archetype 4a55bbbc's "laser" group (start/stop on
# "create"/"destroy", range 1, beam mesh 4e6e7fc6). Its hit group is left out
# (the special keeps this port's own hit) and so is its emitter.
ARCHETYPE_DEFAULTS[0x4a55bbbc] = {0xe94ca4cc: [
    (key, code, {0x8541406c: 0x8fd6e0fb, 0xf7be9018: 0x7c4a867b, 0x93875a49: 0x3f800000,
                 0x4c4391a4: 0x4e6e7fc6, 0xb823fe47: 0xb7840510}.get(key, default))
    for key, code, default in ARCHETYPE_DEFAULTS[0xd08eabe2][0xe94ca4cc]]}
# Groups an archetype supplies that its nodes do not list. 4a55bbbc's curve
# player 60bf9208 (plays the node's position track on "create"; archetype
# values flags 2, d14d703e 1, speed 1): without it the bolts stayed where
# they spawn.
ARCHETYPE_GROUPS = {0x4a55bbbc: [
    (0x60bf9208, 0x0001000c, [0x60bf9208]), (0x8ddaf3ee, 0x0201000c, [0]), (0x8541406c, 0x0201000c, [0x8fd6e0fb]),
    (0xf7be9018, 0x0201000c, [0x7c4a867b]), (0x8c1d1043, 0x0201000c, [0]), (0xa050a7dc, 0x0201000c, [0]),
    (0x6e023a40, 0x0201000c, [1]), (0xc4081b46, 0x0201000c, [0]), (0x6f949845, 0x0101000c, [0x3f800000]),
    (0xd14d703e, 0x0201000c, [1]), (0x84a5da07, 0x0101000c, [0]), (0xf95dcaa8, 0x0201000c, [0])]}
# Archetype 9210498f (Chromastone's crystal spike) is absent here, and so are its
# curve player's (60bf9208) settings: without them the spikes play no animation
# and sit where they spawn instead of flying forward. Same values as 4a55bbbc's:
# play the node's position track (flag 6e023a40), speed 1.
CRYSTAL_ARCHETYPE = 0x9210498f
CRYSTAL_SPREAD = {0x31b9464e: -3.0, 0xf49a74a1: 3.0}
# Four shots in the animation: left hand, right hand, left hand again, then two
# crystals from the chest. Spikes keep their own start events (timeline order
# 980371ee, 010a2054, 760d10c2, e8698561); the third shot is moved to the left
# hand's spot and the fourth shot gets a second spike beside the first.
CRYSTAL_PLACEMENT = {0x2679ff3d: (-0.274, 1.789, 1.043), 0x31b9464e: (-0.09, 1.812, 0.261),
                     0xf49a74a1: (0.09, 1.812, 0.268)}
CRYSTAL_DEFAULTS = {0x60bf9208: [
    (0x8ddaf3ee, 0x0201000c, 0), (0x8541406c, 0x0201000c, 0x8fd6e0fb), (0xf7be9018, 0x0201000c, 0x7c4a867b),
    (0x8c1d1043, 0x0201000c, 0), (0xa050a7dc, 0x0201000c, 0), (0x6e023a40, 0x0201000c, 1),
    (0xc4081b46, 0x0201000c, 0), (0x6f949845, 0x0101000c, 0x3f800000), (0xd14d703e, 0x0201000c, 1),
    (0x84a5da07, 0x0101000c, 0), (0xf95dcaa8, 0x0201000c, 0)]}
# Goop (Vilgax Attacks e_gp): seven nodes in three roots; no captures name them, so
# the mapping is a first guess from their contents. 6751d0ee: one green puff emitter
# with gravity (Acid Hose spray); 93997af2: a 868-vertex goop mesh that rotates, with two
# puff emitters 1.9 m to each side (Puddle Smack). 866df60c, a 156-vertex blob with no
# events, is not used yet (Goopershot, Split Kick unmapped).
EFFECT_TREES['goop'] = {0x549d5666: 0x9f8ccf10, 0xcaf9c3c5: 0x93997af2, 0x239a66f0: 0x911c74a4}  # goop_shot  # R2 + X: goop mesh and trails. R2 + triangle (Goopershot): the green puff emitter, taken out of its root 6751d0ee (whose only group has no component here and crashed the form).
# Jetray (Vilgax Attacks e_jr), named from its HUD in frame captures: 88f8c328
# two eye beams (Lazer-Eye), 6c9dd55c six beams from eyes and tail while
# airborne (Tri Shot), 9718b112 three flying bolts (Tail Zap, the whipzap
# clip). Sonic dash has no tree.
EFFECT_TREES['jetray'] = {0x549d5666: 0x88f8c328, 0x239a66f0: 0x6c9dd55c, 0xba93374a: 0x9718b112}
# Burnout's original dust/trails use the particle component supported by both games.
EFFECT_TREES['cannonbolt'] = {0xcaf9c3c5: 0xf69eafe4}
# The eye beams hung from Jetray's head weapon (rotated into bone space).
# Here trees follow his feet. Vilgax Attacks' capture has the beam start at
# (-0.09, 1.24, 0.27) from his feet, level, 12 m long: same height and
# direction here (the children's 10 degree tilt was bone space too).
# The game's laser ray skips its owner (apply_game_integration.py), so the
# beams start where Vilgax Attacks' do: eyes at (-0.07 / 0.08, 1.24, 0.27).
NODE_PLACEMENT = {0x8cc9a5f1: (0.0, 1.1, 0.6),  # Goop's puff emitter: chest height, a little ahead.
                  0x8d7d2524: (0.0, 1.922, 1.331),  # Level beam: the original is pitched 5 degrees.
                  0x88f8c328: (0.0, 1.19, 0.19),
                  0x11f19292: (0.081, 0.048, 0.078), 0x66f6a204: (-0.068, 0.048, 0.078),
                  # Tri Shot's children are placed from his feet: at the origin they match
                  # Vilgax Attacks' capture (eyes (+-0.07, 3.39, 0.43), tail (0.13, 1.75, 1.98)).
                  0x6c9dd55c: (0.0, 0.0, 0.0)}
# (start events, stop events) each tree listens for. Vilgax Attacks' own code
# raised the four laser colors; here the attack raises them together.
EFFECT_SIGNALS = {
    0xe2719479: ([0x8fd6e0fb], [0x7c4a867b]),
    0x1474749e: ([0x8fd6e0fb], [0xe168c121]),
    0xe3dade88: ([0x8fd6e0fb, 0x760d10c2, 0x010a2054, 0xe8698561, 0x980371ee],
                 [0x7c4a867b, 0xe95fbf78, 0x9e588fee, 0x773b2adb, 0x0751de54]),
    0x7ad38f32: ([0x8fd6e0fb, 0x760d10c2, 0x010a2054, 0xe8698561, 0x980371ee],
                 [0x7c4a867b, 0xe95fbf78, 0x9e588fee, 0x773b2adb, 0x0751de54]),
}
# The gatling gun's volley root carries its own timeline (block 0x17, times in
# milliseconds): it raises each volley's start event at 0, 1.6, 3.7 and 5.4 s, so
# only the root's start event is renamed to the special's, and the crystals keep
# their own events. (Renaming them all made every crystal start at once, and a
# timer per crystal on top of the timeline fired them twice.)
GATLING_TIMERS = {}
GATLING_TIMER_GROUP = []  # The root's timer group entries, copied onto each crystal.
CRYSTAL_FLIGHT_TIME = 9600.0  # Track units; the original's 1600 flew far too fast here.
CRYSTAL_LIFETIME = 7.0  # Seconds from a crystal's start to its stop (the 1.6 s flight at 0.25 speed lasts 6.4 s).
GATLING_TREE = 0xe3dade88
DOME_MESHES = {0xa64f48dc, 0xc9fd6fb5, 0x1dada3f1, 0x98b1daec}
CRYSTAL_MESHES = {0x458e037e, 0xf404a61f}  # Vertex colours dimmed: the crystal spike and the laser beam (shared palette texture, but only the crystals get a new palette).
GATLING_TIMERS = {0x010a2054: 0.25, 0x980371ee: 0.75, 0xe8698561: 1.25, 0x760d10c2: 1.25}
EFFECT_SIGNALS[GATLING_TREE] = ([0x8fd6e0fb], [0x7c4a867b])
EFFECT_SIGNALS.update({0x8cc9a5f1: ([0xa6a70680], [0x6b271a59]), 0x6751d0ee: ([0xa6a70680], [0x6b271a59]), 0x93997af2: ([0x216cb2c7], [0xf4331d1a]),  # Goop
                       0x88f8c328: ([0x9f79558f, 0x40e6da18], [0xb95616b6, 0x8d66c6c1]),
                       0x9718b112: ([0x8fd6e0fb], [0x7c4a867b]),
                       0x6c9dd55c: ([0x8fd6e0fb], [0x7a1fd331])})
FOUR_ARMS_EFFECT_ROOT = 0x3cdbef3d
FOUR_ARMS_EFFECT_TRIGGER = 0x25d0050b
# Four Arms' spawned effect container (type bb09f978): names its package and
# holds the effect pieces; trigger events sent to it reach its children.
FOUR_ARMS_EFFECT_CONTAINER = 0x4a5918fa
# Effect nodes are looked up in the character's own package. Four Arms' setup
# attaches his hit volumes (the damage spheres attacks switch on through words
# 26-33) as effect roots 1-4; the imported form needs its own copies.
FOUR_ARMS_HIT_VOLUMES = 0x52725e1f
# Four Arms' spawned specials damage and break objects through expanding
# shockwave nodes (type 59bfb057) in their container. Vilgax Attacks' hit
# groups lack this game's radius and collision settings, so each imported
# special gets one of these, reduced to its hit and expansion groups.
FOUR_ARMS_SHOCKWAVE = 0x5e6de23c
SHOCKWAVE_GROUPS = {0x961699b1, 0x293c8e8b, 0x7fb6a6e3}
SHOCKWAVE_RADIUS = 0x700f6884
SPECIAL_REACH = {'chromastone': {0x549d5666: 6.0, 0x239a66f0: 7.0, 0xba93374a: 4.0, 0xcaf9c3c5: 6.0},
                 'jetray': {0x549d5666: 7.0, 0x239a66f0: 6.0, 0xba93374a: 5.0, 0xcaf9c3c5: 4.0},
                 'goop': {0x549d5666: 6.0, 0x239a66f0: 5.0, 0xba93374a: 4.0, 0xcaf9c3c5: 4.0}}
EVENT_GROUP = 0x721aeda8  # Property group: on 939b68a0, send 8541406c to node 557c4b4d.
NODE_REVISION = 0x0b
# Name hash of the package holding a spawned effect's resources (Four Arms:
# crc32("g_fa")). Imported effects now live in the alien's own g_<code>.
EFFECT_PACKAGE = 0x3a416c07


SPECIAL_REACH['cannonbolt'] = {0x549d5666: 2.5, 0x239a66f0: 3.0, 0xba93374a: 4.5, 0xcaf9c3c5: 3.0}
SPECIAL_LIFETIME = {'chromastone': {0x549d5666: 2.0, 0x239a66f0: 3.0, 0xba93374a: 2.0, 0xcaf9c3c5: 1.5}}
MISSING_NODE_TYPES = {0x9210498f, 0x02e1a005, 0xe2c9bc42, 0x80ec768c, 0x8a0d47c4, 0xd3476a13}
# Archetype efd9e2dc (the prismatic dome a64f48dc; same groups in both games)
# starts its groups on "create"/"destroy" defaults, which nothing raises here:
# trees listen for their special's own events. Listing the events on the node
# lets the rename below reach them. The hit group 961699b1 stays unstarted so
# the special's damage is unchanged. (group id, group type)
ARCHETYPE_EVENTS = {0xefd9e2dc: [(0x7fb6a6e3, 0x7fb6a6e3), (0x0a2dd96a, 0xbfdf3dde), (0xe8f6f36c, 0xbfdf3dde),
                                 (0x9e96f425, 0xbfdf3dde), (0x046b0df8, 0xbfdf3dde), (0x6a015e80, 0xbfdf3dde),
                                 (0x52ff3aac, 0x52ff3aac)]}
# The laser's spark emitter draws large yellow stars along the beam here.
REMOVED_NODES = {0x89954ee0}
# The gatling gun's volley root lists six overlapping spikes per shot (24). One per
# shot is kept: the four shots then show four crystals.
GATLING_EXTRA_SPIKES = {0x58c88380, 0xc1c1d23a, 0x1df9d194, 0x36d48257, 0x41d3b2c1, 0x5fa54799, 0xa8b017f4,
                        0x2fcfb316, 0x46be76d8, 0x4865feea, 0x517ecfab, 0xb6c6e2ac, 0xdfb72762, 0x839d4437, 0xc6ac1623,
                        0x1a94158d, 0x6d93251b, 0xafddd3ed, 0xd8dae37b}
REMOVED_NODES |= GATLING_EXTRA_SPIKES
# Offset applied to each child of a tree (x, y up, z forward). Frame captures
# of both games (beam transform relative to the body draw) put Vilgax Attacks'
# beam start at (-0.1, 1.43, 0.62) from Chromastone's feet, at his hand; the
# node itself says (0, 1.92, 1.33). This game's laser ray (sub_82109D70 ->
# sub_82147FB8) also tests the firing character's own capsule and accepts a
# negative distance, so a start inside it (radius ~0.73 m, from a measured
# -0.59 m beam at 0.43 m) draws the beam backwards. Start just outside: 0.80.
EFFECT_OFFSETS = {0x1474749e: (-0.1, -0.49, -0.53)}
# Vilgax Attacks draws the beam 15 m long (captured scale 14.99) although the
# node says range 7; here length is the range property times the hit fraction.
NODE_OVERRIDES = {0x8d7d2524: {0x93875a49: 0x41700000}}
ARCHETYPE_MESHES = {0x9210498f: 0x458e037e}  # Chromastone's crystal spike.


def shockwave_node(four_arms_nodes, key, container, start, reach):
    header, blocks = node_parts(four_arms_nodes[FOUR_ARMS_SHOCKWAVE])
    header = list(header)
    header[0] = key
    kept = []
    for block in blocks:
        if block[0] == 0x00:
            kept.append([0x00, block[1], key, key])
        elif block[0] == 0x08:
            kept.append([0x08, 3, container])
        elif block[0] == 0x0e:
            entries_, group, cursor = [], None, 2
            while cursor < len(block):
                entry, code = block[cursor], block[cursor + 1]
                size = (code & 0xffff) // 4
                values = list(block[cursor + 2:cursor + size])
                if code & 0xff7fffff == 0x1000c:
                    group = values[0]
                if group in SHOCKWAVE_GROUPS:
                    if entry == 0x8541406c:
                        values = [start]
                    elif entry == SHOCKWAVE_RADIUS:
                        values = [struct.unpack('>I', struct.pack('>f', reach))[0]]
                    entries_.append((entry, code & 0xff7fffff, values))
                cursor += size
            kept.append(node_properties(entries_))
        else:
            kept.append(block)
    return node_record(header, kept)


def set_property(blocks, key, value):
    for block in blocks:
        if block[0] != 0x0e:
            continue
        cursor = 2
        while cursor < len(block):
            if block[cursor] == key:
                block[cursor + 2] = value
            cursor += (block[cursor + 1] & 0xffff) // 4


def property_entries(block):
    entries_, cursor = [], 2
    while cursor < len(block):
        size = (block[cursor + 1] & 0xffff) // 4
        entries_.append((block[cursor], block[cursor + 1] & 0xff7fffff, block[cursor + 2:cursor + size]))
        cursor += size
    return entries_


def with_defaults(block, groups):
    """Rewrite a property block so each group in groups lists every key, in
    order, with the node's own value or the archetype default."""
    parsed, cursor = [], 2
    while cursor < len(block):
        size = (block[cursor + 1] & 0xffff) // 4
        parsed.append((block[cursor], block[cursor + 1] & 0xff7fffff, block[cursor + 2:cursor + size]))
        cursor += size
    result, index = [], 0
    while index < len(parsed):
        key, code, values = parsed[index]
        index += 1
        result.append((key, code, values))
        if code == 0x1000c and values[0] in groups:
            own = {}
            while index < len(parsed) and parsed[index][1] != 0x1000c:
                own[parsed[index][0]] = parsed[index]
                index += 1
            result += [own.pop(entry, (entry, entry_code, [default])) for entry, entry_code, default in groups[values[0]]]
            result += own.values()
    return node_properties(result)


def with_events(block, groups, start, stop):
    """Give each listed group explicit start/stop events, adding absent groups."""
    parsed, cursor = [], 2
    while cursor < len(block):
        size = (block[cursor + 1] & 0xffff) // 4
        parsed.append((block[cursor], block[cursor + 1] & 0xff7fffff, block[cursor + 2:cursor + size]))
        cursor += size
    events = [(0x8541406c, 0x0201000c, [start]), (0xf7be9018, 0x0201000c, [stop])]
    result, seen = [], set()
    for key, code, values in parsed:
        result.append((key, code, values))
        if code == 0x1000c and (key, values[0]) in groups:
            seen.add(key)
            result += events
    for group, kind in groups:
        if group not in seen:
            result += [(group, 0x1000c, [kind])] + events
    return node_properties(result)


def effect_events(name, slot):
    return crc(f'{name}_special_{slot:08x}_start'), crc(f'{name}_special_{slot:08x}_stop')


def effect_root(name):
    return crc(f'{name}_specials')


def vaps_rows(blob):
    """(key, flags, data) in directory order; duplicate keys are kept."""
    count, = struct.unpack_from('>I', blob, 36)
    records, = struct.unpack_from('>I', blob, 44)
    base, = struct.unpack_from('>I', blob, 28)
    rows = []
    for index in range(count):
        key, info, offset = struct.unpack_from('>III', blob, 32 + records + index * 12)
        rows.append((key, info >> 24, blob[base + offset:base + offset + (info & 0xffffff)]))
    return rows


def bucket_sorted(rows):
    buckets = max(1, len(rows) // 4)
    return sorted(rows, key=lambda row: (row[0] % buckets, row[0]))


def build_vaps(section_id, align_log2, rows):
    """A vaps bank whose directory keeps the given (bucket-sorted) row order."""
    count = len(rows)
    buckets = max(1, count // 4)
    if [key % buckets for key, _, _ in rows] != sorted(key % buckets for key, _, _ in rows):
        raise ValueError('Rows must be ordered by bucket')
    alignment = 1 << align_log2
    directory = bytearray(struct.pack('>5I', buckets, count, 32, 32 + buckets * 4, 12) + bytes(12))
    cursor = 0
    for index in range(buckets):
        while cursor < count and rows[cursor][0] % buckets < index:
            cursor += 1
        directory += struct.pack('>I', cursor)
    payload = bytearray()
    for key, flags, data in rows:
        payload += bytes((-len(payload)) % alignment)
        directory += struct.pack('>3I', key, flags << 24 | len(data), len(payload))
        payload += data
    payload += bytes((-len(payload)) % alignment)
    base = (32 + len(directory) + alignment - 1) // alignment * alignment
    header = b'vaps' + struct.pack('>IIHHIIII', 0x10003, count, align_log2, 0x1c00,
                                   len(payload), section_id, 0, base)
    result = header + directory + bytes(base - 32 - len(directory)) + payload
    if [(k, f, d) for k, f, d in vaps_rows(result)] != list(rows):
        raise ValueError('Bank failed round-trip validation')
    return bytes(result)


# Each clip names a flag channel (clip word 20): keyframes of {time, 0, 0, 0,
# mask, hash, ...} whose bits tell the engine when to switch weapon slots on
# and off (sub_82148DF0, table 0x820088A4: left hand 0x100000/0x20000, right
# hand 0x80000/0x10000, feet 0x4000/0x800 and 0x2000/0x400, head 0x1000/0x200),
# plus footsteps and sound cues. Vilgax Attacks uses the same flags 7 bits
# higher, so unconverted punches never raise a hit and specials signal the
# right hand instead of the head slot that holds the effect triggers.
FLAG_CHANNEL = 0x0a095000
FLAG_SHIFT = 7


HEAD_START, HEAD_STOP = 0x1000, 0x200
HIT_STARTS, HIT_STOPS = 0x00100000 | 0x00080000 | 0x4000 | 0x2000, 0x00020000 | 0x00010000 | 0x800 | 0x400


def flag_frames(data):
    kind, count = struct.unpack_from('>II', data)
    count &= 0xffff
    if kind != FLAG_CHANNEL or len(data) != 8 + count * 36:
        raise ValueError('Unexpected animation flag channel')
    return [list(struct.unpack_from('>9I', data, 8 + frame * 36)) for frame in range(count)]


def flag_channel(frames):
    return struct.pack('>II', FLAG_CHANNEL, len(frames) << 16 | len(frames)) + b''.join(
        struct.pack('>9I', *frame) for frame in frames)


def remap_animation_flags(channel_bank, clip_bank, special_clips):
    """Converted flag channels, and clips that gained a new one.

    Special attacks also switch the head slot (the effect triggers) on from
    their first hit marker, or the clip's start, until their last stop marker,
    or the clip's end. New channels are returned as extra rows; the clips that
    use them carry 0x80000000 | row in word 20 until merge_channels places them."""
    rows = vaps_rows(channel_bank)
    channels = [data for _, _, data in rows]
    converted = {}
    clips, extra = [], []
    for key, flags, clip in vaps_rows(clip_bank):
        index, = struct.unpack_from('>I', clip, 80)
        frames = None
        if index != 0xffffffff:
            frames = converted.get(index)
            if frames is None:
                frames = flag_frames(channels[index])
                for frame in frames:
                    if frame[4] & ((1 << FLAG_SHIFT) - 1):
                        raise ValueError('Animation flag without an equivalent')
                    frame[4] >>= FLAG_SHIFT
                converted[index] = frames
        if key in special_clips:
            frames = [list(frame) for frame in frames or []]
            begin, end = animation_time_range(clip, channels)
            time = lambda frame: struct.unpack('>f', struct.pack('>I', frame[0]))[0]
            starts = [frame for frame in frames if frame[4] & (HIT_STARTS | HEAD_START)]
            stops = [frame for frame in frames if frame[4] & (HIT_STOPS | HEAD_STOP)]
            first = min(starts, key=time) if starts else None
            last = max(stops, key=time) if stops and (not first or time(max(stops, key=time)) > time(first)) else None
            if first is None:
                first = [struct.unpack('>I', struct.pack('>f', max(begin, 1.0)))[0]] + [0] * 8
                frames.append(first)
            if last is None:
                last = [struct.unpack('>I', struct.pack('>f', end))[0]] + [0] * 8
                frames.append(last)
            first[4] |= HEAD_START
            last[4] |= HEAD_STOP
            frames.sort(key=time)
            clip = bytearray(clip)
            struct.pack_into('>I', clip, 80, 0x80000000 | len(extra))
            extra.append((crc(f'{key:08x}_flags'), 0, flag_channel(frames)))
            clip = bytes(clip)
        clips.append((key, flags, clip))
    for index, frames in converted.items():
        key, flags, _ = rows[index]
        rows[index] = (key, flags, flag_channel(frames))
    return (build_vaps(9, struct.unpack_from('>H', channel_bank, 12)[0], rows),
            build_vaps(13, struct.unpack_from('>H', clip_bank, 12)[0], clips), extra)


# Goop has no lunge of his own in Vilgax Attacks: his range attacks ran to the enemy. His travel clip is built here from
# another alien's range lunge in this game: for every bone the two skeletons share (bone ids are game-wide), the source clip's
# rotation track; Goop's own idle pose supplies everything else (positions, scales and his extra bones), so his proportions
# stay his. The clip carries no flag channel, like the originals' travel clips.
LUNGE_SOURCES = {}  # Experiment (Goop from Water Hazard's lunge, 'goop': ('g_wh.xbx', 'atk_far_fwd_travel_01')) deformed him; off.
LUNGE_CLIP = 'atk_lunge_01'


def bone_ids(clip):
    count, = struct.unpack_from('>I', clip, 76)
    return [struct.unpack_from('>H', clip, 88 + 2 * index)[0] for index in range(count)]


def cannonbolt_visibility(channel_bank, clip_bank):
    """Apply Vilgax Attacks' ball/body events using the paired skeleton branches."""
    channels = vaps_rows(channel_bank)
    clips = vaps_rows(clip_bank)
    original_channels = [data for _, _, data in channels]
    idle = next(clip for _, _, clip in clips if clip.startswith(b'idle_01\0'))
    ball_id, body_id = 193, 31
    ball_idle = struct.unpack_from('>3I', idle, 216 + 12 * bone_ids(idle).index(ball_id))
    ball_on, body_on = 0x2bd41ee1, 0x692ca718
    rolling_at_start = {'run_01', 'run_out_01', 'land_run_01',
                        'burnout_charging_01', 'burnout_run_01', 'burnout_out_01'}
    output = []
    for key, flags, source in clips:
        ids = bone_ids(source)
        if body_id not in ids:  # The clavicle overlays never own visibility.
            output.append((key, flags, source))
            continue
        name = source[:64].split(bytes(1))[0].decode('ascii')
        begin, end = animation_time_range(source, original_channels)
        events_index = struct.unpack_from('>I', source, 80)[0]
        transitions = {}
        if events_index != 0xffffffff:
            for event in flag_frames(original_channels[events_index]):
                for signal in event[5:]:
                    if signal in (ball_on, body_on):
                        frame_time = struct.unpack('>f', struct.pack('>I', event[0]))[0]
                        transitions[min(end, max(begin, frame_time))] = signal == ball_on
        clip = bytearray(source)
        if ball_id not in ids:
            struct.pack_into('>H', clip, 88 + 2 * len(ids), ball_id)
            ids.append(ball_id)
            struct.pack_into('>2I', clip, 72, len(ids), len(ids))
            clip.extend(struct.pack('>3I', *ball_idle))
        visible = name in rolling_at_start
        if name == 'balldash_01':
            visible = True  # Its ball-on marker is one tick after the clip begins.
        for bone_id in (body_id, ball_id):
            scale_offset = 224 + 12 * ids.index(bone_id)
            scale_index = struct.unpack_from('>I', clip, scale_offset)[0]
            scale_data = original_channels[scale_index]
            assert scale_data[:4] == bytes.fromhex('0c045003')
            keys = list(struct.iter_unpack('>4f', scale_data[8:]))
            def scale_at(t):
                if t <= keys[0][0]:
                    return keys[0][1:]
                for first, last in zip(keys, keys[1:]):
                    if t <= last[0]:
                        blend = (t - first[0]) / (last[0] - first[0])
                        return tuple(a + (b - a) * blend for a, b in zip(first[1:], last[1:]))
                return keys[-1][1:]
            times = {begin, end, *(key[0] for key in keys if begin <= key[0] <= end)}
            for time in transitions:
                times.update((max(begin, time - 1), time))
            samples = []
            state = visible
            for time in sorted(times):
                state = transitions.get(time, state)
                factor = 1.0 if state == (bone_id == ball_id) else 0.0001
                scale = scale_at(time)
                if bone_id == ball_id and name in {'run_01', 'burnout_run_01'}:
                    # Match the original starting vertical size on all axes.
                    scale = (scale_at(begin)[1],) * 3
                samples.append(struct.pack('>4f', time, *(value * factor for value in scale)))
            new_scale = scale_data[:4] + struct.pack('>2H', len(samples), len(samples)) + b''.join(samples)
            struct.pack_into('>I', clip, scale_offset, len(channels))
            channels.append((crc(f'cannonbolt_{name}_{bone_id}_visibility'), 0, new_scale))
        if name in {'run_01', 'burnout_run_01'}:
            # The older game spun the ball outside the animation. Bake one
            # seamless revolution around its lateral axis into the run cycle.
            rotation_offset = 220 + 12 * ids.index(ball_id)
            rotation_index = struct.unpack_from('>I', clip, rotation_offset)[0]
            base = original_channels[rotation_index]
            assert base[:4] == bytes.fromhex('10025002') and end > begin
            x, y, z, w, _ = struct.unpack_from('>3hbB', base, 8)
            x, y, z, w = x / 32767, y / 32767, z / 32767, w / 127
            norm = math.sqrt(x*x + y*y + z*z + w*w)
            x, y, z, w = (value / norm for value in (x, y, z, w))
            first, last = int(begin / 160), int(end / 160)
            samples = []
            for frame in range(first, last + 1):
                angle = -math.pi * (frame - first) / (last - first)
                c, sn = math.cos(angle), math.sin(angle)
                q = (x*c + w*sn, y*c + z*sn, z*c - y*sn, w*c - x*sn)
                samples.append(struct.pack('>3hbB', *(round(v*32767) for v in q[:3]),
                                           round(q[3]*127), frame))
            channel = base[:4] + struct.pack('>2H', len(samples), len(samples)) + b''.join(samples)
            struct.pack_into('>I', clip, rotation_offset, len(channels))
            channels.append((crc(f'cannonbolt_{name}_roll'), 0, channel))
        output.append((key, flags, bytes(clip)))
    # The game stores channel references as bank directory indices.
    buckets = max(1, len(channels) // 4)
    order = sorted(range(len(channels)), key=lambda i: (channels[i][0] % buckets, channels[i][0]))
    remap = {index: position for position, index in enumerate(order)}
    remapped = []
    for key, flags, clip in output:
        clip = bytearray(clip)
        for offset in [80] + list(range(216, len(clip), 4)):
            index = struct.unpack_from('>I', clip, offset)[0]
            if index != 0xffffffff:
                struct.pack_into('>I', clip, offset, remap[index])
        remapped.append((key, flags, bytes(clip)))
    alignment = lambda bank: struct.unpack_from('>H', bank, 12)[0]
    return (build_vaps(9, alignment(channel_bank), [channels[i] for i in order]),
            build_vaps(13, alignment(clip_bank), remapped))


def lunge_clip(cosmic, name, clip_bank):
    """(key, flags, clip, extra channel rows, patches) for merge_channels, or None."""
    if name not in LUNGE_SOURCES:
        return None
    package, source_name = LUNGE_SOURCES[name]
    source_file = cosmic / 'global' / package
    if not source_file.is_file():
        return None
    sections = entries(source_file.read_bytes())
    source_channels = channel_records(sections[9])
    source = next((clip for clip in table(sections[13]).values()
                   if clip[:64].split(bytes(1))[0].decode('ascii') == source_name), None)
    if source is None:
        return None
    base_key = crc(f'{name}_idle_01')
    flags, base = next((flags, clip) for key, flags, clip in vaps_rows(clip_bank) if key == base_key)
    clip = bytearray(base)
    clip[0:64] = LUNGE_CLIP.encode('ascii').ljust(64, bytes(1))
    struct.pack_into('>I', clip, 80, 0xffffffff)
    source_position = {ident: position for position, ident in enumerate(bone_ids(source))}
    rows, patches, placed = [], {}, {}
    for position, ident in enumerate(bone_ids(base)):
        if ident not in source_position:
            continue
        index, = struct.unpack_from('>I', source, 216 + 12 * source_position[ident] + 4)
        if index == 0xffffffff:
            continue
        if index not in placed:
            placed[index] = len(rows)
            rows.append((crc(f'{name}_lunge_channel_{index}'), 0, source_channels[index]))
        patches[216 + 12 * position + 4] = placed[index]
    return crc(f'{name}_{LUNGE_CLIP}'), flags, bytes(clip), rows, patches


def merge_channels(channel_bank, clip_bank, curves, extra_count=0, lunge=None):
    """Animation channels plus effect curves in one section 9.

    Clips address channels by directory position, so renumber them after
    the effect curves are sorted in by bucket."""
    channels = vaps_rows(channel_bank)
    tagged = [(key, flags, data, ('clip', index)) for index, (key, flags, data) in enumerate(channels)]
    lunge_rows = lunge[3] if lunge else []
    tagged += [(key, flags, data, ('curve', index)) for index, (key, flags, data) in enumerate(list(curves) + lunge_rows)]
    buckets = max(1, len(tagged) // 4)
    ordered = sorted(tagged, key=lambda row: (row[0] % buckets, row[0], row[3]))
    moved = {row[3][1]: position for position, row in enumerate(ordered) if row[3][0] == 'clip'}
    placed = {row[3][1]: position for position, row in enumerate(ordered) if row[3][0] == 'curve'}
    align = struct.unpack_from('>H', channel_bank, 12)[0]
    merged = build_vaps(9, align, [(key, flags, data) for key, flags, data, _ in ordered])

    clips = []
    for key, flags, clip in vaps_rows(clip_bank):
        clip = bytearray(clip)
        bones, = struct.unpack_from('>I', clip, 76)
        for at in [80] + list(range(216, 216 + bones * 12, 4)):
            index, = struct.unpack_from('>I', clip, at)
            if at == 80 and index != 0xffffffff and index & 0x80000000:
                # A new flag channel, appended after the effect curves.
                struct.pack_into('>I', clip, at, placed[len(curves) - extra_count + (index & 0x7fffffff)])
            elif index != 0xffffffff:
                struct.pack_into('>I', clip, at, moved[index])
        clips.append((key, flags, bytes(clip)))
    if lunge:
        key, flags, clip, _, patches = lunge
        clip = bytearray(clip)
        bones, = struct.unpack_from('>I', clip, 76)
        for at in range(216, 216 + bones * 12, 4):
            index, = struct.unpack_from('>I', clip, at)
            if at in patches:
                struct.pack_into('>I', clip, at, placed[len(curves) + patches[at]])
            elif index != 0xffffffff:
                struct.pack_into('>I', clip, at, moved[index])
        clips.append((key, flags, bytes(clip)))
        clips = bucket_sorted(clips)
    return merged, build_vaps(13, struct.unpack_from('>H', clip_bank, 12)[0], clips)


def node_parts(record):
    words = list(struct.unpack(f'>{len(record) // 4}I', record))
    if words[26] + 27 != len(words):
        raise ValueError('Unexpected effect node size')
    blocks, cursor = [], 27
    while cursor < len(words):
        kind, size = words[cursor], words[cursor + 1]
        if size < 2 or cursor + size > len(words):
            raise ValueError('Unexpected effect node block')
        blocks.append(words[cursor:cursor + size])
        cursor += size
    return words[:26], blocks


def node_record(header, blocks):
    body = [word for block in blocks for word in block]
    return struct.pack(f'>{26 + 1 + len(body)}I', *header, len(body), *body)


def node_properties(entries_):
    """A property block from (key, type code, values); flags the last entry."""
    words = []
    for index, (key, code, values) in enumerate(entries_):
        if index == len(entries_) - 1:
            code |= 0x800000
        words += [key, code, *values]
    return [0x0e, 2 + len(words)] + words


def trigger_node(header, key, root, signals):
    header = list(header)
    header[0] = key
    properties = []
    for index, (attack_event, effect_event, tree) in enumerate(signals):
        properties += [(crc(f'{key:08x}_signal_{index}'), 0x1000c, [EVENT_GROUP]),
                       (0x939b68a0, 0x201000c, [attack_event]),
                       (0x8541406c, 0x201000c, [effect_event]),
                       (0x557c4b4d, 0x201000c, [tree])]
    return node_record(header, [[0x08, 3, root], node_properties(properties)])


# Energy outburst's rainbow orbs come from Chromastone's hand weapon
# (Vilgax Attacks tree 3880ba5b, archetype c14f240f), whose particle emitter
# f9168a88 its code starts with events this game never raises. The emitter is
# rebuilt here from that archetype's values on the laser spark's node layout
# one per side, under a copy of the laser tree's root.
# shortcut: fixed beside the body, not on the hand bones. Five ways of starting
# an emitter under the hand weapons (root 52725e1f) drew nothing in captures;
# upgrade when a trace shows what those weapons receive during a special.
OUTBURST_SLOT = 0xba93374a
# (alien, slot) -> (forward speed, steers toward the stick). Jetray's R2 + circle
# (Lazer-Eye), R2 + triangle (Tri Shot) and R2 + square (Tail Zap) steer; the
# R2 + X sonic roll runs straight ahead, slowly.
# shortcut: constant speed even with the stick released.
TRAVELLING_SPECIALS = {('jetray', 0x239a66f0): (2.5, True), ('jetray', 0x549d5666): (2.5, True),
                       ('jetray', 0xba93374a): (2.5, True), ('jetray', 0xcaf9c3c5): (4.0, False)}
TRAVELLING_SPECIALS.update({
    ('cannonbolt', 0x549d5666): (4.5, False),
    ('cannonbolt', 0x239a66f0): (5.0, False),
    ('cannonbolt', 0xcaf9c3c5): (6.0, True),
})
EFFECT_SIGNALS[0xf69eafe4] = ([0xe6d20ed3], [0x38bf0e63])
OUTBURST_TREE = 0xed76b19f  # crc32('chromastone_outburst')
OUTBURST_SIDES = ((-0.7, 1.6, 0.0), (0.7, 1.6, 0.0))
OUTBURST_EMITTER = {
    0x9d762289: [30], 0xe7965460: [0x42c80000], 0x3de73088: [0x3e99999a], 0x0f26fef6: [0],
    0x297c98f1: [0x42b40000],  # 1.5708 rad; nodes give this angle in degrees.
    0x7cb5a078: [0x3d4ccccd] * 3, 0xd7943d68: [0x3d4ccccd] * 3, 0x7a76b57b: [0x3e4ccccd] * 3,
    0x118a27c7: [0x3e800000], 0x9c822a32: [0x3e800000], 0x27703ece: [0xbe4ccccd], 0xaa78333b: [0xbe4ccccd],
    0xc806a61b: [1], 0xf66c33f6: [1], 0xaa9373f5: [1],  # Flag word 0x16. (Without bit 4 the orbs vanished in-game.)
    0x5a6ce323: [0xff000064], 0xc365b299: [0xff005509], 0xb462820f: [0xff512000], 0x2a0617ac: [0xff3e0036],
    0x82660d72: [0x37084d44]}


def outburst_nodes(nodes):
    emitters = {}
    block = next(block for block in node_parts(nodes[0x89954ee0])[1] if block[0] == 0x0e)
    properties = [(key, code, OUTBURST_EMITTER.get(key, values))
                  for key, code, values in property_entries(block)]
    properties = properties[:[key for key, _, _ in properties].index(0x99194c8e)]  # The emitter group only.
    for index, position in enumerate(OUTBURST_SIDES):
        header, _ = node_parts(nodes[0x89954ee0])
        header[0] = crc(f'chromastone_outburst_{index}')
        header[7:14] = [struct.unpack('>I', struct.pack('>f', value))[0] for value in position] + [0, 0, 0, 0x3f800000]
        emitters[header[0]] = node_record(header, [[0x08, 3, OUTBURST_TREE], node_properties(properties)])
    header, blocks = node_parts(nodes[0x1474749e])
    header[0] = OUTBURST_TREE
    blocks = [[0x14, 3 + len(emitters), len(emitters)] + list(emitters) if block[0] == 0x14 else block
              for block in blocks]
    set_property(blocks, 0x865f80c0, 0x3fc00000)  # Stop after 1.5 s, the length of the spin.
    return {OUTBURST_TREE: node_record(header, blocks), **emitters}


EFFECT_TREES['chromastone'][OUTBURST_SLOT] = OUTBURST_TREE


# Goopershot (R2 + triangle): Vilgax Attacks' puff emitter 8cc9a5f1 hangs under a
# launcher group (a1ecc595) this game cannot run and crashed the form when its
# node was used. Rebuilt from parts known to work here: Chromastone's spark emitter
# group (as the outburst orbs use it) in Goop's greens, flown forward by a curve
# player and a position track like the gatling crystals', under a copy of the
# laser's tree root (which stops after a timer).
GOOP_SHOT_TREE = 0x911c74a4  # crc32('goop_shot')
EFFECT_SIGNALS[GOOP_SHOT_TREE] = ([0x216cb2c7, 0x8fd6e0fb], [0xf4331d1a, 0xe168c121])
EFFECT_SIGNALS[0x9f8ccf10] = ([0x8fd6e0fb], [0x7c4a867b, 0xe168c121])
GOOP_SHOT_EMITTER = {
    # Capture 3772 showed one small blob; Vilgax Attacks' Goopershot (frames 2944, 3653) is a
    # wide cloud of large soft puffs, so: more of them, longer lived, much bigger.
    0x9d762289: [12], 0xe7965460: [0x42a00000], 0x3de73088: [0x3f800000], 0x0f26fef6: [0],
    0x297c98f1: [0x42b40000],
    0x7cb5a078: [0x3d4ccccd] * 3, 0xd7943d68: [0x3d4ccccd] * 3, 0x7a76b57b: [0, 0xc0a00000, 0],
    0x118a27c7: [0x3f4ccccd], 0x9c822a32: [0x3f4ccccd], 0x27703ece: [0x3e99999a], 0xaa78333b: [0x3e99999a],
    0xc806a61b: [1], 0xf66c33f6: [1], 0xaa9373f5: [1],
    0x5a6ce323: [0xff14c27c], 0xc365b299: [0xff15d02d], 0xb462820f: [0xff1baf65], 0x2a0617ac: [0xff2cbc50],
    0x82660d72: [0x37084d44]}
GOOP_SHOT_SPEED = 4800.0  # Track units for the flight (the crystals' 1600 flew very fast here).


GOOP_DROP = 0x6c0d2e11  # key of the droplet mesh (a scaled copy of the blob)
GOOP_DROP_SCALE = 0.55
GOOP_HOSE_DROPS = 22
GOOP_HOSE_GAP = 430.0  # Track units between droplets (about 0.15 s)
GOOP_HOSE_FLIGHT = 1500.0
GOOP_HOSE_TREE = 0x9f8ccf10  # crc32('goop_hose'), checked at use
GOOP_BLOB_TREE = 0x911c74a4  # crc32('goop_shot')
GOOP_HOSE_EMITTER = {**GOOP_SHOT_EMITTER, 0x9d762289: [12], 0xe7965460: [0x42340000], 0x3de73088: [0x3f666666],
                     0x0f26fef6: [0x40400000],  # speed 3 along the node's forward axis
                     0x7cb5a078: [0x3da3d70a] * 3, 0xd7943d68: [0x3eb33333] * 3,  # jitter 0.08 m, 0.35 m/s
                     0x7a76b57b: [0, 0x3e99999a, 0],  # smoke drifts up a little
                     0x118a27c7: [0x3df5c28f], 0x9c822a32: [0x3df5c28f], 0x27703ece: [0x3e800000], 0xaa78333b: [0x3e800000],  # capture 2887: the cloud was far too big
                     0x5a6ce323: [0xff0a6a1c], 0xc365b299: [0xff0c8a22], 0xb462820f: [0xff085a14], 0x2a0617ac: [0xff10781c]}


GOOP_BLOB_SCALE = 2.2  # Capture 4283: the thrown blob was a small tadpole; Vilgax Attacks' is bigger.


def scale_mesh(record, scale):
    """An effect mesh scaled about its origin (positions are the first three floats of
    each vertex)."""
    layout, count, _, vertices, _, _ = mesh_parts(record)
    stride = {9: 20, 11: 44}[layout & 15]
    out = bytearray(record)
    for n in range(count):
        for axis in range(3):
            at = 372 + stride * n + 4 * axis
            value, = struct.unpack_from('>f', out, at)
            struct.pack_into('>f', out, at, value * scale)
    return bytes(out)


def flight_track(origin, distance, time, drop=True):
    """A position track (block 0x15) from origin straight ahead, then out of the world."""
    f = lambda value: struct.unpack('>I', struct.pack('>f', value))[0]
    track = ([0x15, 34, 0x050ad001, 0x00030003] + [0] * 7 + [f(v) for v in origin]
             + [f(time)] + [0] * 6 + [f(origin[0]), f(origin[1]), f(origin[2] + distance)]
             + [f(time + 1.0)] + [0] * 6 + [f(origin[0]), f(origin[1] - 1000.0), f(origin[2] + distance)])
    return track


def goop_effects(cs_nodes, goop_nodes):
    """Two trees: Acid Hose (R2 + circle), a stream of green puffs from Chromastone's
    spark emitter group, and Goopershot (R2 + triangle), his blob mesh thrown forward."""
    f = lambda value: struct.unpack('>I', struct.pack('>f', value))[0]
    result = {}
    # Acid Hose: smoke from a particle emitter fixed at his hand for as long as the
    # attack runs. Emitter keys, read from the emitter code (sub_821F17E8, 821F2C48):
    # 0f26fef6 is the speed along the node's forward axis, 7cb5a078 a start position
    # jitter and d7943d68 a start velocity jitter (nonzero ones make particles
    # world-space, so they trail behind); the earlier tries set the jitter to a few
    # metres a second and no forward speed, which scattered the puffs everywhere.
    key_tree, key_puff = crc('goop_hose'), crc('goop_hose_puffs')
    block = next(block for block in node_parts(cs_nodes[0x89954ee0])[1] if block[0] == 0x0e)
    properties = [(key, code, GOOP_HOSE_EMITTER.get(key, values)) for key, code, values in property_entries(block)]
    properties = properties[:[key for key, _, _ in properties].index(0x99194c8e)]
    origin = (0.25, 1.25, 0.45)  # At his hand.
    header, _ = node_parts(cs_nodes[0x89954ee0])
    header[0] = key_puff
    header[7:14] = [f(v) for v in origin] + [0, 0, 0, 0x3f800000]
    puff = node_record(header, [[0x08, 3, key_tree], node_properties(properties)])
    header, blocks = node_parts(cs_nodes[0x1474749e])
    header[0] = key_tree
    blocks = [[0x14, 4, 1, key_puff] if block[0] == 0x14 else block for block in blocks]
    set_property(blocks, 0x865f80c0, 0x41200000)  # The root stops after 10 s.
    result.update({key_tree: node_record(header, blocks), key_puff: puff})
    # Goopershot: the blob mesh with the puddle's own event groups (the ones that
    # make a mesh appear on the attack's start) and a flight track.
    key_tree, key_blob = crc('goop_shot'), crc('goop_blob')
    header, blocks = node_parts(goop_nodes[0xd313e756])
    props = next(block for block in blocks if block[0] == 0x0e)
    origin = (0.0, 1.1, 0.7)
    header = list(header)
    header[0] = key_blob
    header[7:14] = [f(v) for v in origin] + [0, 0, 0, 0x3f800000]
    blob = node_record(header, [[0x00, 4, 0x866df60c, 0x866df60c], [0x08, 3, key_tree], props,
                                flight_track(origin, 12.0, 8000.0)])
    header, blocks = node_parts(cs_nodes[0x1474749e])
    header[0] = key_tree
    blocks = [[0x14, 4, 1, key_blob] if block[0] == 0x14 else block for block in blocks]
    set_property(blocks, 0x865f80c0, 0x40a00000)
    result.update({key_tree: node_record(header, blocks), key_blob: blob})
    return result


# Tried and failed: the same emitter group on the hand weapons' root 52725e1f. A
# trace shows slots 0 and 1 do get the attack's start event (word 36) during the
# outburst, but no orbs drew, so that hit-volume node type does not run emitters.
EFFECT_SIGNALS[OUTBURST_TREE] = EFFECT_SIGNALS[0x1474749e]


GATLING_SECOND_EVENTS = {0x6812fccd, 0xf11bad77, 0x861c9de1, 0x18780842}


def timeline_without(block, events):
    """An event timeline block (0x17, nine-word frames ending in the event) minus
    the frames that raise the given events."""
    frames = [block[4 + 9 * i:13 + 9 * i] for i in range((len(block) - 4) // 9)]
    frames = [frame for frame in frames if frame[8] not in events]
    return [0x17, 4 + 9 * len(frames), block[2], len(frames) << 16 | len(frames)] + [word for frame in frames for word in frame]


UNKNOWN_GROUPS = {0xa1ecc595}


def without_groups(block, groups):
    """A property block minus the whole groups (header plus its properties) whose
    instance key is listed."""
    entries_, kept, skip = property_entries(block), [], False
    for entry in entries_:
        if entry[1] == 0x1000c:
            skip = entry[0] in groups
        if not skip:
            kept.append(entry)
    return node_properties(kept) if kept else [0x0e, 2]


def crystal_flight(key, block):
    """A crystal spike's blocks: the flight runs straight ahead from where it
    starts (Vilgax Attacks' end point drifts a metre down and two to the side), and
    a timer sends the spike its own stop event when the flight ends, which clears
    it from the world."""
    if block[0] == 0x15 and len(block) == 24:
        block = list(block)
        if key in CRYSTAL_PLACEMENT:
            block[11:14] = [struct.unpack('>I', struct.pack('>f', value))[0] for value in CRYSTAL_PLACEMENT[key]]
            block[23] = struct.unpack('>I', struct.pack('>f', CRYSTAL_PLACEMENT[key][2] + 15.0))[0]
        block[14] = struct.unpack('>I', struct.pack('>f', CRYSTAL_FLIGHT_TIME))[0]  # Flight length (was 1600).
        block[21], block[22] = block[11], block[12]
        block[23] = struct.unpack('>I', struct.pack('>f', struct.unpack('>f', struct.pack('>I', block[13]))[0] + 15.0))[0]
        block[15:21] = [0] * 6
        # The shot's two chest crystals fly apart at an angle (3 m to each side over 15 m).
        block[21] = struct.unpack('>I', struct.pack('>f', struct.unpack('>f', struct.pack('>I', block[11]))[0]
                                                    + CRYSTAL_SPREAD.get(key, 0.0)))[0]
        # A third key keeps the flight from wrapping around and starting again from the chest
        # (that looked like several crystals and flicker).
        block[1] = 34
        block[3] = 0x30003
        # The stop event does not remove the spike, so at the end of the flight it drops
        # 1000 m in one track unit: it leaves the world instead of hanging at the end.
        end_y, = struct.unpack('>f', struct.pack('>I', block[22]))
        block += ([struct.unpack('>I', struct.pack('>f', CRYSTAL_FLIGHT_TIME + 1.0))[0]] + [0] * 6
                  + [block[21], struct.unpack('>I', struct.pack('>f', end_y - 1000.0))[0], block[23]])
        return block
    if block[0] != 0x0e or not GATLING_TIMER_GROUP:
        return block
    entries_ = property_entries(block)
    # Tried: leaving out group e16f3a56 made the crystals vanish, so it stays.
    start = next(values[0] for entry, code, values in entries_ if entry == 0x8541406c)
    stop = next(values[0] for entry, code, values in entries_ if entry == 0xf7be9018)
    copy = [(entry, code, [{0x8541406c: start, 0x865f80c0: struct.unpack('>I', struct.pack('>f', CRYSTAL_LIFETIME))[0],
                            0xd058515c: stop}.get(entry, values[0])] if entry in (0x8541406c, 0x865f80c0, 0xd058515c) else values)
            for entry, code, values in GATLING_TIMER_GROUP]
    return node_properties(entries_ + [(crc(f'crystal_timer_{key:08x}'), 0x1000c, [0x6ad0de1a])] + copy)


def gatling_timers(block, start):
    """The root's property block with one copy of its timer group (6ad0de1a: on
    8541406c wait 865f80c0 s, then raise d058515c) per crystal."""
    entries_ = property_entries(block)
    first = next(index for index, (key, code, values) in enumerate(entries_) if code == 0x1000c and key == 0x6ad0de1a)
    last = next((index for index in range(first + 1, len(entries_)) if entries_[index][1] == 0x1000c), len(entries_))
    group = entries_[first + 1:last]
    GATLING_TIMER_GROUP[:] = group
    # The root itself stays up (9 s) while its timeline fires all four volleys.
    group = [(key, code, [0x41100000] if key == 0x865f80c0 else values) for key, code, values in group]
    entries_[first + 1:last] = group
    for event, delay in GATLING_TIMERS.items():
        copy = [(key, code, [{0x8541406c: start, 0x865f80c0: struct.unpack('>I', struct.pack('>f', delay))[0],
                              0xd058515c: event}.get(key, values[0])] if key in (0x8541406c, 0x865f80c0, 0xd058515c) else values)
                for key, code, values in group]
        entries_ += [(crc(f'chromastone_gatling_timer_{event:08x}'), 0x1000c, [0x6ad0de1a])] + copy
    return node_properties(entries_)


CRYSTAL_PALETTE = 0x4391b359


def rainbow_palette(record):
    """The crystals' 64x32 palette texture (DXT1) redrawn as a plain saturated
    rainbow along its width. The original's rows run from black to white, so the
    crystals' fixed row washed out to pale pastels here."""
    import colorsys
    from extract_discord_level_images import tiled_offset
    data = bytearray(len(record) - 128)
    def rgb565(hue):
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 0.8)
        return int(r * 31 + 0.5) << 11 | int(g * 63 + 0.5) << 5 | int(b * 31 + 0.5)
    for by in range(8):
        for bx in range(16):
            c0, c1 = rgb565(bx / 16 * 0.83), rgb565((bx + 1) / 16 * 0.83)
            if c0 == c1:
                c1 ^= 1
            if c0 < c1:
                c0, c1 = c1, c0  # c0 > c1 selects the four-colour mode.
            # Columns 0..3 blend c0 -> c1 (indices 0, 2, 3, 1 in four-colour mode).
            row = 0 | 2 << 2 | 3 << 4 | 1 << 6
            block = struct.pack('<HH', c0, c1) + bytes([row]) * 4
            offset = tiled_offset(bx, by, 16, 3)
            data[offset:offset + 8] = bytes(block[i ^ 1] for i in range(8))
    return record[:128] + bytes(data)


BEAM_MESH = 0xf404a61f
BEAM_THICKNESS = 0.55


def thin_beam(record, scale):
    """The laser beam mesh with its cross-section scaled. The mesh is a 1.14 m wide
    tube along z; this game's laser draw scales only its length, so the beam was
    about 2.5 times thicker than Vilgax Attacks' (whose laser group scales the width
    by 0.4)."""
    layout, count, _, vertices, _, _ = mesh_parts(record)
    out = bytearray(record)
    for n in range(count):
        at = 372 + 20 * n
        for axis in (0, 1):
            value, = struct.unpack_from('>f', out, at + 4 * axis)
            struct.pack_into('>f', out, at + 4 * axis, value * scale)
    return bytes(out)


def special_effects(vilgax, name, mesh_reference, color_reference, four_arms_nodes):
    code = ALIENS[name]
    archive = entries((vilgax / 'global' / f'e_{code}.xbx').read_bytes()) if EFFECT_TREES[name] else None
    nodes = {key: data for key, _, data in vaps_rows(archive[14])} if archive else {}
    if name == 'chromastone':
        nodes.update(outburst_nodes(nodes))
    if name == 'goop':
        cs = entries((vilgax / 'global' / 'e_cs.xbx').read_bytes())
        nodes.update(goop_effects({key: data for key, _, data in vaps_rows(cs[14])}, nodes))
    converted = {}
    offsets = {}
    for tree in EFFECT_TREES[name].values():
        pending = [tree]
        while pending:
            key = pending.pop()
            if key in converted:
                continue
            header, blocks = node_parts(nodes[key])
            header[1] = NODE_REVISION
            blocks[:] = [[0x14, 3 + len(kept), len(kept)] + kept if block[0] == 0x14 else block for block in blocks
                         for kept in [[child for child in block[3:] if child not in REMOVED_NODES]]]
            if header[6] in ARCHETYPE_EVENTS:
                if not any(block[0] == 0x0e for block in blocks):
                    blocks.append([0x0e, 2])
                blocks[:] = [block if block[0] != 0x0e else with_events(block, ARCHETYPE_EVENTS[header[6]],
                                                                        crc('create'), crc('destroy'))
                             for block in blocks]
            if header[6] in ARCHETYPE_DEFAULTS:
                blocks[:] = [block if block[0] != 0x0e else with_defaults(block, ARCHETYPE_DEFAULTS[header[6]])
                             for block in blocks]
                for block in blocks:
                    if block[0] == 0x0e and header[6] in ARCHETYPE_GROUPS:
                        block[-len(block) + 2:] = node_properties(property_entries(block) + ARCHETYPE_GROUPS[header[6]])[2:]
                        block[1] = len(block)
                header[6] = crc('root')
            # Node types name an archetype; ones this game lacks would create
            # nothing, so those nodes become plain nodes driven by their own
            # property groups.
            if key == GATLING_TREE:
                # The timeline raises a second event per shot (0.8 s after the first);
                # the crystals' group e16f3a56 hears it and re-triggers, which showed as
                # a crystal coming out, failing and coming out again. Only the first
                # event per shot is kept.
                blocks[:] = [timeline_without(block, GATLING_SECOND_EVENTS) if block[0] == 0x17 else block for block in blocks]
            if key == GATLING_TREE:
                for block in blocks:
                    if block[0] == 0x0e:
                        entries_ = property_entries(block)
                        first = next(i for i, (entry, code, values) in enumerate(entries_) if code == 0x1000c and entry == 0x6ad0de1a)
                        last = next((i for i in range(first + 1, len(entries_)) if entries_[i][1] == 0x1000c), len(entries_))
                        GATLING_TIMER_GROUP[:] = entries_[first + 1:last]
            # A property group this game has no component for (Goop's a1ecc595) leaves a
            # null component in the node, and the node loader (sub_821E36B8) then calls
            # through it: a crash when the form is made. Such groups are dropped.
            blocks[:] = [without_groups(block, UNKNOWN_GROUPS) if block[0] == 0x0e else block for block in blocks]
            if name == 'goop':
                # Goop's mesh group carries 9e7e4e69 = 1. The puddle then stayed at the
                # spot where the form was made instead of following him; try it off.
                set_property(blocks, 0x9e7e4e69, 0)
            if header[6] == CRYSTAL_ARCHETYPE:
                blocks[:] = [block if block[0] != 0x0e else with_defaults(block, CRYSTAL_DEFAULTS) for block in blocks]
                set_property(blocks, 0xe7965460, 0)  # The spark emitter's rate: it left a trail in the world.
                blocks[:] = [crystal_flight(key, block) for block in blocks]
            if header[6] in MISSING_NODE_TYPES:
                # The archetype also named the node's mesh. Nodes here carry
                # it as block 0 {mesh, vertex colors}.
                if header[6] in ARCHETYPE_MESHES and not any(block[0] == 0 for block in blocks):
                    blocks.insert(0, [0x00, 4, ARCHETYPE_MESHES[header[6]], ARCHETYPE_MESHES[header[6]]])
                header[6] = crc('root')
            set_property(blocks, EFFECT_PACKAGE, crc(f'g_{code}'))
            # Sprites are opaque DXT1 on black: draw them additively.
            set_property(blocks, 0x22944c2a, crc('additive'))
            # Beams carry Vilgax Attacks' damage types (370021c8, b7840510: masks
            # 128 and 256 in sub_82101540). Use the punch type 11abfea5 (mask 1),
            # which this game's breakable objects and enemies react to.
            set_property(blocks, 0xb823fe47, 0x11abfea5)
            for entry, value in NODE_OVERRIDES.get(key, {}).items():
                set_property(blocks, entry, value)
            if key in CRYSTAL_PLACEMENT:
                header[7:10] = [struct.unpack('>I', struct.pack('>f', value))[0] for value in CRYSTAL_PLACEMENT[key]]
            if key in NODE_PLACEMENT:
                header[7:14] = [struct.unpack('>I', struct.pack('>f', value))[0]
                                for value in NODE_PLACEMENT[key]] + [0, 0, 0, 0x3f800000]
            if key in offsets:
                for axis in range(3):
                    value, = struct.unpack('>f', struct.pack('>I', header[7 + axis]))
                    header[7 + axis], = struct.unpack('>I', struct.pack('>f', value + offsets[key][axis]))
            converted[key] = node_record(header, blocks)
            for block in blocks:
                if block[0] == 0x14:
                    pending.extend(child for child in block[3:] if child in nodes)
                    if key in EFFECT_OFFSETS:
                        offsets.update({child: EFFECT_OFFSETS[key] for child in block[3:]})
    pending = [FOUR_ARMS_HIT_VOLUMES]
    while pending:
        key = pending.pop()
        if key in converted:
            continue
        converted[key] = four_arms_nodes[key]
        for block in node_parts(four_arms_nodes[key])[1]:
            if block[0] == 0x14:
                pending.extend(block[3:])
    # The fifth weapon slot follows the character itself (no bone), and a
    # weapon's children receive the attack's start/stop events (words 36/37).
    # So each special's tree hangs under that weapon and listens for its own
    # attack's events in place of Vilgax Attacks' "create"/"destroy" family.
    root = effect_root(name)
    root_header, root_blocks = node_parts(four_arms_nodes[FOUR_ARMS_EFFECT_ROOT])
    children = []
    for slot in SPECIAL_REACH[name]:
        tree = EFFECT_TREES[name].get(slot)
        start, stop = effect_events(name, slot)
        starts, stops = EFFECT_SIGNALS.get(tree, ((), ()))
        renamed = {event: start for event in starts}
        renamed.update({event: stop for event in stops})
        pending, seen = [tree] if tree else [], set()
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            header, blocks = node_parts(converted[key])
            for block in blocks:
                if block[0] == 0x14:
                    pending.extend(block[3:])
                cursor = 2
                while block[0] == 0x0e and cursor < len(block):
                    size = (block[cursor + 1] & 0xffff) // 4
                    if block[cursor + 1] & 0xff000000 == 0x02000000:
                        # The root must not unload itself between uses.
                        if key == tree and block[cursor] in (0xd21b0463, 0xd050838c):
                            block[cursor + 2] = 0
                        elif block[cursor + 2] in renamed:
                            block[cursor + 2] = renamed[block[cursor + 2]]
                    cursor += size
            if key == tree:
                blocks[:] = [[0x08, 3, root]] + [block for block in blocks if block[0] != 0x08]
                if key == GATLING_TREE:
                    set_property(blocks, 0x6f949845, 0x3ea8f5c3)  # Timeline speed 0.33: it ran about three times too fast.
                    blocks[:] = [gatling_timers(block, start) if block[0] == 0x0e else block for block in blocks]
            converted[key] = node_record(header, blocks)
        shockwave = crc(f'{name}_special_{slot:08x}_shockwave')
        converted[shockwave] = shockwave_node(four_arms_nodes, shockwave, root, start,
                                              SPECIAL_REACH[name][slot])
        children += [tree, shockwave] if tree else [shockwave]
    root_header[0] = root
    properties = [block for block in root_blocks if block[0] == 0x0e]
    converted[root] = node_record(root_header, [[0x14, 3 + len(children), len(children)] + children] + properties)

    if archive is None:
        return dict(nodes=converted, meshes={}, textures={}, colors={}, curves=[])
    mesh_bank = dict(table(archive[4])) if name != 'cannonbolt' else {}
    color_bank = dict(table(archive[3])) if name != 'cannonbolt' else {}
    if name == 'goop':
        mesh_bank[GOOP_DROP] = scale_mesh(mesh_bank[0x866df60c], GOOP_DROP_SCALE)
        color_bank[GOOP_DROP] = color_bank[0x866df60c]
    meshes, textures, colors = {}, set(), {}
    for key, record in mesh_bank.items():
        if name == 'goop' and key == 0x866df60c:
            record = scale_mesh(record, GOOP_BLOB_SCALE)
        if name == 'chromastone' and key == BEAM_MESH:
            record = thin_beam(record, BEAM_THICKNESS)
        meshes[key], used = convert_mesh(record, mesh_reference)
        textures.update(used)
    for key, record in color_bank.items():
        flags, = struct.unpack_from('>I', record)
        vertex_count, = struct.unpack_from('>I', meshes[key], 4)
        if flags != 0x10000 or len(record) != 16 + 4 * vertex_count:
            raise ValueError('Unexpected effect vertex colors')
        address = struct.unpack_from('<I', meshes[key], 28)[0] - 344
        # Six spikes overlap on each volley's path and the sprites draw additively, so
        # at full strength they saturate to white; dim each one (the palette keeps
        # its hues), which brings back the rainbow.
        if name == 'chromastone' and key == BEAM_MESH:
            dimmed = bytes([0x90]) * (len(record) - 16)  # Less white core now that the beam is thin.
        elif name == 'chromastone' and key in CRYSTAL_MESHES:
            dimmed = bytes([0xd0]) * (len(record) - 16)
        elif name == 'chromastone' and key in DOME_MESHES:
            dimmed = bytes([0x70]) * (len(record) - 16)  # The prismatic dome was a white-out.
        else:
            dimmed = record[16:]
        colors[key] = (record[:12] + color_reference[12:16] + bytes(4) + struct.pack('<I', address)
                       + bytes(8) + dimmed)
    images = {key: convert_texture(data) for key, data in table(archive[0]).items()}
    if name == 'chromastone' and CRYSTAL_PALETTE in images and 0x458e037e in meshes:
        # The crystals get a palette of their own; the laser beam keeps the original.
        crystal_palette = crc('chromastone_crystal_palette')
        images[crystal_palette] = rainbow_palette(images[CRYSTAL_PALETTE])
        old, new = struct.pack('>I', CRYSTAL_PALETTE), struct.pack('>I', crystal_palette)
        if meshes[0x458e037e].count(old) != 1:
            raise ValueError('Unexpected crystal material')
        meshes[0x458e037e] = meshes[0x458e037e].replace(old, new)
    # Particle emitters name their sprite (property 82660d72, "texture") from
    # Vilgax Attacks' global package.
    shared = None
    for node in converted.values():
        for block in node_parts(node)[1]:
            cursor = 2
            while block[0] == 0x0e and cursor < len(block):
                size = (block[cursor + 1] & 0xffff) // 4
                sprite = block[cursor + 2]
                if block[cursor] == 0x82660d72 and sprite and sprite not in images:
                    if shared is None:
                        shared = table(entries((vilgax / 'global/global.xbx').read_bytes())[0])
                    if sprite in shared:
                        images[sprite] = convert_texture(shared[sprite])
                cursor += size
    if not textures <= set(images):
        raise ValueError('Effect mesh texture missing')
    curves = [(key, flags, data) for key, flags, data in vaps_rows(archive[9]) if key in converted] if 9 in archive else []
    return dict(nodes=converted, meshes=meshes, textures=images, colors=colors, curves=curves)


# Special-attack sounds. An attack record names its sound in word 38; Four
# Arms' come from his own FMOD project (package section 24: an FEV event
# file and an FSB sample bank, both keyed by crc32 of the project name).
# The imported form gets a project of its own: Four Arms' event file under
# the new name, played from Vilgax Attacks' XMA bank for the alien (the
# format this game's other alien banks use), with the special events
# pointed at the alien's samples. sounds.txt adds their sounds.ddf entries.
SOUND_PROJECTS = {'chromastone': ('chrmstn', 'swpchrom.fsb'), 'jetray': ('jetrays', 'swpjetry.fsb'),
                  'goop': ('goopsnd', 'swpgoop.fsb'), 'cannonbolt': ('cboltva', 'swpcbolt.fsb')}
SPECIAL_SOUNDS_ENABLED = {'chromastone', 'jetray', 'goop', 'cannonbolt'}
FOUR_ARMS_PROJECT = b'fourarm'
# Slot: (sound name, Four Arms event index, Vilgax Attacks sample).
SPECIAL_SOUNDS = {
    'chromastone': {
        0x549d5666: ('chrmstone_gatling_gun', 0, 'chrom_gatling_gun.wav'),
        0x239a66f0: ('chrmstone_laserbeam', 2, 'chrom_laserbeam.wav'),
        0xcaf9c3c5: ('chrmstone_prismatic_explo', 15, 'chrom_prismatic_explosion.wav'),
        # Vilgax Attacks has no separate energy outburst sample.
        0xba93374a: ('chrmstone_energy_outburst', 19, 'chrom_prismatic_explosion.wav')},
    'jetray': {
        0x549d5666: ('jetray_lasereye', 0, 'jetray_lasereye.wav'),
        0x239a66f0: ('jetray_trishot', 2, 'jetray_trishot.wav'),
        0xba93374a: ('jetray_whip_zap', 15, 'jetray_whip_zap.wav'),
        0xcaf9c3c5: ('jetray_sonic_dash', 19, 'jetray_sonic_dash.wav')},
    'goop': {
        0x549d5666: ('goop_acid_hose', 0, 'goop_acid_hose_b.wav'),
        0x239a66f0: ('goop_goopershot', 2, 'goop_goopershot.wav'),
        0xba93374a: ('goop_puddle_uppercut', 15, 'puddle_uppercut_01.wav'),
        0xcaf9c3c5: ('goop_splitkick', 19, 'goop_split_kick.wav')}}
SPECIAL_SOUNDS['cannonbolt'] = {
    0x549d5666: ('cbolt_ball_dash', 0, 'cbolt_ball_dash_01.wav'),
    0x239a66f0: ('cbolt_superball', 2, 'cbolt_superball.wav'),
    0xba93374a: ('cbolt_powerflop', 15, 'cbolt_powerflop.wav'),
    0xcaf9c3c5: ('cbolt_burnout', 19, 'canbolt_burnout_chargeup_loop.'),
}
# Four Arms' events by their samples (four_aftershock, concussion clap,
# seismic upper, spinning crusher).
FOUR_ARMS_EVENT_SAMPLES = {0: 62, 2: 64, 15: 81, 19: 82}
# Everyday sounds. Attack and person records name Four Arms' sounds (punches,
# jump, hurt); each imported form gets sounds of its own on Four Arms' event
# ids: (suffix, event id). Four Arms' samples for those events (hurt 65-69,
# jump 70-73, land 74-76, light 77-80) are replaced by the form's samples
# of the matching kind, found by sample name.
EVERYDAY_SOUNDS = (('hurt', 5), ('jump', 6), ('land_big', 8), ('land_small', 9),
                   ('light1', 10), ('light2', 11), ('light3', 12), ('heavy1', 12), ('heavy2', 11))
SOUND_PREFIX = {'chromastone': 'chrmstone', 'jetray': 'jetray', 'goop': 'goop'}
# Vilgax Attacks' clips already name some of these (jump double, spit).
EXTRA_SOUNDS = {'jetray': (('double', 6),), 'goop': (('jump_double', 6), ('spit', 12))}
SOUND_KINDS = {
    'chromastone': {'hurt': 'hitreact', 'jump': 'jumpexert', 'land': 'chrmstone_land', 'light': 'chrmstone_ligh'},
    'jetray': {'hurt': 'hitreact', 'jump': 'jumpexert', 'land': 'jumpland', 'light': 'atkreact_(01|19|22|23)'},
    'goop': {'hurt': 'hitreact', 'jump': 'jumpexert', 'land': 'jumpland', 'light': '(light|heavy)_attack'}}
SOUND_PREFIX['cannonbolt'] = 'cbolt'
SOUND_KINDS['cannonbolt'] = {'hurt': 'hitreact', 'jump': 'jumpexert',
                            'land': 'land_feet|jumpland', 'light': 'canbolt_light'}
FOUR_ARMS_SAMPLE_KINDS = {'hurt': range(65, 70), 'jump': range(70, 74), 'land': range(74, 77), 'light': range(77, 81)}
# Four Arms' sound names in records, and the form's sound that replaces each.
SOUND_SWAPS = {'four_hurt': 'hurt', 'four_jump': 'jump', 'four_light1': 'light1', 'four_light2': 'light2',
               'four_light3': 'light3', 'four_pounce': 'heavy1', 'four_stomp': 'heavy1',
               'four_counter': 'heavy2', 'four_jump_attack': 'heavy2'}


def everyday_sounds(name):
    prefix = SOUND_PREFIX[name]
    return [(f'{prefix}_{suffix}', event) for suffix, event in EVERYDAY_SOUNDS + EXTRA_SOUNDS.get(name, ())]


def swap_sounds(data, name):
    """Replace Four Arms' sound names (whole words) with this form's."""
    if name not in SPECIAL_SOUNDS_ENABLED:
        return data
    swaps = {crc(old): crc(f'{SOUND_PREFIX[name]}_{new}') for old, new in SOUND_SWAPS.items()}
    words = list(struct.unpack(f'>{len(data) // 4}I', data[:len(data) // 4 * 4]))
    words = [swaps.get(word, word) for word in words]
    return struct.pack(f'>{len(words)}I', *words) + data[len(data) // 4 * 4:]


def fsb_samples(bank):
    if bank[:4] != b'FSB4':
        raise ValueError('Unexpected sample bank')
    count, header_size = struct.unpack_from('<II', bank, 4)
    samples, cursor, data = [], 48, 48 + header_size
    for index in range(count):
        size, = struct.unpack_from('<H', bank, cursor)
        name = bank[cursor + 2:cursor + 32].split(b'\0')[0].decode('latin1')
        length, compressed = struct.unpack_from('<II', bank, cursor + 32)
        frequency, = struct.unpack_from('<I', bank, cursor + 52)
        samples.append((name, length, frequency))
        cursor += size
    return samples


def sound_project(vilgax, four_arms_rows, name):
    project, bank_file = SOUND_PROJECTS[name]
    project = project.encode('ascii')
    if len(project) != len(FOUR_ARMS_PROJECT):
        raise ValueError('Project name must keep the event file layout')
    (event_key, _, event_row), (_, _, bank_row) = four_arms_rows
    if event_row[32:36] != b'FEV1' or bank_row[32:36] != b'FSB4' or event_key != crc('fourarm'):
        raise ValueError('Unexpected Four Arms sound project')
    bank = bytearray((vilgax / 'global/snd_xbx' / bank_file).read_bytes())
    struct.pack_into('<I', bank, 20, struct.unpack_from('<I', bank_row, 32 + 20)[0])
    samples = fsb_samples(bytes(bank))
    by_name = {sample[0]: index for index, sample in enumerate(samples)}
    targets = {FOUR_ARMS_EVENT_SAMPLES[event]: by_name[sample]
               for _, event, sample in SPECIAL_SOUNDS[name].values()}
    for kind, pattern in SOUND_KINDS[name].items():
        matching = [index for index, sample in enumerate(samples) if re.search(pattern, sample[0])]
        if not matching:
            raise ValueError(f'No {kind} samples in the {name} sound bank')
        for position, source in enumerate(FOUR_ARMS_SAMPLE_KINDS[kind]):
            targets[source] = matching[position % len(matching)]
    fallback = targets[FOUR_ARMS_SAMPLE_KINDS['light'][0]]
    events = bytearray(event_row[32:])
    marker = struct.pack('<I', len(FOUR_ARMS_PROJECT) + 1) + FOUR_ARMS_PROJECT + b'\0'
    # The wave bank entry (offset 16: name, two words, then the first 8 bytes
    # of the FSB's own hash at FSB offset 24) must match the paired bank.
    if events[16:28] != marker or events[40:48] != bank_row[32 + 24:32 + 32]:
        raise ValueError('Unexpected Four Arms wave bank entry')
    events[40:48] = bank[24:32]
    # Waveform entries: wav path, u32 8, project name, u32 sample index, u32
    # length (ms). The same name also opens the bank, project and group
    # entries, so only entries after a .wav path are waveforms.
    cursor, waves = events.find(marker), 0
    while cursor >= 0:
        at = cursor + len(marker)
        if not events[:cursor].endswith(b'.wav\0'):
            cursor = events.find(marker, at)
            continue
        index, = struct.unpack_from('<I', events, at)
        sample = targets.get(index, fallback)
        _, length, frequency = samples[sample]
        struct.pack_into('<II', events, at, sample, length * 1000 // frequency)
        waves += 1
        cursor = events.find(marker, at)
    if not waves:
        raise ValueError('Four Arms event file has no waveforms')
    events = bytes(events).replace(b'/fourarm/', b'/' + project + b'/').replace(
        b'\0' + FOUR_ARMS_PROJECT + b'\0', b'\0' + project + b'\0').replace(
        marker, struct.pack('<I', len(project) + 1) + project + b'\0')
    if FOUR_ARMS_PROJECT + b'\0' in events:
        raise ValueError('Four Arms project name left in event file')
    key = crc(project.decode())
    rows = []
    for prefix, body in ((event_row[:32], events), (bank_row[:32], bytes(bank))):
        prefix = bytearray(prefix)
        struct.pack_into('>I', prefix, 4, len(body))
        struct.pack_into('>I', prefix, 20, key)
        if struct.unpack_from('>I', prefix, 24)[0]:
            struct.pack_into('>I', prefix, 24, key)
            # Marker the game's own XMA banks carry (Four Arms' ADPCM bank differs).
            struct.pack_into('>I', prefix, 28, 0x00393400)
        rows.append((key, 0, bytes(prefix) + body))
    listed = [(sound, event) for sound, event, _ in SPECIAL_SOUNDS[name].values()] + everyday_sounds(name)
    lines = ''.join(f'<sound name="{sound}" id="{event}" swpgroupid="0" prjid="{project.decode()}"/>\n'
                    for sound, event in listed)
    return build_vaps(24, 5, rows), lines.encode('ascii')


WHEEL_ICONS = {'chromastone': 0x05e1c713, 'jetray': 0xb458a502, 'goop': 0x7206e5bc, 'cannonbolt': 0xf3b76348}
FOUR_ARMS_WHEEL_ICON = 0xbc29c46d
FOUR_ARMS_RING_PICTURE = 0xc6baa5e5  # The R3 ring's 256x256 picture (gtex_s.xbx)
HOLOGRAM_FUNCTION = 0xb09930d3  # Hologram index -> texture key; the registration calls it with Four Arms' index
# Transformation callout: the form's voice resolver answers this event with a
# descriptor in sounds.ddf, whose sample the launcher adds to every voice bank.
NAME_CALLOUT_EVENT = 0x8768763b
FOUR_ARMS_VOICE = 0x6b894905  # Each mission's own resolver for Four Arms.
CALLOUT_SAMPLES = {'chromastone': b'chromastone.wav', 'jetray': b'jetray.wav', 'goop': b'goop.wav', 'cannonbolt': b'cannonbolt.wav'}


def callout_bank(vilgax, voice_bank, name):
    """One-sample FSB4 bank holding the alien's Vilgax Attacks name callout."""
    source = (vilgax / 'global/snd_xbx/core.fsb').read_bytes()
    count, headers, _ = struct.unpack_from('<III', source, 4)
    at, offset, found = 48, 48 + headers, None
    for _ in range(count):
        size, = struct.unpack_from('<H', source, at)
        packed, = struct.unpack_from('<I', source, at + 36)
        if source[at + 2:at + 32].split(b'\0')[0] == CALLOUT_SAMPLES[name]:
            if found:
                raise ValueError('Ambiguous name callout')
            found = (bytearray(source[at:at + size]), source[offset:offset + packed])
        at += size
        offset += packed
    if not found:
        raise ValueError('Name callout missing from Vilgax Attacks')
    header, data = found
    if len(header) != 112 or len(data) % 2048:
        raise ValueError('Unexpected name callout layout')
    sample = f'{name}_name_callout_01.wav'.encode('ascii')[:30]
    header[2:32] = sample + bytes(30 - len(sample))
    table_size = (48 + len(header) + 31) // 32 * 32 - 48
    bank = bytearray(voice_bank[:48])
    struct.pack_into('<III', bank, 4, 1, table_size, len(data))
    return bytes(bank + header + bytes(table_size - len(header)) + data)


def voice_resolver(prefix):
    """Answer the name callout event; leave every other event to Four Arms'."""
    c = Code()
    c.emit(4 << 8 | 5, NAME_CALLOUT_EVENT)
    c.binary(0x10, 5, 0, 4)
    c.false(5, 'other')
    c.emit(4 << 8 | 5, crc(f'{prefix}_name_callout_01'))
    c.emit(4 << 8 | 0x22)
    c.label('other')
    c.call(FOUR_ARMS_VOICE, [0, 1], 4)
    c.emit(4 << 8 | 0x22)
    return c.finish()


# Registration. A new form reuses the structure of the imported Four Arms
# form: the same registration block, setup callback and attack table layout,
# with its own form ID, model, animations and attack IDs.
FORM_IDS = 0xe1003dc4
PLATFORM_FORM = 0x4b5b4447
PLATFORM_UPGRADES = 0x0fa12932
FOUR_ARMS_INIT = 0x39a05949
FOUR_ARMS_ATTACKS = 0x2c00026b
FORM_IDENTITIES = {'chromastone': (20, 13.0), 'jetray': (21, 14.0), 'goop': (22, 15.0), 'cannonbolt': (23, 16.0)}  # Form ID, roster ordinal.
UPGRADE_TABLE = 0xe6db5005

# Four Arms' animations, by the matching Vilgax Attacks animation. Special
# attacks follow their ability slot rather than their animation name.
CLIP_ROLES = {
    'atk_close_fwd_01': 'punch_01', 'atk_close_fwd_out_01': 'punch_out_01',
    'atk_close_fwd_02': 'punch_02', 'atk_close_fwd_out_02': 'punch_out_02',
    'atk_close_fwd_03': 'punch_03', 'atk_close_fwd_out_03': 'punch_out_03',
    'atk_close_bwd_01': 'punch_04', 'atk_fin_fwd_01': 'punch_04', 'atk_fin_fwd_02': 'punch_03',
    'atk_far_fwd_travel_01': 'run_01', 'atk_far_fwd_01': 'punch_02', 'atk_far_fwd_out_01': 'punch_out_02',
    'atk_far_bwd_travel_01': 'run_01', 'atk_far_bwd_01': 'punch_01', 'atk_far_bwd_out_01': 'punch_out_01',
    'counter_atk_travel_01': 'run_01', 'counter_atk_01': 'punch_04', 'counter_atk_out_01': 'punch_out_04',
    'atk_ground_fwd_travel_01': 'run_01', 'atk_ground_fwd_01': 'punch_03',
    'atk_ground_fwd_out_01': 'punch_out_03', 'airattack_01': 'airattack_01',
}
# Experiment: the clip the far/ground/counter attacks play while the alien travels to the enemy. Four Arms has a dedicated
# travel clip there; Vilgax Attacks has none, so these slots hold its run clip. COSMIC_TRAVEL_CLIP names another
# Vilgax Attacks clip (e.g. jump_01) to try in its place.
if os.environ.get('COSMIC_TRAVEL_CLIP'):
    for _travel in [name for name in CLIP_ROLES if name.endswith('_travel_01')]:
        CLIP_ROLES[_travel] = os.environ['COSMIC_TRAVEL_CLIP']
# Hit reactions in Four Arms' combat configuration ("person" record).
REACTION_CLIPS = {
    'gethit_front_01': 'gethit_01', 'gethit_behind_01': 'gethit_01', 'knockback_01': 'fall_01',
    'gethit_front_fall_01': 'fall_01', 'gethit_behind_fall_01': 'fall_01',
}
FOUR_ARMS_PERSON = 0x8f53d987
# Big Chill's person record (globals.ds names it in his setup script) is the one
# of the movement records that differs from Four Arms' in glide settings only:
# double jump speed (0x44), 0x7c, and the block 0x10c..0x120. Jetray, who
# double jumps and then glides in Vilgax Attacks, takes them. (An imported
# alien's person record is a copy of Four Arms'.)
BIG_CHILL_PERSON = 0x823fc04a
GLIDE_FIELDS = (0x44, 0x7c, 0x10c, 0x110, 0x118, 0x120)
GLIDERS = {'jetray'}
# Goop double jumps in Vilgax Attacks but does not glide: only the double jump speed (0x44).
DOUBLE_JUMPERS = {'goop'}
# A set of animation roles: entries of 28 bytes after a two-word header, each
# ending in a role byte. This game and Vilgax Attacks number the glide roles
# differently (and this game's set has interact entries the other lacks), so a
# glider's glide entries take this game's role numbers (read from Big Chill's
# set, which only supplies the numbers; every clip stays Vilgax Attacks').
CD_GLIDE_ROLES = {'glide_in_01': (0x2e,), 'glide_forward_01': (0x2f, 0x30, 0x31), 'glide_out_01': (0x32,),
                  'glide_land_01': (0x38,)}
CD_LATE_ROLES = {0x2d, 0x2e, 0x2f, 0x30, 0x31, 0x32, 0x38, 0x39, 0x3a, 0x3d, 0x3e}


def cd_animation_set(record, names):
    """Vilgax Attacks' animation set with this game's glide role numbers, and
    its double-jump clip under role 0x13. Roles the code plays are the role
    byte minus one (fall plays 23-25 for bytes 0x18-0x1a, the first jumps 16 and
    17 for 0x11 and 0x12, the glide 45 and 49 for 0x2e and 0x32), so the double
    jump's 18 is byte 0x13, which neither game's set fills."""
    words = list(struct.unpack(f'>{len(record) // 4}I', record))
    by_name = {name: key for key, name in names.items()}
    seen = {}
    for entry in range(words[0]):
        at = 2 + 7 * entry
        name, role = names.get(words[at]), words[at + 6] >> 24
        if name in CD_GLIDE_ROLES:
            new = CD_GLIDE_ROLES[name][seen.get(name, 0)]
            seen[name] = seen.get(name, 0) + 1
        elif name == 'land_01' and role == 0x2b:
            new = 0x2d
        elif role == 0x05:
            new = 0x49
        elif role in CD_LATE_ROLES:
            new = 0xfe  # Another role here, a clash with this game's late numbers.
        else:
            new = role
        words[at + 6] = new << 24 | words[at + 6] & 0xffffff
    # The glide code plays only its first clip once (role 45) and nothing after it,
    # so that slot holds the looping glide pose rather than the short lead-in.
    # The record holds more than one table of entries, so every use of the lead-in clip is replaced, not only the
    # first table's. The game maps role 45 to two further entries that name the knockdown-out clip in this set
    # (found with the glide pose test), and those take the glide pose as well.
    if 'glide_forward_01' in by_name:
        for clip in ('glide_in_01', 'knockdown_out_01'):
            if clip in by_name:
                words = [by_name['glide_forward_01'] if word == by_name[clip] else word for word in words]
    spare = next((e for e in range(words[0]) if words[2 + 7 * e + 6] >> 24 == 0xfe), None)
    double = next((e for e in range(words[0]) if names.get(words[2 + 7 * e]) == 'jumpdouble_01'), None)
    if spare is not None and double is not None:
        words[2 + 7 * spare:9 + 7 * spare] = words[2 + 7 * double:9 + 7 * double]
        words[8 + 7 * spare] = 0x13 << 24 | words[8 + 7 * spare] & 0xffffff
    return struct.pack(f'>{len(words)}I', *words)
FOUR_ARMS_SPECIAL_EFFECTS = 0x3cdbef3d  # Fifth effect root attached at creation.
FOUR_ARMS_ANIMATION_SET = 0x5d5a8175
SPECIAL_CLIPS = {'chromastone': {0x549d5666: 'gatlinggun_01', 0x239a66f0: 'laserbeam_01',
                                 0xba93374a: 'energyoutburst_01', 0xcaf9c3c5: 'prismaticexplosion_01'},
                 'jetray': {0x549d5666: 'lasereye_01', 0x239a66f0: 'trishot_01',
                            0xba93374a: 'whipzap_01', 0xcaf9c3c5: 'sonicdash_run_01'},
                 'goop': {0x549d5666: 'acidhose_01', 0x239a66f0: 'goopershot_01',
                          0xba93374a: 'puddleuppercut_01', 0xcaf9c3c5: 'splitkick_01'}}


SPECIAL_CLIPS['cannonbolt'] = {0x549d5666: 'balldash_01', 0x239a66f0: 'superball_01',
                              0xba93374a: 'powerflop_01', 0xcaf9c3c5: 'burnout_run_01'}

# Lead-in and recovery animations of specials that have them.
SPECIAL_EDGES = {'chromastone': {0x239a66f0: ('laserbeam_in_01', 'laserbeam_out_01')},
                 'jetray': {0xcaf9c3c5: ('sonicdash_in_01', 'sonicdash_out_01')}}

SPECIAL_EDGES['cannonbolt'] = {0xcaf9c3c5: ('burnout_in_01', 'burnout_out_01')}


def crc(name):
    return zlib.crc32(name.lower().encode('ascii'))


def ddf_records(blob):
    if blob[:4] != b'\x1b\xad\xba\xbe':
        raise ValueError('Unsupported data file')
    result, cursor = {}, 4
    while cursor < len(blob):
        header = blob[cursor:cursor + 24]
        size, = struct.unpack_from('>I', header, 20)
        result[struct.unpack_from('>I', header)[0]] = (header, blob[cursor + 24:cursor + 24 + size])
        cursor += 24 + size
    if cursor != len(blob):
        raise ValueError('Truncated data file')
    return result


def original(path):
    backup = path.with_name(path.name + '.cosmic-original')
    return (backup if backup.is_file() else path).read_bytes()


def replace_arguments(code, values, strings=()):
    """Swap constant operands of whole VM tokens, never partial words."""
    words, tokens = decode(code)
    words = list(words)
    for at, kind in tokens:
        if kind in (3, 5, 7, 8, 0x17, 0x19, 0x20) and words[at + 1] in values:
            words[at + 1] = values[words[at + 1]]
    result = bytearray(struct.pack(f'>{len(words)}I', *words))
    for old, new in strings:
        if len(old) != len(new) or result.count(old) != 1:
            raise ValueError('Unexpected registration string')
        result = result.replace(old, new)
    return bytes(result)


def attack_table(four_arms, four_arms_clips, prefix, clips, specials):
    """Four Arms' attack records with this form's IDs and animations."""
    names = {key: CLIP_ROLES.get(clip[:64].split(b'\0')[0].decode('ascii'))
             for key, clip in four_arms_clips.items()}
    if prefix in LUNGE_SOURCES and crc(f'{prefix}_{LUNGE_CLIP}') in clips:
        for key, clip in four_arms_clips.items():
            if clip[:64].split(bytes(1))[0].decode('ascii').endswith('_travel_01'):
                names[key] = LUNGE_CLIP
    records, ids = bytearray(four_arms[:4]), {}
    for at in range(4, len(four_arms), 224):
        record = bytearray(four_arms[at:at + 224])
        key, = struct.unpack_from('>I', record)
        new_key = crc(f'{prefix}_attack_{key:08x}')
        ids[key] = new_key
        # Record words: 0 key, 2 attack set, 7-9 lead-in/main/recovery clips, 40 slot.
        struct.pack_into('>I', record, 0, new_key)
        struct.pack_into('>I', record, 8, crc('atk_' + prefix))
        slot, = struct.unpack_from('>I', record, 40 * 4)
        if slot in specials:
            # Words 36/37 are the start/stop events this ability's effect tree listens for.
            # Word 13 is Four Arms' forward travel during the move; these
            # specials are cast standing still.
            # Specials are cast standing still, except: energy outburst carries
            # Chromastone forward, as Four Arms' move in this slot does (travel
            # 2.0, his flags). Jetray steers during tri shot (R2 + triangle): flag
            # 0x80 turns him toward the stick (sub_8214A7C0, at the turn rate in
            # word 16) while word 13 moves him along that heading (sub_82148EF0).
            travel, steering = TRAVELLING_SPECIALS.get((prefix, slot), (0.0, False))
            if travel:
                struct.pack_into('>f', record, 13 * 4, travel)
                struct.pack_into('>I', record, 25 * 4, 0x00041eb4)
            elif not (prefix == 'chromastone' and slot == OUTBURST_SLOT):
                struct.pack_into('>f', record, 13 * 4, 0.0)
                struct.pack_into('>I', record, 25 * 4, 0x00041e3c)
            # Four Arms' lunge reach (19) is zeroed; his turn rate (16) is kept
            # only where the special steers.
            if not steering:
                struct.pack_into('>f', record, 16 * 4, 0.0)
            if prefix == 'chromastone' and slot == OUTBURST_SLOT:
                # The orbs' particles stay in world space, so a fast turn flings
                # them off the hands; turn slowly while it runs.
                struct.pack_into('>f', record, 16 * 4, 3.0)
            struct.pack_into('>f', record, 19 * 4, 0.0)
            for field, role in zip((7, 9), SPECIAL_EDGES.get(prefix, {}).get(slot, ())):
                struct.pack_into('>I', record, field * 4, crc(f'{prefix}_{role}'))
            struct.pack_into('>3I', record, 36 * 4, *effect_events(prefix, slot),
                             crc(SPECIAL_SOUNDS[prefix][slot][0]) if prefix in SPECIAL_SOUNDS_ENABLED else 0)
        for field in (7, 8, 9):
            clip, = struct.unpack_from('>I', record, field * 4)
            if not clip or clip in clips:
                continue
            role = specials[slot] if slot in specials and field == 8 else names.get(clip)
            if role is None:
                # Specials keep only their main animation.
                struct.pack_into('>I', record, field * 4, 0)
                continue
            target = crc(f'{prefix}_{role}')
            if target not in clips:
                raise ValueError('Missing animation ' + role)
            struct.pack_into('>I', record, field * 4, target)
        records += swap_sounds(bytes(record), prefix)
    return bytes(records), ids


def enabled_attacks(code):
    """Four Arms' always-on attacks and the strongest level of each special."""
    words, tokens = decode(code)
    calls = [words[at + 1] for at, kind in tokens if kind == 5 and words[at] >> 8 & 0xff == 14]
    if len(calls) != 29:
        raise ValueError('Unexpected Four Arms attack setup')
    return calls[:17] + [calls[17 + 3 * i + 2] for i in range(4)]


def person_record(four_arms, four_arms_clips, prefix, clips):
    """Four Arms' combat configuration with this form's hit reactions."""
    names = {key: clip[:64].split(b'\0')[0].decode('ascii') for key, clip in four_arms_clips.items()}
    record = bytearray(four_arms)
    for at in range(0, len(record), 4):
        clip, = struct.unpack_from('>I', record, at)
        if clip in names:
            role = REACTION_CLIPS.get(names[clip])
            target = crc(f'{prefix}_{role}') if role else 0
            if role and target not in clips:
                raise ValueError('Missing animation ' + role)
            struct.pack_into('>I', record, at, target)
    return swap_sounds(bytes(record), prefix)


def registration_rows(prefix, form_id, ordinal, character_key, donor, init, attacks, ids,
                      animation_set, person, costs):
    form = crc(prefix)
    rows = []
    # The R3 ring's picture and centre hologram are the owner's private art (COSMIC_RING_PICTURES names the folder
    # they were added to gtex_s.xbx from). Without them the form keeps Four Arms' stock ring pictures.
    own_pictures = prefix == 'cannonbolt' or bool(os.environ.get('COSMIC_RING_PICTURES'))
    arguments = {crc('fourarms'): form, 0x43149521: character_key,
                 FOUR_ARMS_INIT: crc(f'Cosmic_{prefix}_init'),
                 FOUR_ARMS_WHEEL_ICON: WHEEL_ICONS[prefix],
                 0x41400000: struct.unpack('>I', struct.pack('>f', ordinal))[0]}
    if own_pictures:
        arguments[FOUR_ARMS_RING_PICTURE] = (WHEEL_ICONS[prefix] if prefix == 'cannonbolt'
                                             else crc(f'Cosmic_{prefix}_ring'))
        arguments[HOLOGRAM_FUNCTION] = crc(f'Cosmic_{prefix}_hologram')
    register = replace_arguments(donor, arguments,
                                 [(b'g_fa\0', b'g_' + ALIENS[prefix].encode() + b'\0'),
                                  (b'atk_fa.ddf\0', b'atk_' + ALIENS[prefix].encode() + b'.ddf\0')])
    rows.append((crc(f'Cosmic_{prefix}_register'), 0, register))
    hologram_key = crc(f'Cosmic_{prefix}_holo')
    if prefix == 'cannonbolt':
        picture_dir = os.environ.get('COSMIC_RING_PICTURES')
        if not picture_dir or not (Path(picture_dir) / 'cannonbolt_holo.png').is_file():
            hologram_key = WHEEL_ICONS[prefix]
    # The ring's centre hologram: the form's own function returns its texture key (gtex_s.xbx).
    if own_pictures:
        rows.append((crc(f'Cosmic_{prefix}_hologram'), 0, struct.pack('>4I', 0x305,
                           hologram_key,
                           0x322, 0x21)))
    # Upgrade costs: Four Arms' block from the platform upgrade setup.
    rows.append((crc(f'Cosmic_{prefix}_costs'), 0, replace_arguments(costs, {crc('fourarms'): form})))
    rows.append((crc(f'Cosmic_{prefix}_init'), 0, replace_arguments(
        init, {crc('fourarms'): form, 0x43149521: character_key,
               FOUR_ARMS_ANIMATION_SET: animation_set, FOUR_ARMS_PERSON: person,
               FOUR_ARMS_SPECIAL_EFFECTS: effect_root(prefix),
               FOUR_ARMS_VOICE: crc(f'Cosmic_{prefix}_vo'),
               FOUR_ARMS_ATTACKS: crc(f'Cosmic_{prefix}_attacks')})))
    # The game reads this form's upgrade levels while transforming. The
    # launcher calls this after the original upgrade table is built, as the
    # Four Arms import does for its own ID; it also runs on registration.
    c = Code()
    c.get(0, UPGRADE_TABLE); c.false(0, 'end')
    c.num(1, form_id); c.index(2, 0, 1); c.false(2, 'create'); c.jump('end')
    c.label('create'); c.table(2); c.store(0, 1, 2)
    for field, count in ((0xfa7aeffb, 3), (0x4c6b3fe3, 4)):
        c.table(3); c.fieldput(2, field, 3); c.num(4, 0)
        for index in range(1, count + 1):
            c.num(5, index); c.store(3, 5, 4)
    c.label('end'); c.done()
    rows.append((crc(f'Cosmic_{prefix}_upgrades'), 0, c.finish()))
    c = Code()
    c.call(f'Cosmic_{prefix}_upgrades')
    c.get(13, 0x98197a65); c.get(10, 0x98197a65); c.field(4, 10, 0x098c5946)
    c.emit(1 << 24 | 13 << 16 | 4 << 8 | 0x20, 5)
    for attack in attacks:
        c.get(13, 0x98197a65); c.emit(14 << 8 | 5, ids[attack])
        c.get(10, 0x98197a65); c.field(4, 10, 0xf65d9a9d)
        c.emit(2 << 24 | 13 << 16 | 4 << 8 | 0x20, 5)
    c.done()
    rows.append((crc(f'Cosmic_{prefix}_attacks'), 0, c.finish()))
    rows.append((crc(f'Cosmic_{prefix}_vo'), 2, voice_resolver(prefix)))
    return rows


def prepare_bundle(vilgax, cosmic, installation, name):
    """Everything the launcher installs for one imported form."""
    package_data, report = prepare(vilgax, cosmic, name)
    form_id, ordinal = FORM_IDENTITIES[name]
    code = ALIENS[name]
    scripts = cosmic / 'global/scripts'
    va_chars = ddf_records((vilgax / 'global/scripts/char.ddf').read_bytes())
    va_player = ddf_records((vilgax / 'global/scripts/player.ddf').read_bytes())
    character_key = crc('character_' + name)
    va_header, va_character = va_chars[character_key]
    animation_set, = struct.unpack_from('>I', va_character, 380)
    set_header, set_record = va_player[animation_set]

    # This game's character record is 76 bytes longer. Start from Four Arms'
    # (other records carry stale memory in their unused middle block) and
    # replace the name, mesh, skeleton and animation set.
    our_header, four_arms_character = ddf_records(original(scripts / 'char.ddf'))[0x43149521]
    character = bytearray(four_arms_character)
    if any(character[132:432]):
        raise ValueError('Unexpected Four Arms character record')
    character[0:36] = va_character[0:36]
    character[36:40] = va_character[36:40]
    character[72:76] = va_character[72:76]
    struct.pack_into('>I', character, 452, animation_set)
    character_header = bytearray(our_header)
    struct.pack_into('>I', character_header, 0, character_key)
    player_header = bytearray(ddf_records(original(scripts / 'player.ddf'))[0x7b19673c][0])
    struct.pack_into('>I', player_header, 0, animation_set)

    clip_data = entries(entries((vilgax / 'global' / f'a_{code}.xbx').read_bytes())[13], True)
    clips = set(clip_data)
    if name in LUNGE_SOURCES and (cosmic / 'global' / LUNGE_SOURCES[name][0]).is_file():
        clips.add(crc(f'{name}_{LUNGE_CLIP}'))
    if name in GLIDERS | DOUBLE_JUMPERS:
        set_record = cd_animation_set(set_record, {key: data[:64].split(bytes(1))[0].decode('ascii') for key, data in clip_data.items()})
    bundle = installation / 'four-arms'
    four_arms_clips = table(entries((bundle / 'g_fa.xbx').read_bytes())[13])
    attacks, ids = attack_table((bundle / 'atk_fa.ddf').read_bytes(), four_arms_clips, name, clips,
                                SPECIAL_CLIPS[name])
    four_arms = {key: code for key, _, code in records((bundle / 'four-arms-registration.bin').read_bytes())}
    xbox_form = {key: code for key, _, code in records(original(scripts / 'gld_xbx.ds'))}[PLATFORM_FORM]
    donor = four_arms[PLATFORM_FORM][len(xbox_form) - 4:]
    xbox_upgrades = {key: code for key, _, code in records(original(scripts / 'gld_xbx.ds'))}[PLATFORM_UPGRADES]
    costs = four_arms[PLATFORM_UPGRADES][len(xbox_upgrades) - 4:]
    person_key = crc(f'{name}_person')
    person_header, four_arms_person = ddf_records(original(scripts / 'xbx.ddf'))[FOUR_ARMS_PERSON]
    person_header = bytearray(person_header)
    struct.pack_into('>I', person_header, 0, person_key)
    person = person_record(four_arms_person, four_arms_clips, name, clips)
    if name in GLIDERS | DOUBLE_JUMPERS:
        glider = ddf_records(original(scripts / 'xbx.ddf'))[BIG_CHILL_PERSON][1]
        person = bytearray(person)
        for offset in (GLIDE_FIELDS if name in GLIDERS else (0x44,)):
            person[offset:offset + 4] = glider[offset:offset + 4]
        person = bytes(person)
    rows = registration_rows(name, form_id, ordinal, character_key, donor, four_arms[FOUR_ARMS_INIT],
                             enabled_attacks(four_arms[FOUR_ARMS_ATTACKS]), ids, animation_set, person_key, costs)
    files = {
        f'g_{code}.xbx': package_data,
        f'atk_{code}.ddf': attacks,
        'character-records.bin': bytes(character_header) + bytes(character),
        'player-records.bin': bytes(player_header) + set_record,
        'xbx-records.bin': bytes(person_header) + person,
        'forms.bin': encode(rows),
        'form-ids.txt': f'{name} {form_id}\n'.encode('ascii'),
        # Name callout sample and its sounds.ddf descriptor name.
        'callout.fsb': callout_bank(vilgax, original(cosmic / 'l_chin/vo/vo_eng.xbx'), name),
        'callout.txt': f'{name}_name_callout_01\n'.encode('ascii'),
        # Albedo recolors this body texture (eyes and Omnitrix badge go red).
        'albedo.txt': f'g_{code}.xbx {report["textures"][0]}\n'.encode('ascii'),
        # sounds.ddf entries for the special-attack sounds in the package's project.
        **({'sounds.txt': report.pop('sounds').encode('ascii')} if name in SPECIAL_SOUNDS_ENABLED else {}),
    }
    report.update(form_id=form_id, attacks=len(ids), animation_set=f'{animation_set:08x}')
    return files, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('vilgax', type=Path, help='Extracted Vilgax Attacks Xbox 360 folder')
    parser.add_argument('installation', type=Path, help='Cosmic Recomp installation folder with Four Arms imported')
    parser.add_argument('alien', choices=sorted(FORM_IDENTITIES))
    parser.add_argument('output', type=Path, help='New bundle folder')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a new output folder')
    files, report = prepare_bundle(args.vilgax, args.installation / 'game', args.installation, args.alien)
    args.output.mkdir(parents=True)
    for file, data in files.items():
        (args.output / file).write_bytes(data)
    print(report)
