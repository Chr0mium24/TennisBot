# Stereo candidate diagnostics result

## Context

Live runtime logs showed YOLO detections in both camera frames, but every
candidate pair was rejected by the epipolar gate and `selected_match` stayed
`null`. The previous diagnostics only reported rejection counts, not the actual
per-pair errors.

## Change

- `StereoBallMatcher` now records per-candidate diagnostics for every evaluated
  left/right detection pair.
- Runtime `detections.ndjson` now includes `diagnostics.candidates` with:
  - left/right detection indexes and image centers;
  - rectified left/right points;
  - `epipolar_error_px`;
  - `disparity_px`;
  - confidence values;
  - rejection reason;
  - `selected` for the winning pair when a match succeeds;
  - 3D point, depth, reprojection error, and cost when triangulation reaches
    those stages.
- The stereo tool recording path writes the same diagnostics payload.

## Verification

- `uv run --project tools/stereo pytest tools/stereo/tests`
  - Result: `5 passed`
- `uv run -- python -m compileall -q src/tennisbot_vision_runtime tools/stereo/src`
  - Result: passed with no output.
