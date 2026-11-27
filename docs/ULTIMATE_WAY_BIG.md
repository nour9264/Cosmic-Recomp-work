# Ultimate Way Big

In the final battle (Way Big against the boss), pressing **L3** as Way Big turns the player into Ultimate Way Big; **L3** again returns to Way Big in the same fight. It uses Way Big's size, rig, attacks, blocking, dodge, lunge and animations, deals **1.5x damage**, shows the Ultimate HUD and plays a voice line on entry. Ben and Albedo each have their own model; the Way Big beam is cyan in both modes. There is no timer.

## What is in the source

- **Native** (`native-rex/src`): `ultimate_way_big.h` (mesh ids, state, the 1.5x damage rule); `way_big_draw_swap.h` (the draw hook: queues the script update on the first player draw, swaps the Way Big mesh, keeps Ben/Albedo in step); `frame_metrics.cpp` (`Ben10SampleWayBigL3`, `Ben10ObserveWayBigForm`); `pc_menu_bridge.h` (`UltimateWayBigRequest`, reset on every level change, voice playback, form trace); `albedo_textures` / `albedo_hud.h` (cyan beam; the beam shaft texture is sampled so it reads cyan); `ultimate_hud_palette.h` / `ultimate_hud_overlay.h` (the Ultimate HUD stays on while Way Big is Ultimate).
- **Generated-code hooks** (`tools/apply_game_integration.py`): the beam vertex colour (`SelectWayBigBeamTint`) and outgoing damage at the shared combat dispatch (`sub_82140398`).
- **Mission script and Hero Time** (`AllAliensPatch.WayBigMission`, called for `l_tokd` by `DiscordPresencePatch.cs`; `prepare_hero_time_candidate.py`): the boss entry's input callback is replaced by `CosmicWayBigUpdate`, a small authored program that asks the native side for the form change and plays the transformation flash.
- **Form bundle** (`tools/prepare_ultimate_way_big.py`, `tools/prepare_ultimate_way_big_form.py`): stage the Ben and Albedo meshes, textures and voice into `l_tokd`, and build `installation/vilgax/ultimatewaybig` (form 25, package `g_uwb.xbx` written into `game/l_tokd`, character record, form scripts). Form 25 is never on the roster wheel, and the launcher sets `BEN10_ULTIMATE_WAY_BIG_FORM` when the bundle exists.
- **Export** (`tools/export_ultimate_way_big.py`, run under Blender): writes the mesh, textures and eye data from the owner's approved model.

## Building the assets (local files only)

1. `blender -b <approved .blend> -P tools/export_ultimate_way_big.py` (`BEN10_WAY_BIG_EXPORT_DIR` chooses the output; `BEN10_WAY_BIG_DONOR_BLEND` the native Way Big rig).
2. `python tools/prepare_ultimate_way_big.py --level <original l_tokd folder> --assets <export> --output <prepared> --voice <wav>`
3. `python tools/prepare_ultimate_way_big_form.py --originals <original game folder> --prepared <prepared> --output <bundle>`; copy the bundle to `installation/vilgax/ultimatewaybig` and the prepared `l_tokd*.xbx`, `g_wayb.xbx` and the voice into the install (the launcher does the bundle part).

## Verified here

- `tools/test_ultimate_way_big_form.py` (VM model of the form scripts: mission package, readiness, entry, return, scale and health restoration) and `tools/test_ultimate_way_big_native.py` (names and ids agree across native, launcher, apply tools and Hero Time) pass; `test_hero_time_program.py` still passes.
- The clone compiles and links with every changed unit, including the five generated units that carry the hooks (draw hook, beam tint, damage, effect owner, suction).
- Both preparation tools were run on the owner's last export and original files: the prepared level and package files (`l_tokd.xbx`, `l_tokd_d.xbx`, `l_tokd_t.xbx`, `g_wayb.xbx`, the voice) and the form bundle (`g_uwb.xbx`, character and form records) are **byte-identical** to the build's saved ones and to the installed bundle.
- Not run in the game from an executable built out of this checkout. The owner played the final battle on the working build; L3 in both directions, Ben and Albedo visuals, voice, beam colour and damage are the owner's observations, not a test here.

## Not in this step

- The transformation (chest-tap) animation that can play before the switch and the gate that holds the request while it plays (`transformation_animation_pending`, `CosmicWayBigTapGate`) are part of the upgrade system: `docs/UPGRADES.md`.
- The Blender authoring history of the model (create, sculpt, paint and verify scripts and the approved `.blend`): the `.blend` is the owner's source asset and is not in the repository.

## Asset provenance

| Asset | Origin |
| --- | --- |
| Ultimate Way Big mesh, weights, textures (Ben and Albedo) | authored in Blender by the repository owner on the game's native Way Big rig |
| `Ultimate_Way_Big_Clean.wav` | supplied by the repository owner; origin to be confirmed at S9 |
| Tools, native code, tests | authored in this repository |
