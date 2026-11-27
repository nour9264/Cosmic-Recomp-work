# Interact animations (Alien Force aliens and Ultimates)

The original aliens have three interact clips (`interact_in_01`, `interact_01`, `interact_out_01`) that play when Ben presses a
lever or button. The imported Alien Force aliens and the stock Ultimates had none. They now have one, authored in Blender from the
timing of Water Hazard's clips (in 0.267 s, loop 0.7 s, out 0.467 s) and put into the game files by the bundled patches.

## What the game does (read from the code and from `Anim controller` trace lines)

- An animation set (player.ddf, 491 words, entries of 7 words) maps a **role byte** to a clip key. Every original alien uses
  `0x4a` = interact_in, `0x48` = interact_01, `0x05` = interact_out and a second idle on `0x49`. This game's sets and Vilgax
  Attacks' sets number the idle differently (Vilgax idle uses 5), so the installer moves a Vilgax idle from 5 to `0x49`.
- The game requests the roles in a fixed order with timings of its own: `5` (also asked whenever Ben stops walking), `0x48`,
  `0x49`, `0x4a`. Splitting the motion over three clips therefore did not play as drawn. The approved layout puts the whole
  sequence (about 1.4 s) in the clip on role `0x48` and makes the other two clips two-key stubs of the idle pose.
- Every original alien's three clips share one timeline (in from tick 0, loop from 1440-1600, out from about 4960, 160 ticks per
  key). The new clips use Water Hazard's offsets (0 / 1440 / 4960). Clip length is `end - begin` (sub_8219EC80).
- A bone that does not move keeps one key per channel, like the game's own clips; this keeps each package about 14 KB larger instead
  of 100 KB.

## Tools

- `tools/interact/interact_scene.py` (run inside Blender; set `COSMIC_APP` and `COSMIC_REPO`) builds the review scene (source and
  target rigs, retargeted arms: swing method for Chromastone and Cannonbolt, Chromastone-replay IK for Goop, Jetray and the Ultimates)
  and `export(path)` writes the poses as JSON.
- `tools/interact/install_interact_clips.py --installation <installation> --poses <json>` bakes the clips into the packages
  (`g_*.xbx`), adds the set entries and keeps the first original of every file in `<installation>/../interact-backup`. Close the
  game and restore every `a_s*_s.xbx` from its `.cosmic-animation-original` before the next launch (the launcher merges the new
  clips into the level banks again).
- The five Ultimates' animation sets are stock records of player.ddf. They travel in
  `vilgax/ultimatecannonbolt/player-records.bin`; the launcher replaces player.ddf records by key, so no launcher code changed.
- `tools/stage_bundled_assets.py` lists `g_ubc`, `g_uec`, `g_uhm`, `g_usf` and `g_usm` as delta files; the Alien Force packages and
  their sets are in the `vilgax/<name>` folders of the bundle.
- `tools/test_interact_clips.py` checks timeline, key compaction, reinstall and set roles on a synthetic package.

## Diagnostics

`native-rex/src/anim_trace.h` logs every clip or role the game starts (`Anim controller:` lines in `runtime.log`). It is off unless
`BEN10_ANIM_TRACE` is set or an empty `user/anim-trace.txt` exists in the installation (the launcher removes every `BEN10_*`
variable before it starts the game, so the file is the way to switch it on).

## Status and open items

- Approved by the owner in the local test build; not played from an installer build.
- The character may still be moved by the game (about 0.33 units forward and back) around the animation; this was not changed.
- A crash when transforming into Ultimate Humungousaur in one Rome level (null model lookup `F6E0FED2` in sub_821DF390, the model is
  not resident) was seen once, with the same signature as the earlier R3 swap crashes. It was not shown to come from these clips.
