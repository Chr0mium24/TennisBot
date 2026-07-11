# Scripts UV Migration Result

Date: 2026-07-12

## Summary

Repository-root operator launchers now run through Python scripts with `uv run
scripts/*.py`. Bun remains in use for TypeScript packages and the stereo replay
frontend internals.

## Migrated Entrypoints

- `uv run scripts/yolo.py ...`
- `uv run scripts/calib.py ...`
- `uv run scripts/stereo.py ...`
- `uv run scripts/vision-runtime.py ...`
- `uv run scripts/check-chassis-position.py ...`

The old root TypeScript launcher files were removed:

- `scripts/yolo.ts`
- `scripts/calib.ts`
- `scripts/stereo.ts`
- `scripts/vision-runtime.ts`
- `scripts/check-chassis-position.ts`
- `scripts/camera-controls.ts`

## Verification

Commands completed successfully:

```bash
uv run python -m py_compile scripts/*.py
uv run scripts/yolo.py --help
uv run scripts/stereo.py --help
uv run scripts/calib.py --help
uv run scripts/vision-runtime.py --help
uv run scripts/check-chassis-position.py --help
uv run scripts/calib.py mono cam1 --dry-run
uv run scripts/calib.py stereo --dry-run
uv run scripts/stereo.py gui --dry-run
uv run scripts/vision-runtime.py run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
uv run scripts/vision-runtime.py task --task-id 42 --dry-run --no-manager --no-auto-source
uv run scripts/stereo.py replay --help
uv run scripts/yolo.py benchmark tiles --dry-run
```

Project tests completed successfully:

```bash
cd tools/yolo && uv run pytest
cd tools/calibration && uv run pytest
cd tools/stereo && uv run pytest
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
cd tools/stereo/web/replay && bun test && bun run typecheck && bun run build
```

## Notes

- `uv run scripts/yolo.py benchmark tiles --dry-run` printed an onnxruntime GPU
  device discovery warning, but the command exited successfully and produced the
  expected dry-run table.
- `uv run scripts/stereo.py replay --help` still invokes the Bun replay server
  help path because the replay frontend remains TypeScript/Bun.
- No ROS/Gazebo closed-loop catch validation was performed; this migration only
  changes root launcher implementation and documentation.
