# Vision-side chassis pose consumed by the headless stereo/trajectory pipeline.
# Coordinates are in the field/interface frame unless explicitly converted by
# the adapter configuration.

# Time when this pose sample was produced or received.
builtin_interfaces/Time stamp

# Monotonically increasing pose sample number.
uint32 sequence_id

# Chassis origin in the field/interface frame. Unit: metre.
float64 x
float64 y
float64 z

# Chassis orientation in the field/interface frame. Unit: radian.
float64 roll
float64 pitch
float64 yaw

# Optional chassis velocity values from the backend. Unit: metre/second.
float64 linear_velocity
float64 ground_speed
