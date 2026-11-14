"""Build the game-text translation tables the overlay uses for Russian, Japanese and Arabic.

Input: build/game-text-segments-en.txt (the English text segments, one per line, numbered from 1) and, per
language, parts named <code>_<n>.txt in build/game-text-translations/ with lines "N<TAB>translation".
Output: <installation>/user/text-<code>.tsv with "English<TAB>translation" lines (UTF-8), and with --shipped a
folder of text-<code>.tsv files keyed by a hash of the English text ("<16 hex><TAB>translation"), which holds the
translations only and is what ships with the game (native-rex/translations). The English table is private game text and
is never committed."""
import argparse
import re
from pathlib import Path


def text_hash(english):
    """FNV-1a 64 over the text as the game holds it (cp1252); native-rex/src/text_overlay.h computes the same."""
    value = 1469598103934665603
    for byte in english.encode('cp1252', errors='replace'):
        value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path, help='the build folder')
    parser.add_argument('user', type=Path, help='installation/user folder to write into')
    parser.add_argument('--shipped', type=Path, help='also write the hash-keyed files that ship with the game here')
    args = parser.parse_args()
    english = args.build.joinpath('game-text-segments-en.txt').read_text(encoding='utf8').split('\n')
    folder = args.build / 'game-text-translations'
    for code in ('ru', 'ja', 'ar'):
        found = {}
        for part in sorted(folder.glob(f'{code}_*.txt')):
            for line in part.read_text(encoding='utf8').splitlines():
                if '\t' not in line:
                    continue
                number, text = line.split('\t', 1)
                text = re.sub(r'<b(\d+)>', lambda m: chr(int(m.group(1))), text)  # <b4> is button code 4
                if number.isdigit() and 1 <= int(number) <= len(english) and text.strip():
                    found[int(number)] = text.strip()
        rows = [f'{english[n - 1]}\t{text}' for n, text in sorted(found.items())]
        args.user.joinpath(f'text-{code}.tsv').write_text('\n'.join(rows) + '\n', encoding='utf8', newline='\n')
        if args.shipped:
            args.shipped.mkdir(parents=True, exist_ok=True)
            hashed = [f'{text_hash(english[n - 1]):016x}\t{text}' for n, text in sorted(found.items())]
            args.shipped.joinpath(f'text-{code}.tsv').write_text('\n'.join(hashed) + '\n', encoding='utf8', newline='\n')
        print(code, len(rows), 'of', len(english))


if __name__ == '__main__':
    main()
