# GitHub Actions build status

This work starts from upstream commit
`a99e9ea` (15 FPS cadence and guest-vblank diagnostics). Original upstream history
and licenses remain intact. The initial work branch does not overwrite the
owner's existing default branch.

## Available workflow

`Windows launcher and diagnostic bridge` builds the standalone frontend and
the explicit `--hero-time --gpu-diagnostics` bridge on Windows. It uses the
recorded UI/SDK revisions and only the SDK's SDL source for the frontend;
it does not build the SDK runtime or run code generation. It runs synthetic
ISO, save-reset, profile-selector, staging and Hero Time reference checks.

The downloadable artifact is deliberately named **NOT-PLAYABLE**. It contains
launcher components, not an installer or a complete game. It must not be used
to replace files in an existing installation. No automatic Release is created
from an incomplete runtime. Actions compilation does not validate gameplay.

## Blocking a complete playable release

The public repository omits original game data and generated game C++.
The contributor flow needs the owner's supported `originals/default.xex`,
post-codegen integration, and the pinned patched SDK before it can build
`ben10.exe` and matching runtime DLLs. Importing an ISO through the player
launcher happens later and cannot supply inputs to a prior cloud build.

Do not commit/upload an ISO, XEX, generated title C++, saves or caches to this
public repository. Do not manufacture an API marker or borrow individual DLLs.
The complete cloud-build input arrangement must be resolved before enabling
playable Release packaging. Existing `build_development.ps1`,
`stage_development.py` and `build_portable_distribution.py` remain the authored
build/staging/package path once prerequisites are available.

## Performance evidence

Prepare imports assets. It does not reproduce slow gameplay. Once a complete
diagnostic runtime is available, follow `CADENCE_DIAGNOSTICS.md`: matched
720p/windowed gameplay intervals at 30 and Unlimited, then preserve the three
startup/runtime logs and GPU/CPU/cadence/vblank JSONL files before relaunch.
No performance improvement is claimed by this CI setup.
