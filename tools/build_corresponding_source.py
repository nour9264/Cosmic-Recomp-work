"""Archive tracked consumer/dependency sources plus the applied SDK patch files.

Run from the actual build checkout; --consumer identifies the matching clean Git
snapshot. Original game inputs, generated title C++, build output and Git data
are never selected. SDK sources are already patched and use a relocation token.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def tracked(folder):
    data = subprocess.check_output(['git', 'ls-files', '-z', '--recurse-submodules'], cwd=folder)
    return [Path(p.decode('utf-8')) for p in data.split(b'\0') if p]


def build(consumer, output, licenses):
    consumer = consumer.resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=consumer).strip():
        raise ValueError('Commit the matching consumer source snapshot first')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=consumer, text=True).strip()
    sdk = ROOT / 'third_party/rexglue-sdk'
    ui = ROOT / 'third_party/full-emerald-ui'
    patch = (consumer / 'sdk-patches/rex-sdk-local.diff').read_text()
    additions = [Path(p) for p in re.findall(r'^diff --git a/\S+ b/(\S+)$', patch, re.M)]
    groups = [('consumer', consumer, tracked(consumer)),
              ('rexglue-sdk', sdk, sorted(set(tracked(sdk) + additions))),
              ('recomp-ui', ui, tracked(ui))]
    private = [str(Path.home()).encode(), str(Path.home()).replace('\\', '/').encode()]
    roots = [str(ROOT).encode(), ROOT.as_posix().encode()]
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for label, folder, paths in groups:
            for relative in paths:
                if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
                    raise ValueError(str(relative))
                if label == 'consumer' and (relative.parts[0] in {'build', 'originals', 'iso', 'toolchain', 'third_party'} or
                    relative.as_posix().startswith('native-rex/generated/default/')):
                    raise ValueError('Unexpected tracked private/build input: ' + str(relative))
                source = folder / relative
                if not source.is_file():
                    raise ValueError('Missing corresponding source: ' + str(source))
                data = source.read_bytes()
                if label == 'rexglue-sdk':
                    for prefix in roots:
                        data = data.replace(prefix, b'@COSMIC_CONSUMER@')
                if any(n.lower() in data.lower() or n.decode().encode('utf-16-le').lower() in data.lower() for n in private):
                    raise ValueError('Private path in source: ' + label + '/' + str(relative))
                archive.writestr(label + '/' + relative.as_posix(), data)
                count += 1
                name = relative.name.upper()
                if label != 'consumer' and name.startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'AUTHORS', 'COPYRIGHT')):
                    target = licenses / label / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
        archive.writestr('SOURCE_IDENTITY.json', json.dumps(dict(consumer_commit=revision,
            sdk_commit='c94f5ebdcb3c9d1a460ca48e04f9758448f8d518', sdk_patch_applied=True,
            ui_commit='047bc82d8679e96d1dec19ce2cd8ab677003465f', original_game_assets=False), indent=2))
        archive.writestr('prepare_sdk_source.py', '''from pathlib import Path
root=Path(__file__).resolve().parent
consumer=(root/'consumer').as_posix().encode()
for p in (root/'rexglue-sdk').rglob('*'):
    if p.is_file():
        data=p.read_bytes()
        if b'@COSMIC_CONSUMER@' in data:p.write_bytes(data.replace(b'@COSMIC_CONSUMER@',consumer))
print('SDK include paths relocated. The SDK patch is already applied.')
''')
        archive.writestr('README-SOURCE.txt', '''Cosmic Recomp corresponding source

Run python prepare_sdk_source.py first. The rexglue-sdk tree already contains
the consolidated project patch: do not apply it a second time.
Follow consumer/docs/CONTRIBUTOR_BUILD_RUNBOOK.md section 3B, building the SDK
from the sibling rexglue-sdk folder and installing to consumer/toolchain/rexglue-sdk.
The pinned UI source is in sibling recomp-ui; copy it to consumer/third_party/full-emerald-ui.
Game input and generated title C++ are intentionally absent; provide your own ISO.
After generating/integrating/building, build the combined Alpha 6 bridge explicitly:
python tools/build_release_bridge.py --hero-time --gpu-diagnostics --performance-alpha5 --ultimate-voices --discord-presence
This selects the tested no-reuse path even if an older diagnostic profile exists.
The ordinary non-Alpha-5 bridge retains the upstream defaults.
Source-path privacy mappings used for release binaries:
SDK C/CXX flags: -march=x86-64-v2 -ffile-prefix-map=<checkout>=cosmic-source
Consumer clang-cl CXX flags append: /clang:-ffile-prefix-map=<checkout>=cosmic-source
Map both slash forms of the checkout path on Windows. These mappings change source
path strings; they do not establish gameplay equivalence or a clean-machine build.
''')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Source archive CRC validation failed')
    print(json.dumps(dict(consumer_commit=revision, source_files=count, bytes=output.stat().st_size)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--consumer', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--licenses', type=Path, required=True)
    args = parser.parse_args()
    build(args.consumer, args.output, args.licenses)
