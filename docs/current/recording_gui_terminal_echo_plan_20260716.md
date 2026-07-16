# Recording GUI Terminal Echo Plan

Date: 2026-07-16

## Goal

Prevent ffmpeg processes started by the recording GUI from consuming terminal
input or leaving terminal echo disabled after the window closes.

## Plan

1. Start every GUI-owned ffmpeg process with `stdin=subprocess.DEVNULL`.
2. Preserve the existing stdout and stderr routing for preview and recording.
3. Add a regression test for the shared non-interactive process launcher.
4. Run the recording test suite with `uv`.

