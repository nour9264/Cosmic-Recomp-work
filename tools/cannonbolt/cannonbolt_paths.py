"""Where the Cannonbolt finishing steps read and write.

COSMIC_APP          the install to change: a folder holding `installation/` (and `runtime/` for steps that protect it).
COSMIC_WORK         where each step saves its before/after copies and validation.json (default: build/cannonbolt-work).
COSMIC_VILGAX_DUMP  the extracted Vilgax Attacks folder (only the steps that read its effect and mesh data).
A missing setting stops the step with a message; nothing is guessed from a personal folder.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get('COSMIC_WORK') or REPO / 'build/cannonbolt-work')
if not os.environ.get('COSMIC_APP'):
    raise SystemExit('Set COSMIC_APP to the install folder that holds installation/ (and runtime/).')
APP = Path(os.environ['COSMIC_APP'])


def vilgax_dump():
    value = os.environ.get('COSMIC_VILGAX_DUMP')
    if not value:
        raise SystemExit('Set COSMIC_VILGAX_DUMP to the extracted Vilgax Attacks (Xbox 360) folder.')
    path = Path(value)
    if not (path / 'global/e_cb.xbx').is_file():
        raise SystemExit(f'{path} does not look like the Vilgax Attacks folder (global/e_cb.xbx missing).')
    return path
