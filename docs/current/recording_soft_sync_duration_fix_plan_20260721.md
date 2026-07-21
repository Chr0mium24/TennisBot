# Recording Soft-Sync Duration Fix Plan

## Problem

Headless stereo recording with soft synchronization and `--duration` creates
634-byte MKV headers containing zero frames. FFmpeg opens each V4L2 stream, but
the absolute input timestamps used by `-copyts -timestamps abs` are already far
greater than a relative `-t 30` or `-t 150` duration before the output timestamp
offset is applied.

## Plan

1. Do not pass relative `-t` to FFmpeg when dual recording uses absolute
   soft-sync timestamps.
2. Preserve the requested duration in the recording plan and enforce it with a
   Python monotonic-clock deadline for parallel, single-process, and preview
   execution paths.
3. Keep FFmpeg's existing `-t` behavior when soft sync is disabled.
4. Add command-construction regression tests and run the recording test suite
   with uv.
