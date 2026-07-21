# Recording Soft-Sync Duration Fix Result

## Outcome

Headless stereo recording no longer passes a relative FFmpeg `-t` duration
when `-copyts -timestamps abs` soft synchronization is active. The requested
duration remains on the recording plan and is enforced by a Python monotonic
deadline for parallel, single-process, and preview execution paths. At the
deadline, the supervisor sends `SIGINT`, allowing FFmpeg to finalize each MKV.

Non-soft-sync recording keeps the original FFmpeg `-t` behavior.

## Regression Coverage

- A soft-sync dual plan with `duration=10` contains no `-t 10` in either FFmpeg
  command and retains `plan.duration == 10`.
- A non-soft-sync plan with `duration=30` retains `-t 30`.
- The foreground supervisor test verifies that a duration timeout sends
  `SIGINT` and reports a successful intentional stop.

## Verification

- `cd tools/recording && uv run python -m pytest -q`: `12 passed`.
- `uv run python -m compileall -q src tests`: passed.
- `uv run scripts/record.py stereo --duration 30 --dry-run`: passed; both
  soft-sync FFmpeg commands contain absolute timestamp normalization and no
  relative `-t` option.

Hardware recording was not run on this macOS workspace because `/dev/video0`
and `/dev/video2` are available only on the target Linux host. The target-side
acceptance check is to record a short session and confirm both MKVs contain
frames and valid trailers with `ffprobe`.
