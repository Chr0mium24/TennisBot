# YOLO CPU/CUDA Dependency Cleanup Result

## Outcome

YOLO inference now defaults to the official CPU-only PyTorch wheels on every
supported operating system. NVIDIA CUDA packages are selected only through the
explicit, mutually exclusive `detect-cuda` extra.

Root commands preserve their existing CPU invocation and accept `--cuda` when
CUDA 13.0 is intentionally requested:

```bash
uv run scripts/yolo.py detect-video input.mkv --tile
uv run scripts/yolo.py detect-video input.mkv --cuda --device 0 --tile
uv run scripts/test.py triangulation stereo
uv run scripts/test.py triangulation stereo --cuda
```

## Dependency Audit

- `tools/yolo` CPU export selects `torch==2.13.0+cpu` and
  `torchvision==0.28.0+cpu` on non-macOS systems.
- `packages/vision-python` CPU export selects the same CPU builds.
- Neither CPU export contains CUDA runtime, cuDNN, cuBLAS, cuFFT, NCCL, or
  related NVIDIA compute wheels.
- The CUDA export selects `torch==2.13.0+cu130`,
  `torchvision==0.28.0+cu130`, and the expected CUDA runtime dependencies.
- Ultralytics still includes the small, platform-independent `nvidia-ml-py`
  hardware-query package; it is not a CUDA runtime.

## Verification

- `uv lock --project tools/yolo`: passed.
- `uv lock --project packages/vision-python`: passed.
- CPU/CUDA `uv export` dependency assertions: passed.
- `tools/yolo`: `python -m pytest -q` with `augment + detect`: passed.
- `packages/vision-python`: `python -m pytest -q` with `test`: passed.
- Python compile check for both root wrappers: passed.
- CUDA wrapper routing for YOLO video and stereo triangulation dry-runs:
  passed; `--cuda` is consumed by the wrapper and not forwarded to the
  application CLI.

The initial broad pytest attempt was discarded because running from the
repository root collected unrelated projects. A subsequent base-only YOLO run
also correctly exposed that several existing tests require the declared
`augment` and `detect` extras; the final scoped runs used the required extras.
