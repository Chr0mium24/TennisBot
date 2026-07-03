# Target interface layer

This directory contains the shared vision-to-motion-control interface.

## Packages

- `target_msgs`: protocol-only package containing the ROS messages.
- `target_manager`: the single runtime node that consumes raw vision data.

## Topics

```text
vision node
    |
    | /target/raw      target_msgs/RawTarget, expected at 30 Hz
    v
target_manager
    |
    | /target/managed  target_msgs/ManagedTarget, at most 10 Hz
    v
state machine / trajectory planner
```

## Time convention

All nodes use the same ROS clock.

- Real system: system time (`use_sim_time=false`).
- Gazebo: `/clock` (`use_sim_time=true` for every related node).

`RawTarget.predicted_t_remain` is measured from the image capture time:

```text
landing_time = capture_stamp + predicted_t_remain
real_t_remain = landing_time - manager_update_time
```

## Coordinate convention

Coordinates are fixed to the world/court frame and are not repeated in every
message:

- origin: tennis-court geometric center;
- +X: along court length;
- +Y: robot-left direction;
- unit: metre.

The target is the predicted ball position when it reaches the configured target
plane. The current headless vision default is ground landing at `field_z = 0.0`.

## ID convention

- `task_id` increases for each new ball/catching task.
- `sequence_id` increases for every prediction frame within that task.
- Delayed older tasks and duplicate/out-of-order frames are discarded.

## Manager pipeline

1. Receive every 30 Hz raw prediction.
2. Validate numbers, time, task ID, sequence ID, and broad court bounds.
3. Correct the remaining time using the ROS clock.
4. Keep the latest 15 frames (about 0.5 seconds).
5. Suppress isolated large jumps; accept a large correction after 3 consistent
   frames.
6. Apply a per-axis exponential filter using the vision-provided standard
   deviations. A smaller sigma gives the new prediction more weight.
7. Mark the estimate stable when the latest 5 frames stay within a 5 cm range
   on both axes.
8. Publish a new managed target only when the filtered target moves at least
   8 cm or stability changes, while limiting normal output to 10 Hz.

Changes between 3 cm and 8 cm are not discarded: they update the filtered
target and can accumulate until the 8 cm planner-update threshold is reached.
Changes below 3 cm are also absorbed at half weight to avoid both jitter and
permanent small bias.

All numerical thresholds are ROS parameters in
`target_manager/config/target_manager.yaml`.
