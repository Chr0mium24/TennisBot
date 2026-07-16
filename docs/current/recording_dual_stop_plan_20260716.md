# Recording Dual Stop Plan

Date: 2026-07-16

## Goal

Make `recording.py dual` stop both ffmpeg capture processes promptly when the
operator enters `q` or presses Ctrl+C.

## Plan

1. Signal all active capture processes before waiting for any one process.
2. Use one timeout budget per shutdown phase instead of one timeout per camera.
3. Escalate all remaining processes together from SIGINT to terminate to kill.
4. Add a regression test for signal-before-wait ordering and run tests with
   `uv`.

