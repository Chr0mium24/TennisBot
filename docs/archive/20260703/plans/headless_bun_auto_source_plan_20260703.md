# Headless Bun Auto Source Plan

Date: 2026-07-03

## Goal

Let the Bun headless launcher start ROS child processes without requiring the
operator to manually source setup files in the current terminal.

## Plan

1. Wrap generated `ros2` commands in `bash -lc`.
2. Source these setup files before each ROS child process:
   - `/opt/ros/humble/setup.bash`
   - `/home/cr/tennis_robot_ws/install/setup.bash`
   - this repository's `install/setup.bash`
3. Keep opt-out and override controls for nonstandard machines:
   - `--no-auto-source`
   - `--setup-file`
   - `--clear-setup-files`
   - `ROS_SETUP`
   - `TENNISBOT_CONTROL_SETUP`
   - `TENNISBOT_LOCAL_SETUP`
4. Update current run docs to distinguish Bun-launched ROS processes from
   manual `ros2` CLI diagnostics.

## Verification

- `bun --check scripts/headless.ts`
- `bun scripts/headless.ts --help`
- `bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun`
- `bun scripts/headless.ts run --dry-run --no-auto-source`
