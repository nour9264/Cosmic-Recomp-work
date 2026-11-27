"""Give the four Alien Force aliens and the five Ultimates (Ultimate Cannonbolt shares Cannonbolt's) an interact animation:
three clips per form baked from interact_scene.py's export (Blender review scene), plus the three animation-set entries the
engine plays them through (roles 0x4a, 0x48 and 0x05, as in every original alien's set).

By default (--single-action interact_01, the layout approved in game) the whole sequence of about 1.4 s is the one clip the
engine plays on role 0x48, and the other two clips are two-key stubs of the idle pose: the engine requests the three roles in
fixed order (5, 0x48, 0x49, 0x4a) with timings of its own, so splitting the motion over three clips did not play as designed.

    python tools/interact/install_interact_clips.py --installation <installation> --poses <interact_poses.json>

Changes (first original of each file is kept once in <installation>/../interact-backup):
  vilgax/<form>/g_*.xbx and game/global/g_*.xbx   new clips + channels (the launcher merges them into the level banks)
  vilgax/<form>/player-records.bin                the form's animation set with the interact entries
  vilgax/ultimatecannonbolt/player-records.bin    the five Ultimates' animation sets (the launcher replaces records by key)
Roles: in this game's sets role 5 is interact-out and 0x49 the second idle; Vilgax Attacks' idle uses 5, so it moves to 0x49.
"""
import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_vilgax_import as m
from merge_alien_streams import entries, channel_records, streamed_clip, animation_time_range

SEQUENCE = ('interact_in_01', 'interact_01', 'interact_out_01')
# Every original alien's three interact clips share one timeline: in from 0, the loop from tick 1440-1600 to about 4800, out from
# about 4960 (keys 160 ticks apart). Water Hazard's, whose timing these clips copy, is 0 / 1440 / 4960. A clip that starts at 0
# instead gets sampled at the wrong times (the loop's first frames skipped, the out clip already at its last pose).
START = {'interact_in_01': 0, 'interact_01': 9, 'interact_out_01': 31}   # in keys of 160 ticks
ROLES = {'interact_in_01': 0x4a, 'interact_01': 0x48, 'interact_out_01': 0x05}
IDLE_ROLE, IDLE2_ROLE, SPARE_ROLE = 1, 0x49, 0xfe
# form -> (code, package folders relative to the installation, where the animation set is)
FORMS = {
    'Chromastone': ('cs', ['vilgax/chromastone', 'game/global'], ('own', 'vilgax/chromastone')),
    'Jetray': ('jr', ['vilgax/jetray', 'game/global'], ('own', 'vilgax/jetray')),
    'Goop': ('gp', ['vilgax/goop', 'game/global'], ('own', 'vilgax/goop')),
    'Cannonbolt': ('cb', ['vilgax/cannonbolt', 'game/global'], ('own', 'vilgax/cannonbolt')),
    'Ultimate Humungousaur': ('uhm', ['game/global'], ('stock', 0x5fec59a3)),
    'Ultimate Big Chill': ('ubc', ['game/global'], ('stock', 0x21281472)),
    'Ultimate Swampfire': ('usf', ['game/global'], ('stock', 0x00d9521e)),
    'Ultimate Echo Echo': ('uec', ['game/global'], ('stock', 0x405bfa5d)),
    'Ultimate Spider Monkey': ('usm', ['game/global'], ('stock', 0x0ecf82ef)),
}
SET_HOLDER = 'vilgax/ultimatecannonbolt/player-records.bin'


def vec_channel(values, kind=1, start=0):
    return struct.pack('>BBHHH', kind, 4, 0x5001 if kind == 1 else 0x5003, len(values), len(values)) + \
        b''.join(struct.pack('>4f', (start + i) * 160, *v) for i, v in enumerate(values))


def quat_channel(values, start=0):
    out = bytearray(struct.pack('>BBHHH', 16, 2, 0x5002, len(values), len(values)))
    prev = None
    for i, q in enumerate(values):
        length = sum(v * v for v in q) ** .5
        q = [v / length for v in q]               # w, x, y, z
        if prev is not None and sum(a * b for a, b in zip(q, prev)) < 0:
            q = [-v for v in q]
        prev = q
        w, x, y, z = q
        out.extend(struct.pack('>3hbB', *(max(-32767, min(32767, round(v * 32767))) for v in (x, y, z)),
                               max(-127, min(127, round(w * 127))), start + i))
    return bytes(out)


def static(values, tolerance=1e-5):
    return all(abs(a - b) <= tolerance for row in values for a, b in zip(row, values[0]))


def payload_order(raw):
    buckets, n, bucket_at, record_at, stride = struct.unpack_from('>5I', raw, 32)
    rows = [struct.unpack_from('>3I', raw, 32 + record_at + i * stride) for i in range(n)]
    return [key for key, _, offset in sorted(rows, key=lambda row: row[2])]


def add_clips(raw, code, tags, clips):
    """The package with the form's interact clips added (or replaced); returns (bytes, {role name: clip key})."""
    parts = entries(raw)
    oldrows, oldclips = m.vaps_rows(parts[9]), m.vaps_rows(parts[13])
    names = {c: f'cosmic_{c}_{code}' for c in SEQUENCE}
    keys = {c: m.crc(names[c]) for c in SEQUENCE}
    # Replace an earlier install instead of stacking: drop its clips and the channels they own.
    mine = {m.crc(f'{names[c]}_{t}_{j}') for c in SEQUENCE for t in tags for j in range(3)}
    drop = [i for i, row in enumerate(oldrows) if row[0] in mine]
    kept_clips = [row for row in oldclips if row[0] not in keys.values()]
    for row in kept_clips:
        refs = [struct.unpack_from('>I', row[2], at)[0] for at in [80] + list(range(216, len(row[2]), 4))]
        assert not set(refs) & set(drop), 'a kept clip uses a channel of this install'
    keep = [i for i in range(len(oldrows)) if i not in set(drop)]
    shift = {old: new for new, old in enumerate(keep)}
    rows = [oldrows[i] for i in keep]
    kept_channels = [row[2] for row in rows]
    base_clips = []
    for key, flags, c in kept_clips:
        c = bytearray(c)
        for at in [80] + list(range(216, len(c), 4)):
            index = struct.unpack_from('>I', c, at)[0]
            if index != 0xffffffff:
                struct.pack_into('>I', c, at, shift[index])
        base_clips.append((key, flags, bytes(c)))
    idle = next(c for k, f, c in base_clips if c.startswith(b'idle_01\0'))
    ids = m.bone_ids(idle)
    assert ids == tags, (code, 'skeleton bones differ from the idle clip')
    new_clips = []
    for clip_name in SEQUENCE:
        frames = clips[clip_name]['frames']
        clip = bytearray(idle)
        encoded = names[clip_name].encode()
        clip[:64] = encoded + b'\0' * (64 - len(encoded))
        start = START[clip_name]
        struct.pack_into('>2f', clip, 64, start * 160, (start + len(frames) - 1) * 160)
        struct.pack_into('>I', clip, 80, 0xffffffff)
        for i, tag in enumerate(tags):
            pos = [f[i][0:3] for f in frames]
            rot = [(f[i][3], -f[i][4], -f[i][5], -f[i][6]) for f in frames]   # stored rotation is the conjugate
            scale = [f[i][7:10] for f in frames]
            if code == 'cb' and tag == 193:
                scale = [(0.0, 0.0, 0.0)] * len(frames)                         # the ball stays hidden
            # A bone that does not move keeps a single key (as the game's own clips do), so the package stays about the
            # size it was; the first bone's rotation always keeps every key, which fixes the clip's length.
            still = [static(pos), static(rot), static(scale)]
            if i == 0:
                still[1] = False
            channels = (vec_channel(pos[:1] if still[0] else pos, 1, start), quat_channel(rot[:1] if still[1] else rot, start),
                        vec_channel(scale[:1] if still[2] else scale, 12, start))
            for j, blob in enumerate(channels):
                struct.pack_into('>I', clip, 216 + i * 12 + j * 4, len(rows))
                rows.append((m.crc(f'{names[clip_name]}_{tag}_{j}'), 0, blob))
        new_clips.append((keys[clip_name], 0, bytes(clip)))
    buckets = max(1, len(rows) // 4)
    order = sorted(range(len(rows)), key=lambda i: (rows[i][0] % buckets, rows[i][0], i))
    remap = {old: new for new, old in enumerate(order)}
    updated = []
    for key, flags, c in base_clips + new_clips:
        c = bytearray(c)
        for at in [80] + list(range(216, len(c), 4)):
            index = struct.unpack_from('>I', c, at)[0]
            if index != 0xffffffff:
                struct.pack_into('>I', c, at, remap[index])
        updated.append((key, flags, bytes(c)))
    parts[9] = m.build_vaps(9, struct.unpack_from('>H', parts[9], 12)[0], [rows[i] for i in order])
    parts[13] = m.build_vaps(13, struct.unpack_from('>H', parts[13], 12)[0], m.bucket_sorted(updated))
    result = m.package(raw, parts, payload_order(raw))
    check = entries(result)
    new_channels = channel_records(check[9])
    new_table = {}
    for key, flags, c in m.vaps_rows(check[13]):   # a package can hold duplicate clip keys (Ultimate Swampfire)
        new_table.setdefault(key, []).append(c)
    seen = {}
    for key, flags, c in base_clips:
        n = seen[key] = seen.get(key, -1) + 1
        assert streamed_clip(new_table[key][n], new_channels) == streamed_clip(c, kept_channels), 'an original clip changed'
    for clip_name in SEQUENCE:
        got = animation_time_range(new_table[keys[clip_name]][0], new_channels)
        assert got == (START[clip_name] * 160, (START[clip_name] + len(clips[clip_name]['frames']) - 1) * 160), got
    for sid, blob in entries(raw).items():
        if sid not in (9, 13):
            assert check[sid] == blob
    return result, keys


def patch_set(record, idle_key, keys):
    """Animation set with the interact entries added and the idle moved off role 5."""
    words = list(struct.unpack(f'>{len(record) // 4}I', record))
    count = words[0]
    assert all(w == 0 for w in words[2 + 7 * count:]), 'unexpected data after the set entries'
    clip_keys = set(keys.values())
    # Drop an earlier install's entries.
    entries_ = [words[2 + 7 * e:9 + 7 * e] for e in range(count)]
    entries_ = [e for e in entries_ if e[0] not in clip_keys]
    taken = {ROLES[c] for c in SEQUENCE}
    for e in entries_:
        role = e[6] >> 24
        if role == 5 and e[0] == idle_key:
            e[6] = IDLE2_ROLE << 24 | e[6] & 0xffffff
        elif role in taken or (role == IDLE2_ROLE and e[0] != idle_key):
            e[6] = SPARE_ROLE << 24 | e[6] & 0xffffff
    for c in SEQUENCE:
        entries_.append([keys[c], 0, 0, 0x3f800000, 0x40a00000, 0, ROLES[c] << 24])
    assert 2 + 7 * len(entries_) <= len(words)
    flat = [w for e in entries_ for w in e]
    words[0] = len(entries_)
    words[2:2 + len(flat)] = flat
    for i in range(2 + len(flat), len(words)):
        words[i] = 0
    return struct.pack(f'>{len(words)}I', *words)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--poses', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true', help='build and check everything, write nothing')
    parser.add_argument('--single-action', choices=SEQUENCE + ('none',), default='interact_01', metavar='CLIP',
                        help='play the whole sequence as this one clip (interact_in_01 / interact_01 / interact_out_01); '
                             'the other two become idle-pose stubs. "none" keeps the three separate clips. Default: interact_01')
    parser.add_argument('--leave-out', nargs='*', default=[], metavar='FORM',
                        help="forms (e.g. 'Ultimate Humungousaur') put back to the game's own package and set; stock forms only")
    args = parser.parse_args()
    root = args.installation.resolve()
    backup = root.parent / 'interact-backup'
    poses = json.loads(args.poses.read_text())

    def keep(path):
        target = backup / path.relative_to(root)
        if not args.dry_run and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    player = m.ddf_records(m.original(root / 'game/global/scripts/player.ddf'))
    holder = []
    for form, (code, folders, where) in FORMS.items():
        data = poses[form]
        tags = data['tags']
        packages = [root / folder / f'g_{code}.xbx' for folder in folders]
        for path in packages:
            if not path.is_file():
                raise SystemExit(f'Missing {path}')
        if form in args.leave_out:
            # Back to the game's own package and animation set (to tell this install's changes from the game's).
            for path in packages:
                original_copy = backup / path.relative_to(root)
                if original_copy.is_file() and not args.dry_run:
                    path.write_bytes(original_copy.read_bytes())
            if where[0] == 'stock':
                holder.append(b''.join(player[where[1]]))
            print(f'{form}: left out, original package and set')
            continue
        raw = packages[0].read_bytes()
        if len(packages) == 2 and packages[1].read_bytes() != raw:
            raise SystemExit(f'{packages[0]} and {packages[1]} differ; not touching them')
        clips = data['clips']
        if args.single_action != 'none':
            # One animation only: the whole sequence plays as the "in" clip; the loop and out clips are two keys of the idle pose.
            frames = [clips[c]['frames'] for c in SEQUENCE]
            rest = frames[0][0]
            whole = {'frames': frames[0] + frames[1][1:] + frames[2][1:]}
            stub = {'frames': [rest, rest]}
            clips = {name: whole if name == args.single_action else stub for name in SEQUENCE}
        result, keys = add_clips(raw, code, tags, clips)
        for path in packages:
            keep(path)
            if not args.dry_run:
                path.write_bytes(result)
        idle_key = next(k for k, f, c in m.vaps_rows(entries(result)[13]) if c.startswith(b'idle_01\0'))
        if where[0] == 'own':
            records = root / where[1] / 'player-records.bin'
            keep(records)
            blob = records.read_bytes()
            header, record = blob[:24], blob[24:]
            assert struct.unpack_from('>I', header, 20)[0] == len(record) == 1964
            patched = header + patch_set(record, idle_key, keys)
            if not args.dry_run:
                records.write_bytes(patched)
        else:
            header, record = player[where[1]]
            holder.append(header + patch_set(record, idle_key, keys))
        print(f'{form}: clips {[f"{k:08x}" for k in keys.values()]} set patched')
    path = root / SET_HOLDER
    keep(path)
    if not args.dry_run:
        path.write_bytes(b''.join(holder))
    print(f"{'Checked' if args.dry_run else 'Installed'} interact clips for {len(FORMS)} forms; Ultimate sets in {SET_HOLDER}.")


if __name__ == '__main__':
    main()

