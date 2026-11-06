# Performance Improvement — Alpha 5 candidate

Community contribution based on upstream `a99e9ea`. This document records local
evidence; it is not an official upstream release announcement. No downloadable
Alpha 5 installer has been published by this contribution yet.

## Problem and attribution

An affected scene ran at approximately 15 game FPS on an NVIDIA GeForce RTX
4060 Laptop GPU, at 1280x720/windowed with a 30 FPS cap. Earlier telemetry showed
about 53 ms/frame of graphics-worker CPU wall time and about 16 ms/frame of guest
GPU command time. The NVIDIA adapter was selected correctly.

Additional shared-memory instrumentation located the dominant cost in
`ben10_profile::UploadAudit::Observe`, called from
`D3D12SharedMemory::UploadRanges`:

- Observe: approximately 49–54 ms/frame in the slow capture.
- Observe accounted for 97.7% of RequestRanges wall time in the final 12 slow
  reporting windows; memcpy accounted for 0.57%, and page-scan lock acquisition
  for 0.10%.
- This identifies the expensive function, not its exact internal map,
  comparison, cache-maintenance or mutex cost. Timing scopes overlap and must
  not be summed.

## Candidate change

The diagnostic-only `measure-no-reuse` profile removes both
`BEN10_REUSE_UPLOADS` and `BEN10_UPLOAD_AUDIT` from the game's child environment.
The existing full-upload path is used without its shadow observer. Environment
variables must be removed: setting them to `0` still enables presence-based
`getenv` checks.

No guest logic, resolution, geometry, effects or frame limiter is changed.
Existing All Aliens, Hero Time, menus and save handling remain in the sources.
The ordinary shipping bridge and default diagnostic profile are unchanged.

For this comparison, only the bridge was rebuilt. The game EXE, runtime DLL,
GPU DLL and launcher remained byte-identical to the preceding instrumented
reference. The optional instrumentation itself had earlier required a GPU
plugin rebuild, without changing SDK class layouts or exports.

## Observed result and limits

The user reported recovery to 30 FPS, then smooth operation at the selected
60 FPS limit in the affected area. The latest six telemetry windows recorded
59.97–60.03 game FPS; cadence rows confirmed the 60 FPS cap. Graphics-worker CPU
wall time in those samples was approximately 3–5.4 ms/frame, and the measured
reuse-comparison subtotal was zero. Both test sessions exited with code 0.

This is scene-level evidence, not a controlled input replay. Baseline and
follow-up caps differed, so the observed 15-to-60 change is not presented as a
controlled 300% optimization benchmark. Full campaign stability, all GPUs,
comprehensive visual correctness and the known above-30-FPS flicker remain
unverified. Diagnostic overhead is present on both sides.

## Reproducing the comparison

Follow the contributor runbook with SDK
`c94f5ebdcb3c9d1a460ca48e04f9758448f8d518` and the consolidated SDK patch.
Build the diagnostic bridge explicitly:

```powershell
python tools/build_release_bridge.py --hero-time --gpu-diagnostics
```

Use that matching bridge with a coherently staged build. In the selected data
root's `graphics-diagnostic-profile.txt`, select `measure-phases` for the
reference or `measure-no-reuse` for the candidate, before starting the game.
The ordinary bridge does not read these diagnostic profiles.

Compare the same scene, camera, resolution and frame cap. Preserve logs before
relaunch. Check image quality, gameplay, GPU time and frame-time distributions,
not FPS alone. Restore `measure-phases` to restore the reference behavior.

## Local checks and publication status

- Pinned SDK and consumer compiled locally after the documented Windows build
  fixes; the native consumer linked successfully with SSE4.1 enabled.
- Generated-function location tests and integration idempotence checks passed.
- Native nearest-even rounding passed 48 synthetic lane cases.
- Shared-memory collector disabled/enabled, accounting and JSON checks passed.
- Profile isolation, full-upload selection and retained telemetry checks passed.

These checks do not establish universal clean-machine reproduction. Original
assets, generated title C++, saves, caches, raw personal logs and machine paths
are excluded from Git. Public installer packaging, source/license completeness
and installer verification remain separate work. GitHub Actions is unavailable
for the account at the time of these local tests.
