# Coordinate Frame Decision - 2026-07-03

## Plan

1. Record the field/interface coordinate frame in `AGENTS.md`.
2. Make the field/interface frame the canonical runtime algorithm frame.
3. Avoid deferring coordinate conversion until only the `/target/raw` publish
   boundary.

## Decision

The field/interface frame is centered at the tennis-court geometric center.

```text
field_x = cartesian_y
field_y = -cartesian_x
field_z = cartesian_z
```

The inverse transform is:

```text
cartesian_x = -field_y
cartesian_y = field_x
cartesian_z = field_z
```

For standard mathematical yaw measured from Cartesian `+x` with
counter-clockwise positive rotation:

```text
field_yaw = cartesian_yaw - pi / 2
cartesian_yaw = field_yaw + pi / 2
```

## Algorithm Rule

The headless vision runtime should convert observations into the
field/interface frame as soon as camera-frame points are transformed through
the chassis pose. Trajectory fitting, catch-plane or landing prediction,
stability checks, and `/target/raw` publishing should all use
the field/interface frame.

Only converting at the final publish boundary is not enough because it leaves
intermediate trajectory state, logs, quality gates, and future control
decisions in a different frame.

## Result

- Updated `AGENTS.md` with the coordinate-frame transform and algorithm rule.
