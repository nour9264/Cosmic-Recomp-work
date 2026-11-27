"""Where the Vilgax Attacks alien animation tools read and write.

COSMIC_APP          the install to change: a folder holding `installation/`.
COSMIC_WORK         where each step saves its before/after copies and validation.json (default: build/vilgax-animations-work).
COSMIC_BLEND_DIR    folder with the owner's Blender exports (<alien>-game-export/*.json); defaults to COSMIC_WORK.
A missing setting stops the step with a message; nothing is guessed from a personal folder.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get('COSMIC_WORK') or REPO / 'build/vilgax-animations-work')
if not os.environ.get('COSMIC_APP'):
    raise SystemExit('Set COSMIC_APP to the install folder that holds installation/ (and runtime/).')
APP = Path(os.environ['COSMIC_APP'])
BLEND = Path(os.environ.get('COSMIC_BLEND_DIR') or WORK)
