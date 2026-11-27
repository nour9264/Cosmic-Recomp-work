# Ultimate Cannonbolt (form 24)

Ultimate Cannonbolt is reached by transforming from Cannonbolt with the Hero Time button (L3), the same way the other Ultimate forms are. It is not on the roster wheel. This document covers the form, its native support and the ordered finishing steps.

## What is in the source

- **Form bundle** (`tools/prepare_ultimate_cannonbolt.py`): builds `installation/vilgax/ultimatecannonbolt` from the owner's Blender exports (`ucb-body.bin`, `ucb-ball.bin`, the two textures and `Ultimate_Cannonbolt_Clean.wav`) and the normal Cannonbolt bundle: new mesh and skin on the normal rig, neutral specular and normal maps, its own character record and attack table (every attack id renamed so it never shares a record with the normal form), registration, upgrade and cost scripts, the voice bank and an Albedo texture entry.
- **Hero Time pairing** (`tools/prepare_hero_time_candidate.py`, `--vilgax` in `build_release_bridge.py`): pair 23 to 24 and the call that plays the host voice are added only when the bridge is built with Vilgax aliens. The number of forms loaded by the program is now read from a variable, so installs with five or six forms both load.
- **Launcher** (`launcher/vilgax/VilgaxAliens.cs`, `AllAliensPatch.cs`, `NativeBridge.cs`): form id 24 is accepted only for the folder named `ultimatecannonbolt`; forms 20 to 23 are on the wheel and 24 is not (`ImportedForm.OnWheel`); `transform.wav` is handed to the game through `BEN10_ULTIMATE_CANNONBOLT_VOICE`.
- **Native** (`native-rex/src`, hooks added by `tools/apply_game_integration.py` and `tools/apply_form_effects.py` to locally generated code):
  - `ucb_effect_owner.h`: its private attack signals belong to the live attached effect tree, not to the scene or to another copy of the node elsewhere in the level.
  - `ucb_suction.h`: the side intake follows the live ball bone instead of the character-facing effect root.
  - `ucb_screen_flash.h` / `ucb_screen_flash_state.h`: the white screen flash when the suction is released (HUD footprint kept clear); `weapon_trace.h` raises it on the release event.
  - `pc_menu_bridge.h`: the voice call (`PlaySoundW`, so the build now links `winmm`).
  - `lookup_guard.h` / `weapon_trace.h`: the diagnostic lookup and event trace run only when `BEN10_RESOURCE_TRACE` is set, so ordinary node events no longer take the trace mutex.

## Verified here

- `tools/test_ultimate_cannonbolt.py`: static checks always; with `COSMIC_UCB_EXPORTS`, `COSMIC_INSTALLATION` and `COSMIC_NORMAL_BUNDLE` it runs the importer and checks the bundle.
- The importer's `atk_ucb.ddf`, `callout.fsb`, `callout.txt`, `character-records.bin`, `form-ids.txt`, `forms.bin`, `transform.wav` and the empty record files are byte-identical to the build's first Ultimate Cannonbolt output, and the Albedo entry file matches the working build. The package differs in size because the owner's exports changed after that first output (badge arms), so its bytes were not compared.
- The clone compiles and links with the native changes (`ben10_app.h`, `pc_menu_bridge.h`, `weapon_trace.h`, `lookup_guard.h`); the two hook sites the apply tools edit (`sub_821E2680`, `sub_8213A9A0`) already carry exactly the text the tools write in the locally generated code the working build compiles.
- The Hero Time program test passes with the default program (no Cannonbolt pair).
- Not run in the game from an executable built out of this checkout.

## Finishing steps (`tools/cannonbolt/`)

The animation clips, effects, audio and damage of both Cannonbolt forms are produced by ordered steps that read and write the installed `g_cb.xbx`, `g_ucb.xbx`, `atk_*.ddf` and `forms.bin`. Paths come from `cannonbolt_paths.py` (`COSMIC_APP`, `COSMIC_WORK`, `COSMIC_VILGAX_DUMP`); each step writes a candidate and its saved copies into the work folder, and many pin the exact input they expect. Scripts that import `mathutils`, `bpy` or `numpy` run under Blender (`blender -b --python tools/cannonbolt/<step>.py`), the rest under Python.

| Group | Steps (in order) |
| --- | --- |
| Source data from the owner's PS2 *Protector of the Earth* files | `extract_player_wad`, `decode_bigb`, `catalog_cannonbolt`, `catalog_original_vfx`, `decode_original_vfx` |
| Spin, audio and Meteor Bolt | `prepare_spin_cycle`, `prepare_remaining`, `prepare_attack_bank`, `fix_meteor_audio`, `recover_ucb_audio`, `compact_poe_audio`, `refine_specials`, `steer_and_loose_audio`, `meteor_air_control`, `meteor_fast_slam_audio_endian`, `louder_weighted_impact`, `clean_synced_audio`, `match_attack_loudness` |
| Spin and suction effects | `spin_backspin_vfx`, `attach_ucb_vfx_root`, `fix_vfx_dispatch`, `refine_air_rubble`, `global_vfx_sprites`, `port_original_vfx_sprites`, `fix_original_vfx_blend`, `spin_mesh_vfx`, `finish_spin_mesh_vfx`, `extend_spin_and_rocks`, `suction_and_cone_vfx`, `refine_suction_reference`, `suction_side_intakes`, `align_suction_intakes`, `suction_intake_cones`, `extend_suction_release`, `spin_growth_suction_flash`, `suction_sync_and_fade`, `ball_attached_suction_release` |
| Pressure burst, release pose, Meteor Bolt for the normal form | `port_pressureburst`, `refine_pressure_meteor`, `fix_pressure_meteor_render`, `suction_release_pose`, `copy_meteor_to_cannonbolt`, `swap_cannonbolt_meteor` |
| Bounce Ball | `ultimate_bounce_ball`, `bounce_impact_reference`, `fix_bounce_impact_startup`, `restore_bounce_stable_effects`, `bounce_progressive_ground_impacts`, `bounce_sync_width_cleanup`, `bounce_stop_on_animation`, `fix_bounce_audio_event`, `boost_bounce_impact_audio` |
| Damage, layout, owners | `balance_ucb_damage_collisions`, `fix_cannonbolt_render_and_hits` (uses `tools/fix_vilgax_punch_reactions.py`), `install_ucb_owner_shoulder_fix`, `isolate_cannonbolt_effect_owners` |
| Blender-authored motion (both forms) | `author_ucb_dodge_and_long_attacks`, `author_cb_dodge_and_long_attacks`, `install_ucb_approved_actions`, `validate_install_cannonbolt_actions`, `fix_cannonbolt_long_attack_timing`, `swap_ucb_aerial_counter`, with `author_alien_actions`, `create_ultimate_cannonbolt` and `export_ultimate_cannonbolt` for the model and animation export |
| Normal-form visuals, impacts, hit ranges, counter | the six steps in `docs/CANNONBOLT.md` |

The order above is the order they were run in the working build; the Blender-authored group ran in the middle of the 24th (after the damage step, before the shoulder fix). The native effect builds that went with some steps (relinking the executable) are not ported: that code is the `ucb_*.h` and hook changes above, compiled from source. `isolate_cannonbolt_effect_owners` and `install_ucb_owner_shoulder_fix` no longer swap the runtime executable.

**Replayed here.** Each of the 51 Ultimate Cannonbolt steps with a saved result was run on its own in a scratch install (the build's saved "before" files laid over a copy of the working install, earlier recorded results carried forward) and its candidate files were compared byte for byte with the ones the build saved (`source-sync-check/replay_ucb_steps.py`, not part of the repository):

- 39 steps produced byte-identical candidates (g_cb, g_ucb, attack tables, audio banks, forms), including the effect-owner isolation (eight files).
- 4 produced identical packages but one differing file each: `atk_ucb.ddf` in two early steps (the scratch attack table was not the one of that moment) and a `preview.png` review image in two steps.
- 8 could not be reproduced in the scratch install because their pinned input state was not kept (`fix_meteor_audio`, `recover_ucb_audio`, `clean_synced_audio`, `attach_ucb_vfx_root`, `port_pressureburst`, `fix_bounce_impact_startup`, `fix_cannonbolt_render_and_hits`) or because they need the owner's corrected model file (`install_ucb_owner_shoulder_fix`).
- The Blender-side group, the PS2 extraction steps and `create_ultimate_cannonbolt` / `export_ultimate_cannonbolt` were ported and compile but were not replayed (the one tried, `fix_cannonbolt_long_attack_timing`, stopped on state that was not saved).
- Replaying the whole chain in one run from the importer output was not done; only per-step results are verified.

## Not in this step

- The Ultimate Way Big pieces of the same files (beam tint, outgoing damage scaling, form 25) and the Ben upgrade program.
- The Ultimate Cannonbolt transformation animation, chest taps and menu pictures (S6, S7).
- No run of the game from an executable built out of this checkout; how the effects look and sound was judged only by the repository owner on the working build.
## Asset provenance

| Asset | Origin |
| --- | --- |
| Ultimate Cannonbolt body and ball meshes, textures, rig weights | authored in Blender by the repository owner on the normal Cannonbolt rig (the rig and animations come from *Vilgax Attacks*, see `docs/CANNONBOLT.md`) |
| `Ultimate_Cannonbolt_Clean.wav` (name callout and transformation voice) | supplied by the repository owner; origin to be confirmed at S9 |
| Wind, rock, pressure-burst, ball-rotation, bounce and impact motion and effects, audio samples (steps in the first four groups) | derived from the owner's PS2 *Protector of the Earth* files, read from the owner's own copy when the steps run; not distributed; this is a large share of the finish, so whether any of it may ship is the repository owner's decision (S9) |
| Dodge, long-attack and counter motion | authored in Blender by the repository owner |
| Importer, steps, native code, tests | authored in this repository |
