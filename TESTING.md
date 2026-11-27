# Alpha validation scope

`VALIDATION.json` records the release gate. It separates unit/fixture evidence, real native-process checks and earlier user confirmation. It does not declare full game compatibility.

| Area | Evidence | Limit |
| --- | --- | --- |
| Animation conversion | Independent C# and Python output matched across eight level stream banks; original clips preserved, dictionary lookup and repeated installation checked | Format and installation checks do not establish every animation's gameplay |
| Transformations | Eleven ordinary forms visually appeared in the recorded Paris corridor; Rath rechecked with the new presentation runtime | Other levels, extended abilities and combat remain open |
| Video menus | Real original-menu callbacks applied Show FPS OFF/ON and window/display choices | Native GPU-only captures omit later host UI/font drawing |
| Live output size | One native PID changed client size 1280×720 → 1920×1080 → 1280×720 | Output/presentation size, not internal supersampling |
| Fullscreen modes | Visible startup samples showed exclusive 1280×720 and borderless desktop 1920×1080 without window captions; in-game mode callbacks accepted | One monitor/driver configuration; unsupported modes are rejected |
| Wipe Data | Opened confirmation, canceled, reopened and confirmed; game exited before archiving and launcher reopened | Disposable copy only; original user saves were never reset |
| Save archive | Six progress files preserved byte for byte, including additional container headers; native video preferences retained | Does not validate every campaign checkpoint |
| Save/Continue | Earlier user-confirmed save, shutdown, restart and Continue recovered the checkpoint | Separate evidence from the reset test |
| SDK runtime | Retained parent relink and recompiled original SDL unit were byte-identical before adding the presentation extension | Full clean-machine rebuild remains unverified |

The ISO parser, installation/save-preservation and menu transformation suites also pass. Branch targets, original Rath progression, the authored Gameplay input guard, idempotence and unknown-edit rejection are checked separately from gameplay.

No new FPS gain, stable 60 FPS, full campaign completion or fix for the earlier first-boss death crash is claimed. Flicker/judder above 30 FPS is the next priority, investigated with the frame limit disabled. Repeated host presents and an FPS average do not prove unique smooth game frames.

Local probes use recorded controller input and mute game audio. Their original assets, saves, raw logs and screenshots are not distributed. The public validation summary contains no personal paths or account data.

**Photo Mode.** `tools/test_photo_pause_menu.py` builds the bridge and checks the pause-menu patch on local original scripts (row order, in-place upgrade, idempotence, rejection of unknown edits). The camera, controls and screenshots are checked by playing; see `docs/PHOTO_MODE.md` for what was and was not verified.

**Ben's Ultimatrix model swap.** `tools/test_ben_ultimatrix.py` is a static check (draw-range constants, hook wiring, `pc-cosmetics.ini` keys, 2048 px limit, Albedo pack tool on a synthetic pack); it does not run the game. See `docs/BEN_ULTIMATRIX.md`.

**Cannonbolt import.** `tools/test_cannonbolt_import.py` runs static checks anywhere; with `COSMIC_VILGAX_DUMP` and `COSMIC_INSTALLATION` set it also runs the importer on the local Vilgax Attacks copy and checks the written bundle. See `docs/CANNONBOLT.md`. `tools/test_cannonbolt_pipeline.py` statically checks the six finishing steps in `tools/cannonbolt/`; replaying them needs local game files (commands in the same document).

**Ultimate Cannonbolt.** `tools/test_ultimate_cannonbolt.py` checks the Hero Time pairing, launcher id rules and native hooks statically, and runs the importer when `COSMIC_UCB_EXPORTS`, `COSMIC_INSTALLATION` and `COSMIC_NORMAL_BUNDLE` are set. See `docs/ULTIMATE_CANNONBOLT.md` (the ordered finishing steps in `tools/cannonbolt/` are checked statically by `test_cannonbolt_pipeline.py`).

**Ultimate Way Big.** `tools/test_ultimate_way_big_form.py` (VM model of the form scripts) and `tools/test_ultimate_way_big_native.py` (static wiring across native, launcher, apply tools and Hero Time). The two preparation tools were checked byte-for-byte against locally saved outputs; see `docs/ULTIMATE_WAY_BIG.md`.

**Upgrade system.** `tools/test_ben_upgrade_program.py` and `tools/test_transformation_animation.py` run the authored scripts on the VM model; `tools/test_ben_upgrades_wiring.py` keeps prices, bridge registrations, the HUD arc hook and the launcher hooks in agreement. The animation tools were checked byte-for-byte against locally saved outputs; see `docs/UPGRADES.md`.

**Remaining tweaks.** `tools/test_gameplay_tweaks.py` statically checks the VM guard, launcher helpers, live frame limit and the imported-alien animation tools; see `docs/GAMEPLAY_TWEAKS.md`.

**Bundled assets.** `tools/test_bundled_assets.py` checks `bundled-assets/MANIFEST.json` against the files and the installer's copy, idempotence, move-aside and damage refusal; see `docs/BUNDLED_ASSETS.md`.

**Alpha 9 test build.** `tools/stage_test_app.py` assembles a portable test app from a local build (`docs/BUILD_ALPHA9.md`). The Alpha 9 build was compiled from this source with the owner's locally generated game code; it launches, but nothing is verified in gameplay until it is played from a fresh ISO import.

**Ben additions in the import.** `tools/ben_ultimatrix/ben_model_patch.py` and `tools/bundle_delta.py` apply the owner's Ben Ultimatrix data and the added animation clips to the player's original files. On a scratch copy of the original game files the installer produced all 37 changed files byte-identical to the working build, and the Albedo pack built with the shipped entry matched the working build's entries; see `docs/BUNDLED_ASSETS.md`.

**First install test (2026-11-26).** Importing an ISO with the Alpha 9 test app installed everything, but the first start failed: the animation-stream step read Ultimate Way Big's package from `game/global` while the installer puts it in `game/l_tokd`. Fixed in `AlienAnimationStreams.Ensure`; after the fix the game starts, loads a level and runs (checked by starting it for about a minute; no gameplay testing).

- 2026-11-26 (second test): added the missing Ultimate Cannonbolt effect sprites (6 in global.xbx, 1 in gtex_s.xbx, 1 Albedo entry) to bundled-assets and the importer; removed the optional PS3 and Alien Force import sections from the launcher; Upgrade Forms and the wheel now map roster ordinals to form IDs before checking the purchased tier (CosmicRosterAllows). Launch checked only (game started, circdisp.ds/globals.ds repatched); gameplay not tested.

- 2026-11-26 (third test): Photo Mode no longer starts while the game is in its own paused screen (R3 form screens). The form ring and its hover lookup now check the purchased tier against the real form ID (table 4c9c726b position to form ID) instead of the list position: Rath 11 (level 1), Four Arms 19 (2), Chromastone/Jetray/Goop/Cannonbolt 20-23 (3) stay padlocked at level 0 (seen in the ring on screen and in the roster-check log lines). Removed the temporary slot trace (it overwrote script registers; suspected cause of a crash after swapping a form in the ring, not yet confirmed). Not played through: swapping then transforming.

- 2026-11-26 (fourth test): cause of the crash after swapping an alien with R3 found by reading the scripts and logs: without Master Control, CosmicAlienUpdate put the saved original four slots back every frame, undoing the R3 swap in the slot table while the game had already loaded the new form in place of the old one. The saved four now follow the player's own changes (CosmicAlienFollow); only a page showing extras is restored. VM test added (R3 change stays). Not run in the game.

- 2026-11-26 (fifth test): the Master Control pages no longer repeat the four aliens the player has set with R3 (the pages list the loaded extras that are not among the current four). A form moved out of the four is not loaded until the next mission, so it returns to the pages then. VM test added; not run in the game.

- 2026-11-26 (sixth test): cosmetics are now bought with the game's points by the script and owned flags are saved in the game save (new game = none owned, each starts OFF when bought); the native menu and effects read ownership from the script sync (cosmic_cosmetics_sync / menu tick mask). VM test added; built into alpha9-test; not run in the game. Purchases made in earlier builds (stored in pc-cosmetics.ini) are not carried over.

- 2026-11-26 (seventh test): a form that leaves the player's four with the R3 screen is loaded again as an extra once the change has settled (150 ticks) and is added to the Master Control pages; forms in the four are skipped at mission unload. Tested in the VM model only; not run in the game.

- 2026-11-26 (eighth test): crash after many swaps traced to paging soon after a swap: the saved four still held the old forms, so leaving an extras page wrote them back over the swap (same crash as before). The saved four now take a change at once; forms that left are queued and loaded again once the change has stood for 150 ticks, skipping any that came back. VM tests for quick paging and several swaps in a row; not run in the game.

- 2026-11-26 (ninth test): double jump of Ultimate Swampfire crashed (20:51:12, guest read of address 6 in sub_821EDF18 called from sub_821EA860 with a null effect instance: sub_822313C8 returned 0). apply_effect_guard.py skips that set-up when the instance is null (the code after the call already handles null) and logs 'Effect guard'. Built into alpha9-test; not run in the game. Not known why the instance could not be created.

- 2026-11-27 (interact animations): the four Alien Force aliens and the five Ultimates got a Blender-made interact animation (docs/INTERACT_ANIMATIONS.md). Findings from the in-game `Anim controller` trace: the game requests roles 5, 0x48, 0x49, 0x4a in a fixed order with its own timings; every original alien's interact clips share one timeline (in 0, loop ~1440-1600, out ~4960 ticks). Final layout: the whole sequence on role 0x48, stubs on the other two. The owner approved the result in alpha9-test; the animation trace needs `installation/user/anim-trace.txt` (the launcher removes BEN10_* variables). Crash seen once when transforming into Ultimate Humungousaur (Rome level): null model lookup F6E0FED2, cause not found. Bundle re-staged (101 files); not played from an installer build.
