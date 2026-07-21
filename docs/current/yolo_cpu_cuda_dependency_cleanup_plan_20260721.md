# YOLO CPU/CUDA Dependency Cleanup Plan

## Problem

The YOLO `detect` extra previously depended on Ultralytics without selecting a
PyTorch distribution. PyPI's Linux PyTorch wheel brings CUDA runtime packages
even when the host has no NVIDIA GPU, so a CPU-only deployment could download
several unnecessary NVIDIA packages.

## Plan

1. Keep the existing `detect` workflow as the safe default and bind its
   `torch` and `torchvision` dependencies to the official PyTorch CPU index.
2. Add a mutually exclusive `detect-cuda` extra bound to the official CUDA
   13.0 index.
3. Let the root YOLO wrapper select CUDA only when the operator passes
   `--cuda`; apply the same selection to the shared vision test wrapper and
   preserve dry-run and help commands without inference extras.
4. Regenerate both affected lockfiles with `uv`, verify both dependency branches,
   and run the focused tests.

## Expected Result

- `uv run scripts/yolo.py detect-video ...` does not install NVIDIA runtime
  wheels on a CPU-only Linux host.
- `uv run scripts/yolo.py detect-video ... --cuda --device 0` retains an
  explicit NVIDIA execution path.
