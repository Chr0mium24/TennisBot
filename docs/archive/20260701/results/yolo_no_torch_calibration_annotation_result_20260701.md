# YOLO No-Torch Calibration/Annotation Result 2026-07-01

## Summary

Calibration and the YOLO annotation/model-package paths are documented as
Torch/CUDA-free default `uv` environments. `detect-gui` remains the explicit
optional path that uses `uv run --extra detect ...` and can install
Ultralytics, Torch, and CUDA/NVIDIA Python packages.

## Files Updated

- `README.md`
- `tools/calibration/README.md`
- `tools/yolo/README.md`
- `docs/current/command_usage.md`
- `docs/current/architecture.md`

## Verification

### YOLO default environment

Command used an isolated environment:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-yolo-no-detect-venv uv sync --no-dev --frozen
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-yolo-no-detect-venv uv run --no-sync python -c '...'
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-yolo-no-detect-venv uv run --no-sync tennisbot-yolo annotate --help
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-yolo-no-detect-venv uv run --no-sync tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Observed package install set:

```text
annotated-doc
annotated-types
anyio
click
fastapi
h11
idna
pydantic
pydantic-core
starlette
tennisbot-yolo
typing-extensions
typing-inspection
uvicorn
```

Import probe:

```text
torch=False ultralytics=False cuda_bindings=False nvidia=False
```

CLI checks:

```text
tennisbot-yolo annotate --help: passed
tennisbot-yolo package verify: verified=/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo
```

### Calibration default environment

Command used an isolated environment:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-calibration-no-torch-venv uv sync --no-dev --frozen
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-calibration-no-torch-venv uv run --no-sync python -c '...'
UV_PROJECT_ENVIRONMENT=/tmp/tennisbot-calibration-no-torch-venv uv run --no-sync camera-calib-lab --help
```

Observed package install set:

```text
numpy
opencv-python
pyyaml
tennisbot-calibration
```

Import probe:

```text
torch=False ultralytics=False cuda_bindings=False nvidia=False
```

CLI check:

```text
camera-calib-lab --help: passed
```
