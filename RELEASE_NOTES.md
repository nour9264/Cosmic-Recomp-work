# Cosmic Recomp Alpha 8.1

- Toggle **Play as Albedo** in the final fight and resume to swap Way Big appearances. Green beams follow Ben and red beams follow Evil Way Big.
- Ben’s boss portrait now shows the Potis Altiare badge in sharper detail. The boss health bar remains yellow.
- Restored the tested Alpha 8 graphics profile and fixed final-fight pause behavior, button prompts, and enhanced cinematic subtitle matching.

The local test build was confirmed in-game. Installer testing is pending.

# Cosmic Recomp Alpha 0.4.0-alpha.4 — stability and accumulated optimizations

This is an **Alpha update**, not a completed port. Bring your own supported Xbox
360 copy. The importer prepares local game data and uses the bundled native
runtime; it does not compile C++ on the player's machine.

## Changes

- Increased the DB File Heap from 64 to **96 MiB** for the additional form resources.
  Both callback record tables and their auxiliary queues now hold **64 entries**
  in appended storage. Existing object fields retain their offsets. These changes
  address missing Vreedle weapons/effects and the crash at the battle-to-story
  transition with All Aliens and Hero Time enabled. The encounter was manually
  retested successfully; this is not full-campaign certification.
- **Hero Time:** the normal-to-Ultimate request now uses the original green
  transformation effect. Ultimate time remains 60 seconds. Returning early
  preserves the corresponding meter fraction; recharge is **time used / 3**, up
  to **20 seconds** as Ben. For example, 30 seconds used means 10 seconds recharge.
  The user confirmed the effect, early return and proportional meter behavior.
- Accumulated native-quality performance work: source-pitch specialization in
  eligible depth resolves, guarded RGBA8 resolve copies into existing compatible
  textures, and bounded CPU PAUSE hints while GPU progress remains unchanged.
  Unsupported transfer layouts retain the original SDK path. Polling keeps all
  guest checks and deadlines; it does not change game speed or impose a frame cap.
- The FPS overlay also reports process RAM and DXGI GPU-memory usage. GPU shared
  memory on integrated graphics is not additional dedicated VRAM.
- Updated window title, complete corresponding SDK sources, one consolidated SDK
  diff, and authored post-codegen integration recipes. No original game code or
  assets are included.

## Performance and limitations

The eight-hint polling candidate measured **39.919 vs 38.940 game FPS (+2.52%)**
against a stored reference in one fixed native-720p Paris scene. The same private
camera instrumentation was present on both sides. P95 changed from 34.821 to
34.908 ms; P99 from 44.096 to 35.563 ms. This is a scoped development observation,
**not a release-to-release guarantee** or proof of stable 60 FPS. Private camera
experiments are excluded from this release.

**30 FPS remains the default. Camera/scenery flicker above 30 FPS is still open.**
Ultimate Big Chill's wing transparency and Rath upgrades with All Aliens disabled
also remain open. No frame generation, FSR, new mouse wheel UI or private test
room is shipped. Existing controls, original-game video menus, save support and
the separate launcher remain available. Back up your user folder before updating.

Validation separates automated recipe/VM/installer checks from manual encounter
and Hero Time feedback. See VALIDATION.json and docs/ALPHA4.md. A clean-machine
rebuild of the entire SDK and consumer has not been verified.
