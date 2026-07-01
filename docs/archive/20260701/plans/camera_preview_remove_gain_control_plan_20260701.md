# Camera Preview Remove Gain Control Plan

## Goal

Remove the gain control from camera preview UI and help text because hardware
experiments showed it does not materially affect these cameras.

## Scope

1. Remove preview `--gain` CLI parsing.
2. Remove gain trackbars and overlay text from the OpenCV preview window.
3. Remove gain from preview dry-run payloads.
4. Update focused preview tests.
5. Verify with calibration tests and Bun script checks.
