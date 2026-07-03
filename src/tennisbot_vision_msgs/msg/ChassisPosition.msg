# Vision-side chassis position consumed by the stereo/trajectory pipeline.
# Coordinates are in the same world/court frame as the external interface.

# Timestamp carried by the external interface publisher.
builtin_interfaces/Time stamp

# Sequence number from the external interface publisher.
uint32 sequence_id

# Chassis center position in world/court frame. Unit: metre.
float64 x
float64 y
