# Cannonbolt (normal form)

Cannonbolt is the sixteenth roster entry (form ID 23), imported from the repository owner's own copy of *Ben 10: Alien Force - Vilgax Attacks* (Xbox 360) with the same importer as Chromastone, Jetray and Goop. Nothing from that game is committed; the importer reads the owner's extracted folder and writes a local bundle.

## What the import covers

- Model, skeleton, textures and all 38 animation clips; roll (`run_01`, `burnout_run_01`) with one baked revolution of the ball, and the ball/body visibility swap on the clips that switch between them.
- Four special attacks: Ball Dash (`balldash_01`), Super Ball (`superball_01`), Power Flop (`powerflop_01`) and Burnout (`burnout_run_01`, with `burnout_in_01` / `burnout_out_01`). Ball Dash, Super Ball and Burnout carry him forward (Burnout fastest); Burnout also gets the original dust and trail effect, the others only hit volumes; Power Flop stays in place.
- Sounds: the character sound project `cboltva` from the original bank, with the special, hurt, jump, land and light-hit sounds; callout sample `cannonbolt.wav`.
- Roster picture from the original texture bank (see `tools/add_cannonbolt_icon.py`), character/person/player/form records. `prepare_albedo_textures.py` recolours a Cannonbolt ring hologram for Albedo when one has been supplied (`COSMIC_RING_PICTURES/cannonbolt_holo.png`); without it the ring uses the roster picture.

The earlier one-off fix-ups for the mesh header and the roll audio are folded into the importer: the written package already has one vertex stream for both draw ranges and the audio project.

## Making and installing the bundle

```
python tools/prepare_vilgax_import.py <extracted Vilgax Attacks folder> <installation> cannonbolt <new bundle folder>
```

Copy the bundle to `installation/vilgax/cannonbolt` (the launcher then installs `g_cb.xbx` and `atk_cb.ddf`, the records and the sound bank at start-up, like the other imported aliens). Add the roster picture to the original textures:

```
python tools/add_cannonbolt_icon.py <bundle>/g_cb.xbx <global.xbx> <gtex_s.xbx> --out-global <new global.xbx> --out-ring <new gtex_s.xbx>
```

The tool reads its inputs and writes new files; replacing the installed ones is a manual step.

## Verified here

- `tools/test_cannonbolt_import.py`: static checks always; with `COSMIC_VILGAX_DUMP` and `COSMIC_INSTALLATION` set it runs the importer and checks the bundle (package sections, one vertex stream, the four special routes reach real streamed clips, sound names, roster picture added without touching other sections).
- The clone's importer produces byte-identical bundles for Chromastone, Jetray and Goop before and after this change (the key-sorted payload order is used for Cannonbolt only).
- The new bundle matches the working build's installed bundle in seven of eleven files. The four that differ come from later hand work (below).

## Finishing steps (`tools/cannonbolt/`)

After the import, the working build finishes the normal form with six steps. Each reads the installed `g_cb.xbx` (and `atk_cb.ddf`), pins the exact input it expects, writes a candidate plus its saved "before" copies into the work folder, and changes the installation only with `--install` (with rollback if a check fails). Run them in this order:

| # | Step | What it does |
| --- | --- | --- |
| 1 | `port_normal_cb_vilgax_visuals.py` | Brings the Vilgax Attacks Cannonbolt effects into the three normal specials; the attack records, animation streams, Meteor Bolt and the Ultimate form are untouched. Reads `e_cb.xbx` from the Vilgax Attacks copy. |
| 2 | `align_normal_cb_ground_impacts.py` | Places each impact where the ball actually lands in the authored poses (Super Ball contacts, Ball Dash contact). |
| 3 | `fade_normal_cb_ground_impacts.py` | Mesh-alpha fade of the ground impacts and a Meteor landing effect, normal form only. |
| 4 | `independent_normal_cb_impacts.py` | One private, independently fading pulse per ground contact. |
| 5 | `normal_cb_visual_hit_ranges.py` | Sizes the hit volumes and damage per special (circle 1.0, triangle 0.75, square 1.75, cross 1.5) to the approved visual contacts. Reads Big Chill's node table from `g_bc.xbx`. |
| 6 | `normal_cb_aerial_counter.py` | Routes the normal dodge-counter pair to the aerial clips already in the Ultimate Cannonbolt package (attack table only). |

```
set COSMIC_APP=<folder holding installation\>       set COSMIC_WORK=<folder for saved copies>
set COSMIC_VILGAX_DUMP=<extracted Vilgax Attacks>   python tools/cannonbolt/<step>.py [--install]
```

Without `--install` a step only writes its candidate and report.

**Replayed here.** All six steps were replayed in a scratch install, starting from the saved "before" package of step 1 and with the Ultimate Cannonbolt, Big Chill and (stand-in) runtime files the steps only check for being unchanged: every step produced exactly the package hash recorded when it ran in the working build (`c7e1125b`, `b1e5241a`, `2748908f`, `45bfb00a`, `0e035cb5`), and the attack table after step 6 matches (`5c1f8d48`); both installed copies end identical. `tools/test_cannonbolt_pipeline.py` keeps the static side (order, pinned inputs, `--install` switch, no personal paths).

**What changed from the working build's copies.** Only paths: the installation, work and Vilgax Attacks folders now come from `COSMIC_APP`, `COSMIC_WORK` and `COSMIC_VILGAX_DUMP`; the independent-impact step finds step 3's saved package by hash instead of a dated folder; a pinned hash of the build's executable was dropped (the executable is still checked for being unchanged).

## Not in this step

- The steps that produce the state step 1 starts from (Meteor Bolt, render and hit fix, Blender dodge and long attacks, effect-owner isolation) are ported in `tools/cannonbolt/` and described in `docs/ULTIMATE_CANNONBOLT.md`, since they also change the Ultimate package; replaying the whole chain from a fresh import in one run has not been done.
- Ultimate Cannonbolt, the upgrade menu pictures and the Cosmetics page.
- No run of the game from an executable built out of this checkout; the gameplay look of these effects was checked only by the repository owner on the working build.

## Asset provenance

| Asset | Origin |
| --- | --- |
| Model, skeleton, textures, animations, sounds, roster picture | derived from *Vilgax Attacks* (Xbox 360), read from the owner's own copy at import time; not distributed |
| Impact, landing and hit-range effects (steps 1 to 4) | the Vilgax Attacks effect meshes, read from the owner's copy when the step runs; their placement, timing and fades are authored here |
| Dodge-counter clips (step 6) | animations already in the Ultimate Cannonbolt package (authored by the owner in Blender; S5) |
| Importer, converters, finishing steps, tests | authored in this repository |
