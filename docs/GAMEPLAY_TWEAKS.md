# Gameplay options and remaining tweaks

Small changes that are not part of one alien or of the upgrade system.

## In the game

- **Gameplay options page:** *All Aliens*, *Hero Time (L3)* and the *Play as Albedo* switch of the launcher are gone; the first two are now bought as Ultimatrix levels and Albedo is a purchase (`docs/UPGRADES.md`). The page lists Invert Up/Down, Invert Left/Right, Vibration, Play as Albedo (locked until bought), Background Controller Input, Show HUD, Customize Keyboard and Mouse Controls, Wipe Data and Field of View. The launcher's Gameplay tab drops the same rows.
- **Script VM guard** (`native-rex/src/vm_guard.h`, hook added by `tools/apply_vm_guard.py`): the member-access opcode used to call the object lookup with whatever a script variable held. When that was a plain number (seen with Ampfibian's weapon event) the call read guest memory at number + 8 and the game died. A value that is neither null nor a plausible guest address is now treated as "no object", as the VM already treats null, and is logged (first 20 times).
- **Live frame limit:** changing the frame limit in Options also sets the guest refresh rate (120 Hz only for the 120 FPS limit, otherwise 60 Hz) instead of waiting for a restart.
- **Trace and diagnostics:** the weapon, animation and resource tracers run only when their environment switches are set (`BEN10_RESOURCE_TRACE`, `BEN10_ANIM_TRACE`), so ordinary frames no longer take their locks.

## Launcher

- `launcher-status.txt` is written through one helper (`InstalledGame.PublishLauncherStatus`) used by both bridges: a unique temporary file, an atomic replace, and a log line instead of a crash when Windows holds the file open.
- The graphics diagnostic profile `standard-no-reuse` is accepted.
- The Ultimate voice links keep a count limit for effect sounds (`effectLimit`) and still recognise installs made with the older limit.

## Tools for the imported Vilgax Attacks aliens (`tools/vilgax_animations/`, `tools/update_alien_force_art.py`)

Paths come from `vilgax_animation_paths.py` (`COSMIC_APP`, `COSMIC_WORK`, `COSMIC_BLEND_DIR`).

- `export_chromastone_native_animations`, `export_goop_native_animations`, `export_jetray_native_animations` (run under Blender): convert the owner's hand-made animations for the three aliens into native clips and a validation report.
- `install_*_native_animations`: install a validated patch into an installation, with backup.
- `fix_goop_melt_dodge`, `fix_jetray_lunge_timing`, `fix_goop_package_layout`, `fix_jetray_package_layout`: one-time repairs of dodge, lunge timing and package layout.
- `tools/update_alien_force_art.py`: refreshes the roster and R3 ring pictures of the Alien Force aliens in an installation without rebuilding the forms (arguments in its `--help`).

## Verified here

- `tools/test_gameplay_tweaks.py` (static): the VM guard header, hook tool and apply step; the launcher helpers and removed rows; the refresh-rate line; every animation tool compiles and takes its paths from the paths module.
- The VM guard hook tool is idempotent on a copy of the locally generated unit; the clone compiles and links with that unit; the launcher's `main.cpp` compiles; the bridge builds from the clone with all feature flags; the whole VM and wiring test set passes.
- Not replayed: the Blender exports and the three installers (they need the owner's animation exports), and the art refresh. Not run in the game from an executable built out of this checkout.

## Left out on purpose

- The pause-menu height experiments (`PauseScaleHook`, `PieceY/PieceH`), the Photo Mode research logging and layer stepping, `cam_probe.h`, and the first-generation Ben device swap: working-build experiments that were abandoned.
- `tools/install_cannonbolt_bundle.py`, `install_cannonbolt_roll_audio.py`, `fix_cannonbolt_mesh_header.py`: replaced by the importer and `tools/add_cannonbolt_icon.py` (see `docs/CANNONBOLT.md`).

## Asset provenance

| Asset | Origin |
| --- | --- |
| Chromastone, Goop and Jetray animation patches | authored in Blender by the repository owner on the Vilgax Attacks rigs; the rigs and base animations come from *Vilgax Attacks* (Xbox 360), read from the owner's own copy |
| Tools, native code, tests | authored in this repository |
