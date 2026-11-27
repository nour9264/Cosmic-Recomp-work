"""Where the Ben upgrade asset and animation tools read and write.

COSMIC_APP          an install: a folder holding `installation/` (some tools read installed packages).
COSMIC_WORK         where tools write their results (default: build/ben-upgrades-work).
COSMIC_ORIGINALS    the original game files (global/..., as extracted from the owner's own disc).
COSMIC_VILGAX_DUMP  the extracted Vilgax Attacks (Xbox 360) folder.
COSMIC_BLEND_DIR    folder with the owner's .blend files (default: COSMIC_WORK).
COSMIC_FFMPEG       ffmpeg executable (only the transformation-sound extraction).
A missing setting stops the tool with a message; nothing is guessed from a personal folder.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get('COSMIC_WORK') or REPO / 'build/ben-upgrades-work')
BLEND = Path(os.environ.get('COSMIC_BLEND_DIR') or WORK)


def _require(name, hint):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f'Set {name} to {hint}.')
    return Path(value)


class _Lazy:
    """A setting that is only demanded when a tool actually uses it."""
    def __init__(self, name, hint):
        self.name, self.hint = name, hint

    def _p(self):
        return _require(self.name, self.hint)

    def __truediv__(self, other):
        return self._p() / other

    def __fspath__(self):
        return str(self._p())

    def __getattr__(self, attr):
        return getattr(self._p(), attr)


APP = _Lazy('COSMIC_APP', 'an install folder that holds installation/')
ORIGINALS = _Lazy('COSMIC_ORIGINALS', 'the original game folder (global/, l_*/)')


def vilgax_dump():
    path = _require('COSMIC_VILGAX_DUMP', 'the extracted Vilgax Attacks (Xbox 360) folder')
    if not (path / 'global').is_dir():
        raise SystemExit(f'{path} does not look like the Vilgax Attacks folder (global/ missing).')
    return path


def ffmpeg():
    return _require('COSMIC_FFMPEG', 'the ffmpeg executable')
