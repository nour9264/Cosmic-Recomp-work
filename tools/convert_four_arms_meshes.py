"""Convert section 4 mesh records for private Four Arms testing."""

import argparse
from pathlib import Path
import struct

from convert_four_arms_textures import rebuild_bank
from extract_discord_level_images import table
from merge_alien_streams import entries


def mesh_buffers(record, xbox=False):
    shift = 4 if xbox else 0
    layout, vertex_count = struct.unpack_from('>II', record)
    index_count, = struct.unpack_from('>I', record, 12 + shift)
    addresses = [struct.unpack_from('<I', record, at + shift)[0]
                 for at in (8, 16, 24)]
    vertex_at, index_at = (address - addresses[2] + 372 + shift
                           for address in addresses[:2])
    stride = {9: 20, 11: 44}[layout & 15]
    vertex_end = vertex_at + vertex_count * stride
    if not 392 + shift <= vertex_at <= vertex_end <= index_at or (
            index_at + 2 * index_count != len(record)):
        raise ValueError('Invalid mesh buffer offsets')
    indices = struct.unpack_from(f'>{index_count}H', record, index_at)
    if max(indices) >= vertex_count or any(record[vertex_end:index_at]):
        raise ValueError('Invalid mesh indices or alignment')
    return vertex_at, record[vertex_at:vertex_end], record[index_at:]


def convert_mesh(record, xbox_reference):
    vertex_at, vertices, indices = mesh_buffers(record)
    layout, vertex_count = struct.unpack_from('>II', record)
    index_count, = struct.unpack_from('>I', record, 12)
    # The loader uses differences from the metadata pointer. Reuse the
    # address origin from a native record and rebuild both buffer pointers.
    metadata_address, = struct.unpack_from('<I', xbox_reference, 28)
    metadata = bytearray(record[36:392])
    cursor = 392
    while cursor < vertex_at:
        kind, = struct.unpack_from('>I', record, cursor)
        if kind == 0:
            break
        size = {1: 16, 2: 20, 5: 16, 9: 16, 10: 16}[kind]
        if cursor + size > vertex_at:
            raise ValueError('Truncated mesh command')
        command = bytearray(record[cursor:cursor + size])
        if kind != 2:
            if command[4:8] != b'\0\0\0\1':
                raise ValueError('Unexpected PS3 mesh command flag')
            command[4:8] = bytes(4)
        metadata.extend(command)
        cursor += size
    if any(record[cursor:vertex_at]):
        raise ValueError('Unexpected bytes after mesh commands')

    xbox_vertex_at = (40 + len(metadata) + 31) & ~31
    xbox_index_at = (xbox_vertex_at + len(vertices) + 31) & ~31
    header = bytearray(struct.pack('>III', layout | 16, vertex_count, 1))
    header.extend(struct.pack('<I', metadata_address + xbox_vertex_at - 376))
    header.extend(struct.pack('>I', index_count))
    header.extend(struct.pack('<I', metadata_address + xbox_index_at - 376))
    header.extend(record[20:24])
    header.extend(struct.pack('<I', metadata_address))
    header.extend(record[28:36])
    result = bytes(header + metadata)
    result += bytes(xbox_vertex_at - len(result)) + vertices
    result += bytes(xbox_index_at - len(result)) + indices
    if mesh_buffers(result, xbox=True)[1:] != (vertices, indices):
        raise ValueError('Converted mesh buffers failed round-trip validation')
    return result


def convert_mesh_bank(section, xbox_reference):
    return rebuild_bank(
        section, lambda record: convert_mesh(record, xbox_reference),
        lambda record: mesh_buffers(record, xbox=True)[0] // 32)


def convert_vertex_colors(record, xbox_mesh, xbox_descriptor):
    """Convert section 3 colors using the caller's verified Xbox descriptor."""
    if len(record) < 32 or len(record) % 4 or len(xbox_descriptor) != 4:
        raise ValueError('Invalid vertex color record')
    flags, = struct.unpack_from('>I', record)
    vertex_count, = struct.unpack_from('>I', xbox_mesh, 4)
    if flags not in (0, 0x10000) or len(record) != 32 + (4 * vertex_count if flags else 0):
        raise ValueError('Vertex color record does not match its mesh')
    if any(record[20:24]):
        raise ValueError('Expected an unset PS3 color pointer')
    metadata_address, = struct.unpack_from('<I', xbox_mesh, 28)
    color_address = metadata_address - 344 if flags else 0
    result = bytearray(record)
    result[12:16] = xbox_descriptor
    struct.pack_into('<I', result, 20, color_address)
    for offset in range(32, len(record), 4):
        r, g, b, a = record[offset:offset + 4]
        result[offset:offset + 4] = bytes((a, r, g, b))
    return bytes(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('donor', type=Path)
    parser.add_argument('xbox_reference', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = entries(args.donor.read_bytes())[4]
    reference = next(iter(table(entries(args.xbox_reference.read_bytes())[4]).values()))
    args.output.write_bytes(convert_mesh_bank(source, reference))
