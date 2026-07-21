# Camera Judgement And Calibration Plan

Date: 2026-06-30

## Goal

Establish the current physical camera flow for TennisBot:

1. Identify which USB device is which physical camera.
2. Confirm both cameras are usable before calibration.
3. Capture DFOptix ChArUco mono and stereo sessions.
4. Produce or import a runtime stereo calibration package.
5. Verify Live3D with real camera frames and a visible tennis ball.

This plan does not claim a real receiving closed loop. Per project rules, true
receiving-loop validation still requires the real ROS/chassis backend pose and control
chain.

## Current Constraints

- Main camera devices are expected to be `/dev/video0` and `/dev/video2`, but
  USB ordering can change after reconnecting.
- `tools/calibration` is the current mainline capture entry and uses `uv`.
- The capture GUI writes ChArUco frame sessions and `manifest.json`.
- Fresh mono/stereo solve and runtime package export are not fully mainlined in
  `tools/calibration` yet.
- Final physical calibration should use the fixed physical DFOptix ChArUco
  board, not an ordinary paper print.
- The existing runtime package at `artifacts/calibration/stereo_cam1_cam2` is
  accepted but has a runtime quality warning: `epipolar_rms_px=4.330`, above the
  `2.000` review threshold.
- Stereo calibration is invalidated if either camera is moved, refocused, zoomed,
  or remounted after capture.

## Phase 1: Preflight

Run from the repository root:

```bash
mkdir -p docs/archive/20260630/probes
bun scripts/operator-preflight.ts \
  --output docs/archive/20260630/probes/local_runtime_preflight_20260630.md
```

Expected checks:

- Live3D surface is reachable.
- YOLO package verifies.
- Stereo calibration package exists.
- At least two USB V4L2 capture devices are present.

If this fails at USB camera devices, fix cabling, permissions, or device
selection before calibration.

## Phase 2: Camera Judgement

First list the detected camera order by brightness:

```bash
bun scripts/check-camera-brightness.ts
```

If the automatic order is unclear, explicitly test the expected devices:

```bash
bun scripts/check-camera-brightness.ts --devices /dev/video0,/dev/video2
```

To identify left and right:

1. Cover the physically left camera lens.
2. Run the brightness check.
3. The darker device is the left camera.
4. Uncover it, cover the physically right camera, and repeat.
5. Record the final mapping in the experiment report.

Usability judgement:

- Both devices must return a frame.
- Brightness should not be near black or saturated white under calibration
  lighting.
- Device order must be stable for the whole capture session.
- If exposure or gain is poor, prepare UVC controls in the calibration preview
  before opening Live3D.

## Phase 3: Physical Target Board Check

Use the fixed physical DFOptix ChArUco target that matches the tool
configuration:

- `DICT_5X5_100`
- `14 x 9` squares
- `15 mm` square
- `11.25 mm` marker

Before capture:

- Confirm the board is the physical DFOptix target for this project.
- Confirm the board is flat, clean, and not warped.
- Confirm the configured dimensions still match the physical board:
  `square_size_m=0.015` and `marker_size_m=0.01125`.
- Record the board source or measurement note in the experiment report.

The tracked generated target files under `artifacts/calibration_targets/` are
reference artifacts. A normal paper print is only acceptable for software
pipeline smoke tests. It should not be used for final camera calibration because
printer scaling, paper stretch, and surface warping directly corrupt the 3D
scale and stereo baseline.

## Phase 4: Capture Mono Sessions

Use fixed camera mounting and the same lens/focus settings intended for runtime.
Move the target, not the cameras.

```bash
cd tools/calibration
uv sync

uv run camera-calib-lab capture charuco-auto-gui \
  --device /dev/video0 \
  --output captures/local/20260630_cam1_charuco

uv run camera-calib-lab capture charuco-auto-gui \
  --device /dev/video2 \
  --output captures/local/20260630_cam2_charuco
```

GUI controls:

- `space`: manually save a qualified frame.
- `c`: finish and mark calibration requested.
- `q` or `Esc`: quit.

Capture requirements:

- Aim for at least `30` accepted views per camera.
- Cover center, corners, near, far, tilted, and rotated target poses.
- Avoid motion blur and reflections.
- The preview should show at least `24` ChArUco corners.
- Sharpness should pass the configured threshold, currently `30.0`.

## Phase 5: Capture Stereo Session

After the mono captures, keep both cameras fixed and capture synchronized stereo
pairs:

```bash
cd tools/calibration
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output captures/local/20260630_stereo_charuco
```

Capture requirements:

- Aim for at least `30` accepted stereo pairs.
- The target must be visible and accepted in both camera views at the same time.
- Include depth variation, horizontal/vertical movement, and tilted board poses.
- Avoid using nearly identical poses; they weaken stereo extrinsics.

## Phase 6: Solve Or Import Runtime Package

Target runtime path:

```text
artifacts/calibration/stereo_cam1_cam2
```

The package must include:

- `cam1.json`
- `cam2.json`
- `stereo.json`
- `rectification.json`
- `verification.json`
- `summary.md`

Acceptance targets:

- Mono RMS reprojection error: preferably `<= 1.0 px`.
- Stereo RMS reprojection error: preferably `<= 2.0 px`.
- Epipolar RMS: target `<= 2.0 px`.
- Rectification Y p95: target `<= 2.0 px`.
- Baseline must be positive and physically plausible.
- `dry_run` must be `false`.
- `hardware_validated` must be `true`.

Because fresh solve/export is not fully mainlined in `tools/calibration`, use
the current import path only if it produces the runtime artifact contract above.
Do not treat the existing package as final if the camera rig has changed.

## Phase 7: Live3D Hardware Evidence

Start the local runtime from the repository root:

```bash
bun scripts/start-local-runtime.ts
```

Then open Live3D with a visible tennis ball in both camera views and watch the
readiness gates.

The hardware evidence is complete only when the report reaches
`prediction-ready`.

## Result Report Template

Save experiment results under `docs/archive/20260630/calibration/` with:

- final left/right device mapping;
- brightness check output;
- physical target board source and dimension note;
- mono capture paths and accepted view counts;
- stereo capture path and accepted pair count;
- solve/import package path;
- quality metrics;
- Live3D verifier report path;
- blockers and next action.

## Decision

Proceed in this order:

1. Preflight.
2. Brightness/device mapping.
3. Physical target board check.
4. Mono captures.
5. Stereo capture.
6. Solve/import package.
7. Live3D visible-ball runtime check.

Do not move the cameras between steps 4 and 7.
