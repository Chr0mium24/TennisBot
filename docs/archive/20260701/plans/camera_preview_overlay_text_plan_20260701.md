# Camera Preview Overlay Text Plan

## Goal

Make the green overlay text readable in 4K preview, especially when stereo
preview shows two resized panes side by side.

## Scope

1. Draw camera preview text after resizing the frame to display size.
2. Increase text size and add an outline for contrast.
3. Shorten overlay labels so the text fits inside each stereo pane.
4. Add a focused unit test for preview overlay sizing.
5. Verify with `uv` tests and `bun` script checks.
