# Vision-side target prediction produced by the stereo/trajectory pipeline.
# The adapter converts this message to target_msgs/RawTarget for the external
# interface layer.

# Actual image capture time, not the vision result publication time.
builtin_interfaces/Time capture_stamp

# Monotonically increasing ID for each new ball/catching task.
uint64 task_id

# Monotonically increasing frame number within one task.
uint32 sequence_id

# Predicted ball position when it reaches the configured target plane. Unit: metre.
float64 target_x
float64 target_y

# Remaining time measured from capture_stamp to the target-plane event.
builtin_interfaces/Duration predicted_t_remain

# Vision-provided 1-sigma prediction uncertainty. Unit: metre.
float64 sigma_x
float64 sigma_y
