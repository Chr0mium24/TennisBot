# Recording GUI Terminal Paths Plan

Date: 2026-07-16

## Goal

Report recording output paths in the launching terminal instead of the GUI
status line.

## Plan

1. Remove full output paths from single and dual GUI recording status text.
2. Print existing saved video paths to stdout when recording stops.
3. Reuse the CLI saved-path formatter for consistent output.
4. Run the recording tests with `uv`, commit, and push.

