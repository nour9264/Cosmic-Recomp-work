"""Locate reviewed functions without assuming codegen's file partition order."""
from pathlib import Path


def locate_functions(generated, names):
    requested = set(names)
    matches = {name: [] for name in requested}
    for path in Path(generated).glob('*.cpp'):
        text = path.read_text()
        for name in requested:
            marker = f'DEFINE_REX_FUNC({name}) {{'
            matches[name].extend([path] * text.count(marker))
    for name, paths in matches.items():
        if len(paths) != 1:
            raise RuntimeError(f'Expected exactly one generated {name}, found {len(paths)}')
    return {name: paths[0] for name, paths in matches.items()}
