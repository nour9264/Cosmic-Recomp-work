
# Architecture and validation

## From ISO to native execution

The C# launcher reads XDVDFS directly without mounting or modifying the ISO. It validates bounds, filenames, Windows device names, directory cycles, and the supported XEX hash before extraction. Assets are written to a new `import-<id>` directory, renamed to `game` only after extraction completes. Cancellation preserves an identifiable partial directory and never deletes existing saves. Partial imports are not resumed in this first implementation.

The package includes an already compiled Windows executable. Installation imports assets; static PowerPC-to-C++ generation happens during development with ReXGlue on a local game copy. Generated game source is not published.

## Frontend and game separation

The native frontend uses Dear ImGui, SDL3 and OpenGL. Its menu layout follows Full Emerald; only the reusable UI code and GIF loader are dependencies, not its game assets. An optional background GIF is decoded once and updated using one texture.

Play starts an independent C# bridge and destroys the frontend. The bridge waits for the frontend process to exit before starting the game. Therefore its window, graphics context and animation do not run during gameplay. The launcher always requires Play. Returning uses a per-launch named event; the bridge reopens the frontend.

The importer derives two menu files from the user's supported copy, keeping validated originals as backups. Original pause-menu QUIT is preserved; QUIT TO LAUNCHER has its own confirmation. VIDEO is added to original OPTIONS. Authored rows and callbacks reuse the original menu templates, stack, input handling and confirmation dialogs. Video options do not open a host popup. A selected setting resets the original completed-action state before showing its submenu again. No original bytecode is shipped.

Video preferences live in `user/pc-video.ini`. Presentation/output size and display modes update live through the existing SDK SDL window. The internal 30/60 Hz pacer updates live; Unlimited disables it. The single Show FPS preference controls both counter and frame-time graph. Borderless uses desktop dimensions and these settings do not enable internal supersampling. A 60 Hz cap is not evidence of correct 60 FPS simulation or sufficient GPU performance.

The bridge supplies its owned startup settings explicitly on the command line. This avoids dependence on the SDK's narrow TOML filename handling when the installation path contains accented characters. Relative `logs/runtime.log` is resolved from the selected installation, not the binary directory. Original assets and saves continue to use the wide portable-root override.

## CPU, GPU, and system services

Recompiled PowerPC functions execute as native host CPU code. Xbox service calls and GPU commands still need equivalent implementations; the kernel, audio, controls, and Direct3D 12 renderer come from ReXGlue. This project does not implement another kernel or renderer. Native CPU code does not make Xbox GPU commands directly executable on every PC GPU.

## Portable data

`BEN10_PORTABLE_ROOT` selects the installation. `game` contains imported original assets; `user` contains saves/profile state; `cache` contains generated caches; `logs` contains local diagnostics; `metadata` is reserved for optional local metadata. None of these personal/original-data folders belongs in a release ZIP or Git. A launcher-selected destination remains separate from application binaries.

The launcher applies retained graphics settings and the selected 30/60 FPS cap, defaulting to 30. Runtime SHA-256 checks verify copies, not authenticity; they do not prohibit intentional library modification.

## Frame counting

The overlay counts game submissions through `VdSwap`, separately from repeated host-window presentations. External counters may report repeated presentations as additional FPS. The 30 Hz playback cadence improved camera behavior in manual testing. Correct simulation/animation at 60 Hz is not established merely by seeing a higher presentation counter, and Unlimited remains an experimental diagnostic option with a known flicker/judder issue.

## Verified scope

- Supported ISO: 1,352 files and 5,435,433,670 extracted bytes.
- A full fresh import, with every path/size checked against the catalog and the XEX hash verified. A second full content-hash pass over all 5.4 GB was not performed.
- Portable native startup and XInput controller detection.
- In-game saving, process exit, restart, and Continue recovering the tested checkpoint, manually confirmed by the player.
- Nine synthetic importer tests: valid catalog, truncation, traversal, reserved device name, trailing dot, out-of-image file, a real cyclic directory-node reference, invalid closing signature, and unsupported XEX identity.

Not verified: the entire campaign, every save/checkpoint, all GPUs/drivers, a clean-machine full native build or stable 60 FPS. Original Options video integration has been exercised with automated controller replay; see TESTING.md for its exact scope.

## Animation streams and reset lifecycle

All Aliens merges the ordinary forms' resident animation clips into level stream banks. Resident channel indices are converted to inline payload offsets; physical channel-record order, duplicate records and original level clips are preserved. The C# installer and independent Python converter produce identical banks in the fixture tests. Data is derived locally from the user's copy and is never distributed.

The Gameplay input pre-handler normally consumes A to confirm the entire settings screen. Only A on the new Wipe Data row bypasses that interceptor and reaches the ordinary option callback. Original checkbox confirmation and B cancellation retain their original handler. The confirmation raises an owned reset event; the bridge waits for process exit and the installation lock before archiving this title's profile directories. No save directory is deleted.

The SDL extension is compiled inside the SDK runtime to use its existing SDL instance. It configures output size and exclusive display modes; the SDK presenter still owns resizing and presentation. No renderer/kernel replacement is introduced. The matching native-menu ABI is 7.
