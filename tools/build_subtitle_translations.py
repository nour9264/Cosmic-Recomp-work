"""Make translated subtitle tracks for the enhanced cinematics.

Each translation file (<code>.txt, private, not committed) lists the translated lines of every clip under
"## <clip>" headings, in the order of the English cues. The English track supplies the timing, and every
output <clip>.subtitles.<code>.tsv keeps it. The game picks the track for the chosen language and falls
back to the English one.

  --zip PACK.zip     read the English tracks from the enhanced cinematics ZIP and add the translated
                     tracks to it (existing entries are left untouched)
  --install DIR      also write them into an installed cinematics folder
"""
import argparse
from pathlib import Path
import zipfile

CLIPS = ['l_chin/chin_a', 'l_chin/chin_b', 'l_mili/mili_a', 'l_mili/mili_b', 'l_pari/pari_a', 'l_pari/pari_b',
         'l_pari/pari_c', 'l_pari/pari_d', 'l_romd/romd_a', 'l_romd/romd_c', 'l_romn/romn_a', 'l_romn/romn_b',
         'l_rush/rush_a', 'l_rush/rush_b', 'l_tokd/tokd_a', 'l_tokd/tokd_b', 'l_tokd/tokd_c', 'l_tokn/tokn_a',
         'l_tokn/tokn_b']


def read_translation(path):
    clips, current = {}, None
    for line in path.read_text(encoding='utf8').splitlines():
        if line.startswith('## '):
            current = clips.setdefault(line[3:].strip(), [])
        elif line.strip() and current is not None:
            current.append(line.strip())
    return clips


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('translations', type=Path, help='Folder of <code>.txt files')
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--install', type=Path)
    parser.add_argument('--no-zip-write', action='store_true')
    args = parser.parse_args()
    pack = zipfile.ZipFile(args.zip)
    english = {}
    for clip in CLIPS:
        rows = pack.read(f'cinematics/{clip}.subtitles.tsv').decode('utf8').splitlines()
        english[clip] = [row.split('\t', 2) for row in rows]
    pack.close()
    outputs = {}
    for file in sorted(args.translations.glob('*.txt')):
        code, lines = file.stem, read_translation(file)
        for clip in CLIPS:
            cues, text = english[clip], lines.get(clip.split('/')[1], [])
            if len(text) != len(cues):
                raise SystemExit(f'{code} {clip}: {len(text)} lines for {len(cues)} cues')
            outputs[f'{clip}.subtitles.{code}.tsv'] = ''.join(
                f'{start}\t{end}\t{line}\n' for (start, end, _), line in zip(cues, text))
        print('Checked', code)
    if args.install:
        for name, data in outputs.items():
            target = args.install / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(data, encoding='utf8', newline='\n')
        print('Installed', len(outputs), 'tracks')
    if not args.no_zip_write:
        with zipfile.ZipFile(args.zip, 'a', zipfile.ZIP_DEFLATED) as pack:
            present = set(pack.namelist())
            added = 0
            for name, data in outputs.items():
                if f'cinematics/{name}' in present:
                    continue
                pack.writestr(f'cinematics/{name}', data.encode('utf8'))
                added += 1
        print('Added', added, 'tracks to', args.zip.name)


if __name__ == '__main__':
    main()
