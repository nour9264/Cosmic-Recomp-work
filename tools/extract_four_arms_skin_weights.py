"""Extract Xbox-packed bone weights in mesh order from the verified PS3 donor."""

import argparse
from hashlib import sha256
from math import sqrt
from pathlib import Path
import struct

from convert_four_arms_meshes import mesh_buffers
from extract_discord_level_images import table
from merge_alien_streams import entries


def packed_influences(data):
    if len(data) == 4:
        bones = (struct.unpack('>I', data)[0],)
        weights = (1.0,)
    elif len(data) == 12:
        weights = struct.unpack_from('>2f', data)
        bones = struct.unpack_from('>2H', data, 8)
    elif len(data) == 20:
        weights = struct.unpack_from('>4f', data)
        bones = data[16:20]
    else:
        raise ValueError('Unsupported influence record')
    if not all(0 <= weight <= 1 for weight in weights):
        raise ValueError('Invalid skin weight')
    return bytes(int(weight * 255) for weight in weights).ljust(4, b'\0') + (
        bytes(bones).ljust(4, b'\0'))


def weights_in_mesh_order(skin, vertices, groups):
    vertex_count, duplicate_count = struct.unpack_from('>2I', skin, 72)
    if vertex_count != duplicate_count or len(vertices) != vertex_count * 44:
        raise ValueError('Skin and mesh vertex counts disagree')
    keys = [vertices[i:i + 24] for i in range(0, len(vertices), 44)]
    expected = set(keys)
    weights = {}
    occurrences = 0
    for begin, end, stride in groups:
        cursor = begin
        while cursor + stride <= end:
            key = skin[cursor:cursor + 24]
            if key not in expected:
                if skin[cursor:cursor + 4] != bytes(4):
                    raise ValueError('Unrecognized PS3 skin data')
                cursor += 4
                continue
            packed = packed_influences(skin[cursor + 24:cursor + stride])
            if weights.setdefault(key, packed) != packed:
                raise ValueError('Conflicting weights for the same position and normal')
            occurrences += 1
            cursor += stride
        if any(skin[cursor:end]):
            raise ValueError('Unexpected bytes at end of skin group')
    if occurrences != vertex_count or weights.keys() != expected:
        raise ValueError('PS3 skin records do not cover the mesh')
    return b''.join(weights[key] for key in keys)


def dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def cross(left, right):
    x, y, z = left
    a, b, c = right
    return (y * c - z * b, z * a - x * c, x * b - y * a)


def skinned_vertex_payload(vertices, indices, weights):
    """Build experimental section 22 rows, without the archive header."""
    rows = list(struct.iter_unpack('>11f', vertices))
    if len(weights) != 8 * len(rows):
        raise ValueError('Expected one influence record per vertex')
    tangents = [[0.0, 0.0, 0.0] for _ in rows]
    bitangents = [[0.0, 0.0, 0.0] for _ in rows]
    for triangle in struct.iter_unpack('>3H', indices):
        origin, first, second = (rows[index] for index in triangle)
        edge_a = [first[i] - origin[i] for i in range(3)]
        edge_b = [second[i] - origin[i] for i in range(3)]
        u_a, v_a = first[9] - origin[9], first[10] - origin[10]
        u_b, v_b = second[9] - origin[9], second[10] - origin[10]
        determinant = u_a * v_b - u_b * v_a
        if abs(determinant) < 1e-12:
            continue
        for index in triangle:
            for axis in range(3):
                tangents[index][axis] += (edge_a[axis] * v_b - edge_b[axis] * v_a) / determinant
                bitangents[index][axis] += (edge_b[axis] * u_a - edge_a[axis] * u_b) / determinant
    payload = bytearray()
    for index, row in enumerate(rows):
        normal = row[3:6]
        tangent = tangents[index]
        projection = dot(tangent, normal)
        tangent = tuple(a - projection * b for a, b in zip(tangent, normal))
        length = sqrt(dot(tangent, tangent))
        if length < 1e-10:
            axis = min(range(3), key=lambda i: abs(normal[i]))
            tangent = cross(tuple(float(i == axis) for i in range(3)), normal)
            length = sqrt(dot(tangent, tangent))
        if length < 1e-10:
            raise ValueError('Missing normal for skinned vertex')
        if dot(cross(normal, tangent), bitangents[index]) < 0:
            length = -length
        start = index * 44
        payload.extend(vertices[start:start + 24])
        payload.extend(struct.pack('>3f', *(a / length for a in tangent)))
        payload.extend(vertices[start + 36:start + 44])
        payload.extend(weights[index * 8:index * 8 + 8])
    return bytes(payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('donor', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--vertex-payload', action='store_true',
                        help='Emit experimental skinned vertices instead of weights alone')
    args = parser.parse_args()
    donor = args.donor.read_bytes()
    if sha256(donor).hexdigest() != 'b36b1077cded79f3d59f150f100d69a351d1ba2dc1cb20fb6c217fac86285dda':
        parser.error('Expected the verified BLES01110 Four Arms archive')
    sections = entries(donor)
    key = 0x63147ce1
    skin = table(sections[22])[key]
    _, vertices, indices = mesh_buffers(table(sections[4])[key])
    weights = weights_in_mesh_order(
        skin, vertices, ((96, 69152, 28), (69152, len(skin), 36)))
    output = skinned_vertex_payload(vertices, indices, weights) if args.vertex_payload else weights
    args.output.write_bytes(output)
