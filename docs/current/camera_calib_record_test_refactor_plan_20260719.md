# Camera / Calibration / Recording / Test Refactor Plan

Date: 2026-07-19

## Goal

Reorganize the current camera-facing commands around four clear operator
surfaces:

```text
camera -> camera discovery, health checks, raw preview, and controls
calib  -> online/offline mono and stereo calibration
record -> GUI/headless mono and stereo raw video recording
test   -> GUI/headless vision diagnostics and read-only ROS communication tests
```

The refactor must remove the mixed `stereo` command surface, preserve the
capabilities that are still needed by the ROS vision runtime, and make camera
capture and recording reusable without opening the same V4L2 device from two
independent processes.

Only online `test` commands support the optional `--record` capability.

## Confirmed Product Decisions

1. Add a top-level `camera` entry with `list`, `check`, `preview`, and
   `controls` operations.
2. Keep calibration and recording as tools.
3. Calibration exposes only the online/offline and mono/stereo business
   dimensions.
4. Online calibration always uses a calibration GUI; offline calibration never
   opens a GUI or camera.
5. Mono calibration explicitly selects `cam1` or `cam2`.
6. Recording exposes only mono/stereo recording with GUI or headless operation.
7. Remove postprocessing and diagnostics from the public `record` surface.
8. Delete the public `stereo` entry after its shared algorithms and recording
   metadata are migrated.
9. Add a top-level `test` entry for YOLO, stereo triangulation, and ROS
   communication diagnostics.
10. GUI and headless test modes execute the same algorithm. Headless mode
    prints structured terminal diagnostics.
11. Only online `test` supports `--record`; `camera`, `calib`, and `record` do
    not gain this cross-command flag.
12. Trajectory and catch-point prediction are outside this refactor.

## Target CLI Contract

### Camera

```bash
uv run scripts/camera.py list
uv run scripts/camera.py check
uv run scripts/camera.py preview cam1
uv run scripts/camera.py preview cam2
uv run scripts/camera.py preview stereo
uv run scripts/camera.py controls show cam1
uv run scripts/camera.py controls show cam2
uv run scripts/camera.py controls show stereo
uv run scripts/camera.py controls apply cam1 --profile runtime
uv run scripts/camera.py controls apply stereo --profile calibration
```

Responsibilities:

- `list`: enumerate capture-capable cameras and resolve stable `cam1`/`cam2`
  identities;
- `check`: verify open/read capability, negotiated format, FPS, brightness, and
  configured controls;
- `preview`: display raw frames only, without YOLO, ChArUco capture,
  triangulation, or recording;
- `controls`: inspect or apply the canonical camera control profiles.

The existing calibration brightness command moves into `camera check`.

### Calibration

```bash
uv run scripts/calib.py online mono cam1
uv run scripts/calib.py online mono cam2
uv run scripts/calib.py online stereo

uv run scripts/calib.py offline mono cam1 --session <path>
uv run scripts/calib.py offline mono cam2 --session <path>
uv run scripts/calib.py offline stereo --session <path>
```

Semantics:

- `online mono`: apply the calibration camera profile, run the mono ChArUco
  capture GUI, save a session, solve it, and export a mono artifact;
- `online stereo`: apply the calibration profile to the configured pair, run
  the stereo ChArUco capture GUI, save a session, solve it using accepted mono
  artifacts, and export a stereo artifact;
- `offline mono`: solve a specified existing mono session without opening a
  camera or GUI;
- `offline stereo`: solve a specified existing stereo session without opening
  a camera or GUI.

The public `brightness`, generic `preview`, `--capture-only`, and `--solve-only`
surfaces are retired. Capture and solve remain internal steps of the online
workflow, while offline explicitly represents solve-only operation.

### Recording

```bash
uv run scripts/record.py mono cam1
uv run scripts/record.py mono cam2
uv run scripts/record.py stereo

uv run scripts/record.py mono cam1 --gui
uv run scripts/record.py mono cam2 --gui
uv run scripts/record.py stereo --gui
```

Semantics:

- headless is the default and must work over SSH;
- `--gui` adds raw preview and start/stop controls without changing the output
  schema or encoder path;
- mono records exactly one configured camera;
- stereo records the configured `cam1`/`cam2` pair and preserves per-frame
  timestamps and pair timing diagnostics;
- both modes use the same camera identities, profiles, session schema, and
  recording implementation.

The public record surface does not contain YOLO, triangulation, dataset frame
extraction, timestamp repair, or replay commands. Existing `extract` and
`normalize` behavior must be audited before it is moved to a separate data or
media utility, archived, or deleted.

### Test

```bash
uv run scripts/test.py yolo mono cam1
uv run scripts/test.py yolo mono cam2
uv run scripts/test.py yolo mono cam1 --gui
uv run scripts/test.py yolo stereo
uv run scripts/test.py yolo stereo --gui

uv run scripts/test.py triangulation stereo
uv run scripts/test.py triangulation stereo --gui

uv run scripts/test.py communication chassis-position
```

Online vision tests may additionally use:

```bash
uv run scripts/test.py yolo mono cam1 --record
uv run scripts/test.py yolo stereo --gui --record
uv run scripts/test.py triangulation stereo --gui --record
uv run scripts/test.py triangulation stereo --gui --record --record-overlay
```

Test semantics:

- mono YOLO validates one camera and reports detections, confidence, FPS, and
  inference latency;
- stereo YOLO validates independent detections from both cameras but does not
  triangulate;
- stereo triangulation runs YOLO, rectification, matching, and triangulation,
  then reports camera-frame `x/y/z`, disparity, epipolar error, and pair timing;
- GUI mode renders the same values over live frames;
- headless mode emits readable terminal summaries and optionally NDJSON;
- communication tests are read-only by default and must not fabricate a ball,
  raw target, chassis tracker, or catch-loop substitute.

The existing `scripts/check-chassis-position.py` behavior moves under
`test communication chassis-position`.

## `test --record` Contract

`--record` attaches a recording sink to the camera stream already owned by the
test process. It must not launch a second command that attempts to reopen the
same V4L2 device.

```text
camera source
  -> algorithm consumer
  -> GUI or terminal diagnostics
  -> optional recording sink
```

Default behavior:

- record raw input streams, not only rendered overlays;
- use the same camera IDs, controls, timestamps, encoders, stop handling, and
  session metadata as `record`;
- store test detections and triangulation diagnostics beside or by reference
  to the recording session;
- make `--record-overlay` imply `--record` and add a rendered diagnostic video;
- support `--record-session <name>` and `--record-root <path>` without
  redefining camera capture parameters.

Expected mono test session data:

```text
session.json
cam1 video
frames.ndjson
detections.ndjson
optional overlay video
```

Expected stereo triangulation test session data:

```text
session.json
left video
right video
frames.ndjson
pairs.ndjson
detections.ndjson
triangulation.ndjson
optional overlay video
```

## Shared Capability Boundaries

The CLI scripts are orchestration only. They must call reusable Python APIs
instead of importing another CLI or spawning a sibling CLI process.

### Camera capability

Owns:

- stable `cam1`/`cam2` device resolution;
- capture format negotiation;
- V4L2 control profiles and readback;
- mono and synchronized-pair frame sources;
- capture timestamps and bounded pair timing diagnostics;
- raw preview primitives.

### Recording capability

Owns:

- mono and stereo recording sinks;
- common session creation and metadata schemas;
- video encoder lifecycle and clean shutdown;
- frame and pair timestamp logs;
- optional rendered-overlay sinks.

The standalone `record` tool and `test --record` both consume this capability.

### Vision diagnostic capability

Owns reusable runtime algorithms currently buried under `tools/stereo`:

- runtime calibration artifact loading;
- YOLO inference and ROI behavior;
- stereo detection pairing;
- rectification and triangulation;
- plain-data diagnostics suitable for GUI, terminal, logging, and ROS runtime
  consumers.

This code must not live only inside the new test tool because the ROS vision
runtime also consumes it.

## Configuration Rules

Create one canonical source for:

- stable `cam1` and `cam2` identities;
- left/right ordering;
- width, height, FPS, and capture format;
- calibration, recording, runtime, and test control profiles;
- output roots and session naming defaults where appropriate.

The refactor must eliminate the current conflicts between calibration control
constants, `scripts/camera_controls.py`, and the recording YAML. In particular,
device order and focus settings must not vary by entry point.

## Migration Mapping

| Current surface | Target surface |
| --- | --- |
| `calib.py brightness` | `camera.py check` |
| `calib.py preview ...` | `camera.py preview ...` |
| calibration `camera controls` | `camera.py controls show` |
| calibration `prepare-calibration` | shared profile used by `calib online` |
| `calib.py mono ...` | `calib.py online/offline mono ...` |
| `calib.py stereo ...` | `calib.py online/offline stereo` |
| `recording.py single` | `record.py mono ...` |
| `recording.py dual` | `record.py stereo` |
| `recording.py gui ...` | `record.py ... --gui` |
| `stereo.py record` | shared stereo recorder behind `record.py stereo` |
| `stereo.py gui` | `test.py triangulation stereo --gui` |
| `stereo.py gui --record-run` | `test.py triangulation stereo --gui --record` |
| `stereo.py preview` | removed ambiguous alias |
| `stereo.py replay` | audit for test-session replay or archive |
| YOLO detect GUI | `test.py yolo ... --gui` for live diagnostics |
| `check-chassis-position.py` | `test.py communication chassis-position` |

## Physical Structure Decision Gate

Do not mechanically rename directories before extracting dependency ownership.
The implementation phase must first inventory imports from `tools/stereo`, the
ROS runtime, root scripts, and tests. It must then record a separate physical
layout decision with these constraints:

- `tools/calibration` remains an independently uv-managed Python tool;
- `tools/recording` remains an independently uv-managed Python tool;
- shared camera, recording, and stereo algorithm code has one importable owner;
- `test` is a thin diagnostic application, not the owner of runtime algorithms;
- the ROS runtime does not depend on a removed `tools/stereo` path or a manual
  `sys.path` injection;
- TypeScript/Bun packages remain isolated from Python runtime packaging unless
  an explicit cross-language boundary is designed.

Candidate physical layouts must be compared before implementation rather than
adding another ad hoc top-level directory.

## Implementation Phases

### Phase 1: Inventory and freeze contracts

1. Inventory every current camera control, device default, capture backend,
   output schema, and import from `tools/stereo`.
2. Define stable camera IDs and the canonical left/right order.
3. Freeze target CLI help text and session schemas in tests.
4. Decide the shared Python package layout and uv dependency strategy.

### Phase 2: Extract camera capability

1. Centralize device resolution and control profiles.
2. Implement mono and stereo frame-source APIs.
3. Add `camera list/check/preview/controls`.
4. Migrate calibration, recording, tests, and runtime consumers to the shared
   device configuration.

### Phase 3: Consolidate recording

1. Define one mono/stereo session schema.
2. Preserve the current ffmpeg recording quality and lifecycle handling.
3. Migrate per-frame and pair timing diagnostics from `stereo record`.
4. Implement headless and GUI modes over the same recording core.
5. Add recording sinks that can attach to an already-open test camera stream.

### Phase 4: Simplify calibration

1. Replace the current public commands with online/offline mono/stereo.
2. Keep ChArUco capture quality gates and artifact validation unchanged.
3. Make online workflows always GUI and offline workflows always headless.
4. Remove calibration-owned generic brightness, preview, and camera-control
   surfaces after camera migration is verified.

### Phase 5: Add test diagnostics

1. Add mono and stereo YOLO tests with shared GUI/headless algorithms.
2. Add stereo triangulation tests with GUI/headless presentation.
3. Add raw and optional overlay recording sinks for online test commands.
4. Move chassis-position communication checks under the test entry.
5. Keep communication tests read-only and preserve the real ROS/Gazebo backend
   boundary.

### Phase 6: Retire legacy surfaces

1. Migrate the ROS runtime away from `tools/stereo` imports.
2. Audit or relocate stereo replay, recording extraction, and timestamp
   normalization.
3. Remove `scripts/stereo.py` and the obsolete `tools/stereo` entry/package only
   after all consumers and tests have moved.
4. Remove obsolete wrappers, aliases, duplicated configuration, and docs.
5. Update current architecture, command usage, runbook, and README documents.

## Verification Plan

Each implementation phase must save a dated Markdown result document and run
the tests appropriate to the changed packages through uv or Bun.

Minimum non-hardware verification:

- CLI help and invalid-argument tests for every target command;
- camera identity and profile parsing tests;
- recording session schema and clean-shutdown tests;
- test recording sink tests using synthetic in-memory frames only at the unit
  boundary;
- calibration online command-construction and offline solve tests;
- YOLO and triangulation fixture tests;
- ROS communication command wrapping and timeout tests;
- import checks proving that the runtime no longer references `tools/stereo`.

Required physical validation:

- `camera list/check/preview/controls` against both real cameras;
- online mono calibration for `cam1` and `cam2`;
- online and offline stereo calibration using the same camera identity mapping;
- headless and GUI mono/stereo recording;
- GUI and headless mono/stereo YOLO tests;
- GUI and headless stereo triangulation tests;
- `test --record` raw video, timestamps, pair data, and optional overlay;
- read-only chassis-position communication validation against the sourced ROS
  control workspace.

No non-ROS test may be reported as validation of the real catch loop.

## Acceptance Criteria

- Operators use only `camera`, `calib`, `record`, `test`, and
  `vision-runtime` root entry points for this scope.
- All commands resolve the same stable `cam1`/`cam2` mapping and left/right
  order.
- Camera controls have one canonical configuration source.
- Online calibration always opens the ChArUco GUI and exports a package after
  successful capture; offline calibration opens no camera or GUI.
- Record GUI and headless modes share one recording implementation and output
  schema.
- Only online test commands expose `--record`.
- `test --record` does not reopen an already-owned camera device.
- Headless YOLO and triangulation tests print useful structured diagnostics.
- The ROS runtime and tests share stereo algorithms without importing a deleted
  tool path.
- The public `stereo` entry is removed only after feature and dependency parity
  is verified.
- The repository is committed and clean at the end of every implementation
  change.

## Non-Goals

- trajectory fitting, landing prediction, or catch-plane prediction CLI work;
- a local chassis tracker, predicted-landing follower, or catch-loop substitute;
- claiming real catch-loop validation without ROS/Gazebo and real backend pose;
- changing the field/interface coordinate-frame contract;
- adding `--record` to camera preview or calibration;
- retaining unrelated utilities under `record` merely for backward
  compatibility.
