# Bundled aliens, pictures and voices

The repository owner decided that the extra content ships with the launcher, so a player needs only their own Xbox 360 ISO: after **Prepare game** (the ISO import) the launcher installs everything in `bundled-assets/` by itself. The optional Four Arms (PS3) and Alien Force (Vilgax Attacks) import buttons were removed from the launcher; the import tools (`tools/prepare_four_arms_import.py`, `tools/import_alien_force.py`) stay in the repository for rebuilding those files from your own copies.

## What ships (`bundled-assets/`, 101 files, 34 MB, listed with SHA-256 and origin in `MANIFEST.json`)

| Folder | Content | Origin |
| --- | --- | --- |
| `four-arms/` | Four Arms package, attack table, registration and upgrade scripts | PS3 edition, prepared by `prepare_four_arms_import.py` |
| `vilgax/chromastone`, `jetray`, `goop` | the three Alien Force aliens, with the interact animation (`docs/INTERACT_ANIMATIONS.md`) | *Ben 10: Alien Force - Vilgax Attacks* (Xbox 360) plus the owner's Blender animations |
| `vilgax/cannonbolt` | Cannonbolt, finished (impacts, hit ranges, counter, transformation taps, interact animation) | Vilgax Attacks plus the steps in `tools/cannonbolt` |
| `vilgax/ultimatecannonbolt` | Ultimate Cannonbolt model, attacks, effects, audio, name callout and transformation voice (`transform.wav`) | the owner's Blender model; effects and audio from *Ben 10: Protector of the Earth* (PS2) |
| `user/` | upgrade, master-control and cosmetic pictures, HUD frame art, HD Ultimatrix picture, Ben's transformation select sound, the Ultimate Way Big transformation voice | owner-made and derived, see the manifest |
| `ben-model/`, `deltas/`, `albedo/` | the owner's Ben Ultimatrix model data, patches for the game's own files, and the Albedo entry of the new texture | owner's Blender export; derived from the game's files |
| `ultimate-way-big-export/` | the owner's Ultimate Way Big mesh and textures; the installer builds the form from them and the player's own Way Big files | owner's Blender export |
| `pictures/wheel-icons/` | the finished selection-wheel pictures of Chromastone, Jetray and Goop | owner-made art |

The Alien Force ring pictures and holograms are the PNGs in `tools/alien-force-pictures/` (the refreshed set of the working build).

## How it is installed

- `tools/import_bundled_assets.py` (shipped in the launcher's importer folder) runs right after the ISO import, and on demand as the launcher action `install-bundled`. It checks every file's size and SHA-256 before writing anything; a folder that already exists with different content is renamed `<name>-previous-<id>`, never overwritten; user files get a one-time backup; running it again changes nothing.
- It also extends the game's picture banks in place, as the Alien Force import does: ring pictures and holograms in `gtex_s.xbx`, the three selection-wheel pictures and Cannonbolt's roster picture in `global.xbx`, and Cannonbolt's roster picture in `gtex_s.xbx` (one-time backups beside the files).
- **Ultimate Way Big is built here:** `prepare_ultimate_way_big.py` and `prepare_ultimate_way_big_form.py` run on the player's untouched Way Big files and the bundled export, and write `vilgax/ultimatewaybig` (checked: byte-identical to the working build's bundle, on files extracted from the original game).
- The bridges then apply scripts, records, animation streams and the Albedo texture pack on the first start exactly as for the individually imported forms.
- `tools/stage_bundled_assets.py --installation <finished installation>` refreshes the folder and the manifest when the owner changes content. `tools/build_portable_distribution.py` accepts `bundled-assets/` only when each file matches the manifest (the rest of the asset ban in that tool is unchanged), and `.gitignore` no longer hides the folder.

## Verified here

- `tools/test_bundled_assets.py`: the manifest matches every file; the installer copies all of them, is idempotent, moves a changed folder aside and refuses a damaged bundle.
- On a scratch installation holding the working build's `global.xbx` and `gtex_s.xbx`, the installer reproduced both picture banks **byte for byte** (using the refreshed pictures). On a scratch copy of the original game files it built Ultimate Way Big identical to the working build's and added the four wheel pictures identical to the working build's, using the Python that ships with the launcher.
- Both bridges (standard and with every feature flag) compile with the new action; the staged files contain no personal path strings.
- Not run: the full launcher flow on a real ISO import, a fresh install from a built portable package, and the game started from such an install.

## Applied to the player's own game files

The installer changes game files only when they are the exact originals of the supported ISO (checked by SHA-256); it keeps a one-time `.cosmic-before-...` backup beside each file and skips a file that is not what the patch was made for.

- **Ben's new Ultimatrix:** `ben-model/` holds the owner's finished vertices, indices and texture (3.2 MB). `tools/ben_ultimatrix/ben_model_patch.py` combines them with the player's own stock Ben records and replaces three records in each of the ten level banks (`l_*.xbx`, `_d`, `_t`; Blender is not needed). Checked: all 30 files rebuilt from the original files are byte-identical to the working build.
- **Chest-tap clips and Ben's transformation:** `deltas/*.cdelta` are small patches (60 to 110 KB each, `tools/bundle_delta.py`) for `a_plyr.xbx`, `g_bc`, `g_ec`, `g_hm`, `g_sf`, `g_sm`, `l_tokd/g_wayb.xbx` and, for the Ultimates' interact animation, `g_ubc`, `g_uec`, `g_uhm`, `g_usf` and `g_usm` (their animation sets travel in `vilgax/ultimatecannonbolt/player-records.bin`). They store the added clips and the pieces of the original file they reuse; each records the hash of the file it applies to and of the result. Checked: the seven results are byte-identical to the working build. The launcher merges the clips into the level animation streams itself on the next start.
- **Albedo look of the new Ultimatrix:** the Albedo texture pack is built on the player's machine; the new texture is larger than the stock one, so its finished Albedo entry (`albedo/14934253.entry`) is passed to `prepare_albedo_textures.py` (`--extra-entry`) and replaces the computed one. Checked: the pack built from the patched files has the same 34 entries as the working build's (without the imported aliens' packages in the scratch copy).
- Everything the player's own ISO produces (translations, level and stream files, voice banks) is still made on the player's machine.

## Rights

Bundling content from Vilgax Attacks, Protector of the Earth and the PS3 edition is the repository owner's decision, recorded in `AGENTS.md` and `SOURCES.md`. Those two files now state what is bundled and where it comes from; the owner should read the wording and confirm it before a public release.
