# Building Alpha 9 from this source

Prerequisites are in `docs/CONTRIBUTOR_BUILD_RUNBOOK.md` (pinned patched SDK, LLVM clang-cl, Visual Studio Build Tools, Ninja). Game-derived inputs stay local: your extracted ISO in `originals/`, the code generated from it in `native-rex/generated/default`.

1. **Generated code:** after code generation run `tools/apply_game_integration.py --generated native-rex/generated/default`, then `tools/apply_text_overlay.py` and `tools/apply_form_effects.py` the same way. `apply_game_integration.py` also applies the Photo Mode, HUD arc and script VM guard hooks (`apply_photo_mode.py`, `apply_ben_upgrade_arc.py`, `apply_vm_guard.py`). All of them are idempotent. Back up `native-rex/generated/default` before editing `ben10_manifest.toml`: the build regenerates it.
2. **Runtime:** `cmake -S native-rex -B build/native-sse41 -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang-cl -DCMAKE_PREFIX_PATH=<sdk> -Drexglue_DIR=<sdk>/lib/cmake/rexglue` then `cmake --build build/native-sse41`. The runtime also links `winmm`.
3. **Launcher:** `cmake -S launcher/native -B build/launcher -G Ninja -DCMAKE_BUILD_TYPE=Release` and build (needs `third_party/full-emerald-ui`).
4. **Bridges** (all with `--hero-time --gpu-diagnostics --performance-alpha5 --ultimate-voices --discord-presence`): `python tools/build_release_bridge.py --output-dir build/bridges/std`, the same with `--four-arms` into `.../fa`, and with `--four-arms --vilgax --ben-upgrades` into `.../vx`.
5. **Test app:** `python tools/stage_test_app.py --native build/native-sse41 --frontend build/launcher --bridges build/bridges --support <earlier staged release folder> --output <new folder>`. It stages the runtime, launcher, bridges, importer scripts and `bundled-assets/`. The support folder supplies the Visual C++ runtime DLLs, the embedded Python and the licenses, which are not built here.
6. **Bundled content:** `tools/stage_bundled_assets.py` refreshes `bundled-assets/` from a finished installation; details in `docs/BUNDLED_ASSETS.md`. Upgrade, Cannonbolt, Way Big and Photo Mode documents: `docs/UPGRADES.md`, `docs/CANNONBOLT.md`, `docs/ULTIMATE_CANNONBOLT.md`, `docs/ULTIMATE_WAY_BIG.md`, `docs/PHOTO_MODE.md`, `docs/GAMEPLAY_TWEAKS.md`, `docs/BEN_ULTIMATRIX.md`.

Verification status is in `TESTING.md`; a successful build does not prove gameplay.
