# Vision Runtime Wording Result

Date: 2026-07-03

## Summary

Changed the user-facing runtime wording to `vision runtime`.

The compatibility identifiers remain unchanged:

- ROS package: `tennisbot_headless_vision`
- executable: `headless_vision_node`
- launch file: `headless_vision.launch.py`
- Bun entrypoint: `scripts/headless.ts`

## Changes

- Renamed the current runtime target document:
  - from `docs/current/headless_ros_vision_runtime.md`
  - to `docs/current/vision_runtime.md`
- Updated current docs to use `vision runtime` / `视觉运行时` in prose.
- Updated Bun launcher help text to say `vision runtime`.
- Changed default runtime log root from `runs/headless` to
  `runs/vision-runtime`.
- Updated runtime log labels:
  - default auto session prefix: `vision_runtime_...`
  - schema: `tennisbot.vision_runtime_log.v1`
  - ready event: `vision_runtime_ready`

## Verification

Commands run:

```bash
git diff --check
python3 -m compileall -q src/tennisbot_headless_vision
PYTHONPATH=src/tennisbot_headless_vision python3 -m unittest discover -s src/tennisbot_headless_vision/tests -v
bun scripts/headless.ts --help
```

Results:

- `git diff --check`: passed.
- Python compileall: passed.
- Python unittest: 5 tests passed.
- Bun launcher help: passed and now uses `vision runtime` wording.
