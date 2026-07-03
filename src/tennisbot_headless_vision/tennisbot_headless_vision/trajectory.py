from __future__ import annotations

from dataclasses import dataclass
import math

from builtin_interfaces.msg import Duration


NANOSECONDS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True)
class BallObservation:
    stamp_ns: int
    x: float
    y: float
    z: float
    confidence: float


@dataclass(frozen=True)
class TrajectoryPrediction:
    target_x: float
    target_y: float
    target_z: float
    predicted_t_remain: float
    sigma_x: float
    sigma_y: float


def predict_target(
    observations: list[BallObservation],
    *,
    target_plane_z: float,
    gravity_mps2: float,
    min_time_s: float,
    max_time_s: float,
    min_sigma_m: float,
) -> TrajectoryPrediction | None:
    if len(observations) < 2:
        return None
    ordered = sorted(observations, key=lambda item: item.stamp_ns)
    latest_ns = ordered[-1].stamp_ns
    times = [(item.stamp_ns - latest_ns) / NANOSECONDS_PER_SECOND for item in ordered]
    if any(later <= earlier for earlier, later in zip(times, times[1:], strict=False)):
        return None

    x0, vx = fit_line(times, [item.x for item in ordered])
    y0, vy = fit_line(times, [item.y for item in ordered])
    z_values = [
        item.z + 0.5 * gravity_mps2 * time_s * time_s
        for item, time_s in zip(ordered, times, strict=True)
    ]
    z0, vz = fit_line(times, z_values)
    t_remain = solve_plane_time(
        z0=z0,
        vz=vz,
        target_plane_z=target_plane_z,
        gravity_mps2=gravity_mps2,
        min_time_s=min_time_s,
        max_time_s=max_time_s,
    )
    if t_remain is None:
        return None

    target_x = x0 + vx * t_remain
    target_y = y0 + vy * t_remain
    sigma_x = max(min_sigma_m, residual_rms(times, [item.x for item in ordered], x0, vx))
    sigma_y = max(min_sigma_m, residual_rms(times, [item.y for item in ordered], y0, vy))
    if not all(math.isfinite(value) for value in (target_x, target_y, sigma_x, sigma_y)):
        return None

    return TrajectoryPrediction(
        target_x=target_x,
        target_y=target_y,
        target_z=target_plane_z,
        predicted_t_remain=t_remain,
        sigma_x=sigma_x,
        sigma_y=sigma_y,
    )


def fit_line(times: list[float], values: list[float]) -> tuple[float, float]:
    if len(times) != len(values) or len(times) < 2:
        raise ValueError("fit_line requires at least two paired samples")
    n = float(len(times))
    sum_t = sum(times)
    sum_tt = sum(time_s * time_s for time_s in times)
    sum_y = sum(values)
    sum_ty = sum(time_s * value for time_s, value in zip(times, values, strict=True))
    det = n * sum_tt - sum_t * sum_t
    if abs(det) < 1e-12:
        raise ValueError("fit_line sample times are degenerate")
    intercept = (sum_y * sum_tt - sum_t * sum_ty) / det
    slope = (n * sum_ty - sum_t * sum_y) / det
    return intercept, slope


def solve_plane_time(
    *,
    z0: float,
    vz: float,
    target_plane_z: float,
    gravity_mps2: float,
    min_time_s: float,
    max_time_s: float,
) -> float | None:
    # z(t) = z0 + vz*t - 0.5*g*t^2
    a = -0.5 * gravity_mps2
    b = vz
    c = z0 - target_plane_z
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return None
    sqrt_d = math.sqrt(discriminant)
    roots = [(-b + sqrt_d) / (2.0 * a), (-b - sqrt_d) / (2.0 * a)]
    valid = sorted(root for root in roots if min_time_s <= root <= max_time_s)
    return valid[0] if valid else None


def residual_rms(
    times: list[float],
    values: list[float],
    intercept: float,
    slope: float,
) -> float:
    if not times:
        return 0.0
    total = 0.0
    for time_s, value in zip(times, values, strict=True):
        residual = value - (intercept + slope * time_s)
        total += residual * residual
    return math.sqrt(total / len(times))


def seconds_to_duration(seconds: float) -> Duration:
    sec = int(math.floor(seconds))
    nanosec = int(round((seconds - sec) * NANOSECONDS_PER_SECOND))
    if nanosec >= NANOSECONDS_PER_SECOND:
        sec += 1
        nanosec -= NANOSECONDS_PER_SECOND
    duration = Duration()
    duration.sec = sec
    duration.nanosec = nanosec
    return duration
