# Recording Control Dependency Order Plan

## Problem

Camera 2 can start with continuous autofocus enabled. Its UVC driver then marks
`focus_absolute` inactive. Sending `focus_automatic_continuous=0` and
`focus_absolute=0` in the same `VIDIOC_S_EXT_CTRLS` batch fails before the
manual focus control becomes active.

The same dependency pattern can apply to automatic exposure and automatic
white balance.

## Plan

1. Replace each recording plan's single combined control command with ordered
   command phases per camera.
2. Apply automatic-mode controls first, dependent manual exposure/white-balance/
   focus controls second, and independent image controls last.
3. Use the same phased application in headless and GUI recording paths.
4. Preserve every executed command in dry-run output and session metadata.
5. Add ordering regression tests and run the recording test suite with uv.
