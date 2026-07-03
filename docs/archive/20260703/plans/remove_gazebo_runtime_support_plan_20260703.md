# Remove Gazebo Runtime Support Plan

Date: 2026-07-03

## Goal

Clean the current vision runtime surface so it targets the real chassis/runtime
chain only, without a Gazebo or simulated-time branch.

## Scope

- Remove `use_sim_time` handling from the Bun vision runtime launcher.
- Remove the `use_sim_time` launch argument from the vision runtime ROS launch
  file.
- Update current operator/runtime/status documentation so validation and timing
  language refers to the real chassis/runtime chain.
- Leave historical archive documents and project-level AGENTS constraints as
  history/guardrails.

## Verification

- Run TypeScript launcher help to confirm the removed option is gone.
- Compile the Python vision runtime package.
- Run the vision runtime unit tests.
- Check the active source/current docs no longer expose Gazebo/sim-time runtime
  support.
