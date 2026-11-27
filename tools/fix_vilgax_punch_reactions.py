"""Restore stock light-hit reactions for the installed Vilgax Attacks punches."""
import datetime
import struct
from pathlib import Path

from merge_alien_streams import entries
from prepare_vilgax_import import table

ROOT = None  # the installation folder, set by main()
ATTACK_WORDS = struct.Struct(">56I")
LIGHT_HIT_SLOT = 0x47C02D3B
KNOCKDOWN = 0xACA8A0D1


def patch_attacks(blob, clips):
    if (len(blob) - 4) % ATTACK_WORDS.size:
        raise ValueError("Invalid attack table size")
    output = bytearray(blob)
    changed = 0
    for offset in range(4, len(blob), ATTACK_WORDS.size):
        row = list(ATTACK_WORDS.unpack_from(blob, offset))
        clip = clips.get(row[8], b"")[:64].split(bytes(1))[0]
        if row[40] != LIGHT_HIT_SLOT or clip not in (b"punch_01", b"punch_02", b"punch_03", b"punch_04"):
            continue
        count = row[45]
        if count > 5:
            raise ValueError("Invalid hit modifier count")
        # Water Hazard and Big Chill use zero override and no secondary
        # modifiers on their ordinary punches. This uses the normal damage,
        # target impact-effect and death-reaction code for each landed hit.
        if row[23] or count:
            row[23] = 0
            row[45:] = [0] * 11
            ATTACK_WORDS.pack_into(output, offset, *row)
            changed += 1
    return bytes(output), changed


def main():
    import argparse
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installation", type=Path)
    parser.add_argument("--backup", type=Path, required=True, help="folder that receives the original attack tables")
    args = parser.parse_args()
    ROOT = args.installation
    revisions = []
    for alien, code in (("chromastone", "cs"), ("goop", "gp"), ("jetray", "jr")):
        bundle = ROOT / "vilgax" / alien
        package = entries((bundle / f"g_{code}.xbx").read_bytes())
        clips = table(package[13])
        original_path = bundle / f"atk_{code}.ddf"
        active_path = ROOT / "game/global/scripts" / original_path.name
        original = original_path.read_bytes()
        if active_path.read_bytes() != original:
            raise ValueError(f"Live attack table differs from {alien} bundle")
        revised, changed = patch_attacks(original, clips)
        if changed != 16:
            raise ValueError(f"Unexpected punch count for {alien}: {changed}")
        for path in (original_path, active_path):
            revisions.append((path, original, revised))
    backup = args.backup / datetime.datetime.now().strftime("vilgax-punch-backup-%Y%m%d-%H%M%S")
    for path, original, _ in revisions:
        destination = backup / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(original)
    for path, _, revised in revisions:
        staged = path.with_suffix(".ddf.punch-new")
        staged.write_bytes(revised)
        staged.replace(path)
        if path.read_bytes() != revised:
            raise IOError(f"Could not verify {path}")
    print("Installed 16 punch reactions per alien for Chromastone, Goop and Jetray.")


if __name__ == "__main__":
    main()
