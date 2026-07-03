# Target-manager output consumed by the state machine and trajectory planner.

# Time at which the manager generated this message.
builtin_interfaces/Time update_stamp

uint64 task_id
uint32 sequence_id

# Filtered target position in the world/court frame. Unit: metre.
float64 target_x
float64 target_y

# Remaining time at update_stamp, after subtracting vision/transport latency.
builtin_interfaces/Duration real_t_remain

# Latest vision-provided 1-sigma uncertainty. Unit: metre.
float64 sigma_x
float64 sigma_y

# True when the recent prediction window is spatially stable.
bool stable
