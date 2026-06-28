# Multi-Agent Refactor Wave 8 Live3D USB Camera Plan

Date: 2026-06-29

## Objective

Move `apps/live3d` from camera placeholders to real browser USB camera input:

```text
browser mediaDevices -> left/right MediaStream -> two live video panels
```

This wave must not add YOLO inference yet. It should create the runtime camera
surface that the next wave can feed into a YOLO adapter.

## Branch

```text
refactor/live3d-usb-camera
```

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/live3d-usb-camera`
- Write scope:
  - `apps/live3d/**`
  - `docs/**`
- Read-only reference:
  - `apps/live3d/src/main.ts`
  - `apps/live3d/src/config.ts`
  - `apps/live3d/src/artifacts.ts`
  - `apps/live3d/src/fixtures.ts`
- Do not edit:
  - `packages/**`
  - `tools/**`
  - lab submodules
  - `.gitmodules`

## Required Implementation

Add an app-local camera adapter under `apps/live3d/src`, for example:

```text
apps/live3d/src/cameras.ts
```

The adapter should:

- define `CameraRuntimeStatus` for left/right cameras;
- support `navigator.mediaDevices.enumerateDevices()`;
- support `navigator.mediaDevices.getUserMedia()` for two camera streams;
- use browser-facing camera config fields, such as:
  - optional `deviceId`;
  - optional label match text;
  - desired width/height/fps;
- return explicit status objects for:
  - unsupported browser media APIs;
  - permission denied;
  - missing second camera;
  - left/right stream opened;
- avoid throwing for ordinary runtime failures.

Update the UI to:

- render real `<video>` elements for left and right camera panels;
- attach streams when camera startup succeeds;
- keep the fixture detection overlays and fixture 3D scene clearly labelled as
  non-validation placeholders until YOLO inference is added;
- show camera runtime status in the status panel.

The app should still build and render without camera permissions or hardware.
In that case it should show blocked camera status and continue showing fixture
scene/artifact status.

## Tests

Add focused Bun tests for:

- media API unsupported returns blocked status;
- one available camera returns blocked status for stereo runtime;
- two available cameras request two streams with expected constraints;
- permission/getUserMedia failure returns blocked status;
- UI helper for attaching streams can be tested without real devices.

If direct DOM/video attachment is awkward in Bun, keep the DOM-facing function
small and test the stream-selection/runtime planner separately.

## Required Verification

The worker must run:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
cd ../..
git diff --check
git diff --name-only main..HEAD
```

## Acceptance Criteria

- Live3D has a browser camera runtime adapter.
- The default app can attempt to open two USB camera streams.
- Missing hardware or permissions produce visible blocked status.
- Fixture scene remains clearly non-validating.
- No YOLO inference is introduced in this wave.
- No edits occur outside `apps/live3d/**` and `docs/**`.
- Existing `TennisBallDetectorLab` dirty state remains untouched.

## Lead Review Notes

The lead should check:

- no Node-only APIs are imported into browser code;
- browser failures are reported as status, not uncaught errors;
- camera stream attachment is separated from artifact loading;
- the UI does not imply YOLO detections are real yet;
- tests do not require physical cameras.
