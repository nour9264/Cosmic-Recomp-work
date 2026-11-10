"""Extract English story subtitles from a local Xbox 360 text table."""
import argparse
import re
import struct
from decimal import Decimal
from pathlib import Path

# Original mission records (missions.ddf), plus the movie calls in
# l_pari.ds and l_tokd.ds. Paris C/D share a four-group mission record.
MOVIE_KEYS = {
    "l_chin/chin_a": (0x4E9EBE5E,), "l_chin/chin_b": (0xF727437F,),
    "l_mili/mili_a": (0x3CE60AD0, 0xA5EF5B6A),
    "l_mili/mili_b": (0x855FF7F1, 0x1C56A64B),
    "l_pari/pari_a": (0x59AB6E02,), "l_pari/pari_b": (0x4B1EC1EC,),
    "l_pari/pari_c": (0x58AEF446, 0xC1A7A5FC),
    "l_pari/pari_d": (0xC579CCFF, 0x5C709D45),
    "l_romd/romd_a": (0xECAB928B,), "l_romd/romd_c": (0xEDAE08CF,),
    "l_romn/romn_a": (0x181828A7, 0x8111791D), "l_romn/romn_b": (0xA1A1D586,),
    "l_rush/rush_a": (0x21DAB93F, 0xB8D3E885), "l_rush/rush_b": (0x9863441E,),
    "l_tokd/tokd_a": (0xD6432E90,), "l_tokd/tokd_b": (0x5DFFD0C4,),
    "l_tokd/tokd_c": (0xD746B4D4, 0x4E4FE56E),
    "l_tokn/tokn_a": (0x22F094BC, 0xBBF9C506), "l_tokn/tokn_b": (0x9B49699D,),
}


def read_table(data):
    entries = {}
    cursor = 4
    while cursor + 8 <= len(data):
        key, size = struct.unpack_from(">II", data, cursor)
        cursor += 8
        if size > len(data) - cursor:
            raise ValueError("Truncated subtitle text table")
        entries[key] = data[cursor:cursor + size]
        cursor += size
    return entries


def extract_cues(entries):
    start_ms = 0
    for entry in entries:
        position = 0
        for match in re.finditer(r"\{(\d*\.?\d+)\}", entry):
            text = " ".join(entry[position:match.start()].split())
            end_ms = start_ms + int(Decimal(match[1]) * 1000)
            if text and end_ms > start_ms:
                yield f"{start_ms}\t{end_ms}\t{text}\n"
            start_ms = end_ms
            position = match.end()
        if entry[position:].strip():
            raise ValueError("Untimed subtitle text")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text_table", type=Path)
    parser.add_argument("output", type=Path, help="enhanced cinematics directory")
    args = parser.parse_args()
    table = read_table(args.text_table.read_bytes())
    files = {}
    for movie, keys in MOVIE_KEYS.items():
        entries = [table[key].rstrip(b"\0").decode("cp1252") for key in keys]
        cues = list(extract_cues(entries))
        if not cues:
            raise ValueError(f"No cues for {movie}")
        files[args.output / f"{movie}.subtitles.tsv"] = cues
    for path, cues in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text("".join(cues), encoding="utf-8", newline="\n")
        temporary.replace(path)
        print(f"{path.name}: {len(cues)} cues")


if __name__ == "__main__":
    main()
