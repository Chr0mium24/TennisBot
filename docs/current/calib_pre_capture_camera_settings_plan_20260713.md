# Calibration pre-capture camera settings plan

## Goal

Before every mono or stereo calibration capture GUI opens, configure each selected camera with manual exposure time 10, manual focus 600, and manual white balance at 4600 K; then print the read-back state.

## Steps

1. Add a calibration CLI preflight command that writes the ordered V4L2 controls and fails clearly if a required control cannot be applied.
2. Run the setting command before the existing control-report command in mono and stereo capture workflows.
3. Add tests, verify the result against the connected cameras, document the result, and commit with a clean worktree.
