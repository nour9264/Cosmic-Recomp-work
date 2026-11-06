# Shared-memory request attribution

This diagnostic follows the recorded 15 FPS scene. It changes no memory
validation rules, upload contents, draw commands, guest timing or frame limiter.
The GPU plugin includes additional timers; host EXE, runtime and bridge can stay
byte-identical because no SDK class layout or exported interface changes.

## Collection

Use the complete locally staged `development-app-shared-audit` directory.
It selects the existing disposable playtest installation. Do not replace files
in another installation or run two game instances against the same data root.
The `measure-phases` bridge already sets `BEN10_CPU_DRAW_PHASES`, which activates
the new collector and places `shared-memory-*.jsonl` beside the existing logs.
`BEN10_SHARED_MEMORY_AUDIT` can explicitly select a path for synthetic checks.
With both variables absent, the collector does not take timestamps or write.

At 720p/windowed, record the same stationary slow scene for 30 seconds at cap 30,
then 30 seconds at Unlimited. Exit normally and preserve all logs before restart.
The earlier recording contained no observed Unlimited frames.

## Interpretation

`request_phase_wall_ms` partitions RequestRanges into validation/merging, sparse
allocation, scan setup, lock acquisition, page scanning, finishing and uploads.
`upload_subtotal_wall_ms` splits uploads into upload-buffer requests, marking
valid memory, memcpy, reuse comparisons, copy preparation and command recording.
Upload subtotals overlap the request upload phase and must not be added to it.
These also overlap the older CPU draw-phase measurements.

Counters report requested ranges/bytes, scanned blocks, queued upload ranges,
uploaded bytes, requests requiring no upload, failures and thread cycles.
Thread cycles are not milliseconds; no clock-frequency conversion is assumed.
Wall times include scheduling and driver calls. Timers and cycle queries have
overhead, so the instrumented build is for attribution, not a clean FPS benchmark.

## Local validation

Synthetic checks cover disabled collection, count/failure accounting, sequential
phase sums, JSON flushing/reset and automatic activation through the existing
CPU-phase variable. The GPU target rebuilt from two translation units and linked.
Gameplay collection remains pending user testing. No performance gain is claimed.
