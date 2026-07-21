# ROS Interface Adapter Plan and Result - 2026-07-03

## Frequency Answer

- Vision-to-interface raw target input is expected at 30 Hz:
  `/vision/target_prediction` -> `/target/raw`.
- Interface-to-vision chassis position is also expected at 30 Hz:
  `/robot/chassis_position` -> `/vision/chassis_position`.
- `target_manager` output is not 30 Hz. `/target/managed` is intentionally
  rate-limited to at most 10 Hz for the planner/state-machine side.

The adapter is event-driven. It does not synthesize 30 Hz data with a timer.
It forwards incoming messages and can drop messages above the configured
maximum rates. If an upstream producer runs below 30 Hz, the adapter will not
invent missing frames.

## Plan

1. Keep the imported `src/interface/target_msgs` package as the external
   interface contract.
2. Add repository-owned vision-side ROS messages so vision code does not need
   to publish directly to the external interface topic names.
3. Add a thin ROS adapter node:
   - external `target_msgs/ChassisPosition` to vision
     `tennisbot_vision_msgs/ChassisPosition`;
   - vision `tennisbot_vision_msgs/TargetPrediction` to external
     `target_msgs/RawTarget`.
4. Keep the adapter limited to validation, field mapping, topic mapping, and
   optional rate limiting. Do not add catch simulation, local vehicle tracking,
   or substitute closed-loop logic.
5. Verify ROS package discovery, Python syntax, and isolated `colcon build`.

## Topic Map

```text
motion/control interface program
    |
    | /robot/chassis_position
    | target_msgs/ChassisPosition
    | nominal 30 Hz
    v
tennisbot_interface_adapter
    |
    | /vision/chassis_position
    | tennisbot_vision_msgs/ChassisPosition
    | forwarded, max 30 Hz by default
    v
vision pipeline

vision pipeline
    |
    | /vision/target_prediction
    | tennisbot_vision_msgs/TargetPrediction
    | nominal 30 Hz
    v
tennisbot_interface_adapter
    |
    | /target/raw
    | target_msgs/RawTarget
    | forwarded, max 30 Hz by default
    v
target_manager
    |
    | /target/managed
    | target_msgs/ManagedTarget
    | at most 10 Hz
    v
planner/state machine
```

## Added Packages

- `tennisbot_vision_msgs`
  - `ChassisPosition.msg`
  - `TargetPrediction.msg`
- `tennisbot_interface_adapter`
  - `vision_interface_adapter_node`
  - `interface_adapter.launch.py`
  - `config/interface_adapter.yaml`

## Run

Build from the repository root with ROS Humble sourced. In this shell, use the
system Python path to avoid conda Python interfering with ROS message
generation:

```bash
env PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/ros/humble/bin PYTHONNOUSERSITE=1 \
  colcon build --base-paths src
```

Run the adapter:

```bash
ros2 launch tennisbot_interface_adapter interface_adapter.launch.py
```

For simulator or any `/clock` based run:

```bash
ros2 launch tennisbot_interface_adapter interface_adapter.launch.py use_sim_time:=true
```

## Verification Results

- `colcon list --base-paths src`
  - Passed.
  - Detected `target_msgs`, `target_manager`, `tennisbot_vision_msgs`, and
    `tennisbot_interface_adapter`.
- `uv run -- python ... compile(...)`
  - Passed.
  - Compiled 10 Python files under `src`.
- Isolated ROS Humble build with system Python
  - Passed.
  - Built `target_msgs`, `target_manager`, `tennisbot_vision_msgs`, and
    `tennisbot_interface_adapter`.
- `ros2 pkg executables tennisbot_interface_adapter`
  - Passed.
  - Reported `vision_interface_adapter_node`.
- `ros2 launch tennisbot_interface_adapter interface_adapter.launch.py --show-args`
  - Passed.
  - Reported `use_sim_time` launch argument.
- `ros2 interface show tennisbot_vision_msgs/msg/TargetPrediction`
  - Passed.
  - Confirmed the vision-side target prediction message is registered.
