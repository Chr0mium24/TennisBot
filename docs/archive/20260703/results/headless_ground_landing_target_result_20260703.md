# Headless Ground Landing Target Result

Date: 2026-07-03

## Summary

- Changed the headless vision default target plane from catch height to ground
  landing:

```text
target_plane_z = 0.0
```

- Updated `TargetPrediction` and `RawTarget` comments to describe a configured
  target plane instead of a fixed catching plane.
- Updated current runtime docs to describe ground landing as the active default.

## Notes

The algorithm still runs in the field/interface coordinate frame. If the
chassis planner later expects a racket/catch height, override
`target_plane_z` in `headless_vision.yaml` instead of converting only at the
output topic.
