# Current-user ROS setup default result

## Context

Running `uv run scripts/vision-runtime.py run` on user `nvidia3` failed because the
auto-source default used the hard-coded control workspace path
`/home/cr/tennis_robot_ws/install/setup.bash`.

## Change

- `scripts/vision-runtime.py` now defaults `TENNISBOT_CONTROL_SETUP` to
  `<current user home>/tennis_robot_ws/install/setup.bash`.
- `scripts/check-chassis-position.py` uses the same current-user default.
- The existing environment variable override behavior is unchanged.

## Verification

- `uv run scripts/vision-runtime.py run --dry-run --no-manager` on local user `cr`
  still resolves to `/home/cr/tennis_robot_ws/install/setup.bash`.
- `HOME=/home/nvidia3 uv run scripts/vision-runtime.py run --dry-run --no-manager`
  resolves the control setup to
  `/home/nvidia3/tennis_robot_ws/install/setup.bash`.
- `HOME=/home/nvidia3 bun -e 'import { homedir } from "node:os"; console.log(homedir())'`
  prints `/home/nvidia3`.
