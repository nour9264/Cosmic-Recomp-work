"""Stage an offline Four Arms archive with the verified mesh and texture conversions."""

import argparse
from hashlib import sha256
from pathlib import Path
import struct

from convert_four_arms_meshes import convert_mesh_bank, mesh_buffers
from convert_four_arms_textures import convert_bank, rebuild_bank
from extract_discord_level_images import table
from extract_four_arms_skin_weights import skinned_vertex_payload, weights_in_mesh_order
from merge_alien_streams import entries


FOUR_ARMS_DONOR_SHA256 = 'b36b1077cded79f3d59f150f100d69a351d1ba2dc1cb20fb6c217fac86285dda'
FOUR_ARMS_ATTACK_SHA256 = '1932dad3303106e48a18e8ef684b6ce2c32625a6dd2d9153b4da1266685f02a9'
PS3_PLATFORM_SCRIPT_SHA256 = 'd6b78cbc16540f234316d6afe9ae06dcb24bf7a8e5717c4db619c83ee3d4171c'


def ps3_title_id(sfo):
    if len(sfo) < 20 or sfo[:4] != b'\0PSF':
        raise ValueError('Invalid PARAM.SFO')
    key_base, data_base, count = struct.unpack_from('<III', sfo, 8)
    if not 20 + count * 16 <= key_base <= data_base <= len(sfo):
        raise ValueError('Invalid PARAM.SFO directory')
    for index in range(count):
        key, _, size, _, offset = struct.unpack_from('<HHIII', sfo, 20 + index * 16)
        key_at = key_base + key
        data_at = data_base + offset
        if key_at >= data_base or data_at + size > len(sfo):
            raise ValueError('Invalid PARAM.SFO entry')
        if sfo[key_at:sfo.index(0, key_at, data_base)] == b'TITLE_ID':
            return sfo[data_at:data_at + size].rstrip(b'\0').decode('ascii')
    raise ValueError('PARAM.SFO has no TITLE_ID')


def read_ps3_donor(folder):
    title = ps3_title_id((folder / 'PARAM.SFO').read_bytes())
    if title != 'BLES01110':
        raise ValueError(f'Unsupported PS3 title {title}. Expected European BLES01110.')
    data = folder / 'USRDIR/global'
    files = {
        'g_fa.ps3': FOUR_ARMS_DONOR_SHA256,
        'scripts/atk_fa.ddf': FOUR_ARMS_ATTACK_SHA256,
        'scripts/gld_ps3.ds.sdat': PS3_PLATFORM_SCRIPT_SHA256,
    }
    verified = {}
    for name, expected in files.items():
        contents = (data / name).read_bytes()
        if sha256(contents).hexdigest() != expected:
            raise ValueError(f'Unsupported or unreadable PS3 donor file: {name}')
        verified[name] = contents
    return verified


def replace_sections(archive, replacements):
    sections = entries(archive)
    if not replacements.keys() <= sections.keys():
        raise ValueError('Unknown archive section')
    alignment = 1 << struct.unpack_from('>H', archive, 12)[0]
    base = struct.unpack_from('>I', archive, 28)[0]
    directory = 32 + struct.unpack_from('>I', archive, 44)[0]
    result = bytearray(archive[:base])
    rows = [(directory + i * 12, *struct.unpack_from('>III', archive, directory + i * 12))
            for i in range(len(sections))]
    for row, key, _, _ in sorted(rows, key=lambda item: item[3]):
        result.extend(bytes((-len(result)) % alignment))
        section = replacements.get(key, sections[key])
        struct.pack_into('>II', result, row + 4, len(section), len(result) - base)
        result.extend(section)
    result.extend(bytes((-len(result)) % alignment))
    struct.pack_into('>I', result, 16, len(result) - base)
    if entries(result) != (sections | replacements):
        raise ValueError('Archive failed round-trip validation')
    return bytes(result)


def xbox_skin_record(source, reference, payload):
    count, repeated_count = struct.unpack_from('>II', source, 72)
    if count != repeated_count or len(payload) != count * 52:
        raise ValueError('Invalid Xbox skin vertex payload')
    reference_count, reference_repeated = struct.unpack_from('>II', reference, 72)
    if (reference_count != reference_repeated or len(reference) != 80 + reference_count * 52
            or reference[68:70] != b'\x07\x01'):
        raise ValueError('Unexpected Xbox skin header')
    return source[:64] + reference[64:72] + source[72:80] + payload


def convert_skin_bank(source, mesh, reference):
    key = 0x63147ce1
    skin = table(source)
    if set(skin) != {key}:
        raise ValueError('Unexpected Four Arms skin bank')
    _, vertices, indices = mesh_buffers(table(mesh)[key])
    record = skin[key]
    weights = weights_in_mesh_order(
        record, vertices, ((96, 69152, 28), (69152, len(record), 36)))
    payload = skinned_vertex_payload(vertices, indices, weights)
    template = next(iter(table(reference).values()))
    return rebuild_bank(source, lambda data: xbox_skin_record(data, template, payload))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('donor', type=Path, help='Extracted PS3_GAME folder or verified g_fa.ps3')
    parser.add_argument('xbox_reference', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        donor = (read_ps3_donor(args.donor)['g_fa.ps3'] if args.donor.is_dir()
                 else args.donor.read_bytes())
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if sha256(donor).hexdigest() != FOUR_ARMS_DONOR_SHA256:
        parser.error('Expected the verified BLES01110 Four Arms archive')
    if args.output.suffix != '.bin':
        parser.error('The incomplete offline archive must use a .bin extension')
    native = entries(args.xbox_reference.read_bytes())
    reference = next(iter(table(native[4]).values()))
    sections = entries(donor)
    replacements = {0: convert_bank(sections[0]), 4: convert_mesh_bank(sections[4], reference),
                    22: convert_skin_bank(sections[22], sections[4], native[22])}
    args.output.write_bytes(replace_sections(donor, replacements))
