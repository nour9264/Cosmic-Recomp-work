# Upgrade system (Upgrade Forms)

Ben's upgrades live in the original **Upgrade Forms** screen. A button prompt in its footer (**Y / Triangle**, or the on-screen prompt) opens the **Upgrades** overlay, drawn natively in the same style as Options. Points are the game's own Upgrade Points; nothing is bought with anything else.

## What can be bought

| Page | Items | Price (points) |
| --- | --- | --- |
| Ultimatrix Upgrades (levels 1 to 6, in order) | Rath, Four Arms, Alien Force Aliens, Ultimate Aliens, Master Control, Cooldown Reduction | 15,000 / 15,000 / 30,000 / 50,000 / 100,000 / 60,000 |
| Ben Upgrades | Health, Energy: three levels each, +20% of base capacity per level | 15,000 / 30,000 / 45,000 per stat |
| Cosmetics | Play as Albedo, Transformation Animation, Realistic Ultimatrix, Potis Altiare | 70,000 / 25,000 / 40,000 / 30,000 |

The campaign total of the first two pages is exactly 450,000 points (checked at compile time and by `tools/test_ben_upgrades_wiring.py`). Cosmetics are paid from the same points by the game script (`CosmicBuyBenCosmetic`, action 48 + item) and the four owned flags are kept in the game save (`CosmicBenCosmetic0..3` in the upgrade table), so a new game starts with none and each one starts OFF after it is bought. `user/pc-cosmetics.ini` only keeps the Realistic and Potis Altiare ON/OFF choices (old `owned_*` and `spent` lines are ignored).

## Effects

- **Level 1 to 4** unlock Rath, Four Arms, the Alien Force aliens (Jetray, Goop, Chromastone, Cannonbolt) and the Ultimate forms; the roster check and the wheel use the saved tier. **Level 4** also turns Hero Time on; **level 5 (Master Control)** enables paging through every unlocked alien; **level 6** shortens the Ultimate cooldown (recharge x0.8). The old *All Aliens* and *Hero Time* switches in Options are gone: ownership replaces them.
- **Health / Energy** raise the stock capacities and widen the HUD arcs; the empty part of the extended arc is painted green (red for Albedo) by `ben_upgrade_frame.h`, following the arc's live fill (`ben_upgrade_arc.h`, hooked into the HUD arc draw by `tools/apply_ben_upgrade_arc.py`).
- **Cosmetics:** *Play as Albedo* stays locked in Options until bought; *Transformation Animation* plays Ben's own transformation pose before the switch (`tools/prepare_transformation_animation.py`, with the Final Battle gate for Way Big); *Realistic Ultimatrix* and *Potis Altiare* choose the wrist device (`docs/BEN_ULTIMATRIX.md`).

## How it is built

- **Script programs** (`tools/prepare_ben_upgrades.py`, `prepare_all_aliens_candidate.py`, `prepare_hero_time_candidate.py`, `ultimate_chest_tap_program.py`): authored VM code. `tools/build_release_bridge.py --vilgax --ben-upgrades` embeds the replaced globals and the menu wrapper; the launcher applies them at start-up (`AllAliensPatch.UpgradeBenGlobals`, `UpgradeBenScreen`, the guarded transformation requests and the Way Big tap gate) and keeps recognising its own earlier output.
- **Native** (`native-rex/src`): `upgrade_economy.h` (prices), `upgrade_ui.h` + `upgrade_text_table.inc` (translated drawing helpers), `options_video_preview.h` (the overlay and the reduced Gameplay page), `pc_menu_bridge.h` (`ben_upgrades` callbacks: tick, Master Control sync, transformation switch, arc resize), `ben_upgrade_arc.h`, `ben_upgrade_frame.h`, `cosmetics_state.h`, and the overlay-aware text code (`text_overlay.h`, `og_text_overlay.h`).
- **Art and animation tools** (`tools/ben_upgrades/`, paths from `ben_upgrade_paths.py`: `COSMIC_APP`, `COSMIC_WORK`, `COSMIC_ORIGINALS`, `COSMIC_VILGAX_DUMP`, `COSMIC_BLEND_DIR`, `COSMIC_FFMPEG`): portraits and cosmetic previews (`prepare_upgrade_art`, `render_*`, `pack_upgrade_portraits`, `pack_cosmetic_previews`, `prepare_original_badges`), Ben's transformation (`prepare_ben_transform_animation`, `extract_transform_sound`, `prepare_ben_core_raise`, `install_ben_core_motion`) and the Ultimate chest-tap clips (`author_ultimate_chest_taps`, `export_ultimate_chest_taps`, run under Blender).

## Verified here

- VM models: `test_ben_upgrade_program.py` (purchases, bar capacity, HUD branches) and `test_transformation_animation.py` (on, off, duplicate, pause, actor death, unload) pass; `test_hero_time_program.py`, `test_all_aliens_script.py`, `test_ultimate_way_big_form.py` and `test_photo_pause_menu.py` still pass; `test_ben_upgrades_wiring.py` keeps prices, registrations and launcher hooks in agreement; `test_show_hud_option.py` was updated to the reduced Gameplay page.
- The clone compiles and links (every unit that carries a hook, including the HUD arc unit), and the bridge builds from the clone with `--hero-time --four-arms --vilgax --ben-upgrades --discord-presence --ultimate-voices`.
- Replays on the owner's files: `prepare_ben_core_raise.py` reproduces the raised-core package byte for byte; `prepare_ben_transform_animation.py` reproduces the retargeted `a_plyr.xbx`, its eight level streams and the validation report byte for byte.
- Not run in the game from an executable built out of this checkout. Not replayed: the portrait renders and packers (they need the owner's `.blend` files and reference pictures), the sound extraction, the Blender chest-tap scripts, `install_ben_core_motion.py`.

## Not in the source on purpose

- The probe-only installers of the working build (`install_master_control`, `install_transform_animation`, `install_transform_retarget`, `install_ultimate_chest_taps`, `fix_ultimate_tap_layout`, `install_tap_settle`): they copy earlier candidates into one particular install and swap its executable and bridge; the source builds those from `native-rex/src` and the bridge instead. The launcher refreshes the animation streams itself (`importedClips` lists the Ben transformation and the chest-tap clips).
- Hashes of the owner's intermediate development installs that the working build's launcher accepted; only the released profiles are listed.
- Research code left in the working build (pause-menu stretch experiments, trace and layer-stepping helpers).

## Asset provenance

| Asset | Origin |
| --- | --- |
| Upgrade pictures (Rath, Four Arms, Alien Force, Ultimate, Master Control) | made from the game's own models and art (stock Ultimate models rendered in Blender, original badge art), the Alien Force ring pictures and the owner's Blender models for Ultimate Way Big and Ultimate Cannonbolt; where the Alien Force ring pictures come from is to be confirmed at S9 |
| Cosmetics pictures (Albedo, Realistic Ultimatrix, Potis Altiare) | made from reference images supplied by the repository owner |
| Ben's transformation pose and the select sound | derived from *Vilgax Attacks* (Xbox 360), read from the owner's own copy and retargeted to the game's skeleton |
| Ultimate chest-tap motion | authored in Blender by the repository owner on the game's native rigs |
| Translations in `upgrade_text_table.inc` | authored for this repository; to be reviewed before release |
| Scripts, native code, tests | authored in this repository |
