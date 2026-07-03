from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

try:
    from builtin_interfaces.msg import Duration
except ModuleNotFoundError:  # Allows pure trajectory tests without a sourced ROS env.

    class Duration:  # type: ignore[no-redef]
        sec: int
        nanosec: int


NANOSECONDS_PER_SECOND = 1_000_000_000
DEFAULT_WEIGHTED_WINDOW_SIZE = 9
DEFAULT_MIN_WEIGHTED_FIT_POINTS = 5
DEFAULT_RANSAC_WINDOW_SIZE = 12
DEFAULT_MIN_RANSAC_POINTS = 6
DEFAULT_RANSAC_SUBSET_SIZE = 4
DEFAULT_RANSAC_THRESHOLD_METERS = 0.12

TrajectoryPredictionMethod = Literal["auto", "two-frame", "weighted-ls", "ransac-ls"]


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
    model: str = ""
    source_count: int = 0
    inlier_count: int = 0
    residual_m: float = 0.0


@dataclass(frozen=True)
class Vector3:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class FitResult:
    position_m: Vector3
    velocity_mps: Vector3
    residual_m: float


@dataclass(frozen=True)
class ProjectileStateEstimate:
    position_m: Vector3
    velocity_mps: Vector3
    source_observations: tuple[BallObservation, ...]
    model: str
    residual_m: float
    inlier_count: int


def predict_target(
    observations: list[BallObservation],
    *,
    target_plane_z: float,
    gravity_mps2: float,
    min_time_s: float,
    max_time_s: float,
    min_sigma_m: float,
    method: TrajectoryPredictionMethod = "auto",
    weighted_window_size: int = DEFAULT_WEIGHTED_WINDOW_SIZE,
    min_weighted_fit_points: int = DEFAULT_MIN_WEIGHTED_FIT_POINTS,
    ransac_window_size: int = DEFAULT_RANSAC_WINDOW_SIZE,
    min_ransac_points: int = DEFAULT_MIN_RANSAC_POINTS,
    ransac_subset_size: int = DEFAULT_RANSAC_SUBSET_SIZE,
    ransac_iterations: int | None = None,
    ransac_threshold_m: float = DEFAULT_RANSAC_THRESHOLD_METERS,
) -> TrajectoryPrediction | None:
    if len(observations) < 2:
        return None
    if method not in ("auto", "two-frame", "weighted-ls", "ransac-ls"):
        return None
    if not all(
        math.isfinite(value)
        for value in (
            target_plane_z,
            gravity_mps2,
            min_time_s,
            max_time_s,
            min_sigma_m,
            ransac_threshold_m,
        )
    ):
        return None
    if gravity_mps2 <= 0.0 or min_time_s <= 0.0 or max_time_s <= 0.0 or min_time_s > max_time_s:
        return None
    if min_sigma_m < 0.0 or ransac_threshold_m <= 0.0:
        return None
    if (
        weighted_window_size < 2
        or min_weighted_fit_points < 2
        or ransac_window_size < 2
        or min_ransac_points < 2
        or ransac_subset_size < 2
    ):
        return None
    if ransac_iterations is not None and ransac_iterations <= 0:
        return None

    ordered = sorted(observations, key=lambda item: item.stamp_ns)
    state = estimate_projectile_state(
        ordered,
        gravity_mps2=gravity_mps2,
        method=method,
        weighted_window_size=weighted_window_size,
        min_weighted_fit_points=min_weighted_fit_points,
        ransac_window_size=ransac_window_size,
        min_ransac_points=min_ransac_points,
        ransac_subset_size=ransac_subset_size,
        ransac_iterations=ransac_iterations,
        ransac_threshold_m=ransac_threshold_m,
    )
    if state is None:
        return None

    t_remain = solve_landing_time_sec(
        z0=state.position_m.z,
        vz0=state.velocity_mps.z,
        landing_surface_z=target_plane_z,
        gravity_mps2=gravity_mps2,
    )
    if t_remain is None or t_remain < min_time_s or t_remain > max_time_s:
        return None

    target_x = state.position_m.x + state.velocity_mps.x * t_remain
    target_y = state.position_m.y + state.velocity_mps.y * t_remain
    sigma_x = max(
        min_sigma_m,
        axis_residual_rms(
            state.source_observations,
            reference_ns=ordered[-1].stamp_ns,
            intercept=state.position_m.x,
            slope=state.velocity_mps.x,
            axis="x",
        ),
    )
    sigma_y = max(
        min_sigma_m,
        axis_residual_rms(
            state.source_observations,
            reference_ns=ordered[-1].stamp_ns,
            intercept=state.position_m.y,
            slope=state.velocity_mps.y,
            axis="y",
        ),
    )
    if not all(math.isfinite(value) for value in (target_x, target_y, sigma_x, sigma_y)):
        return None

    return TrajectoryPrediction(
        target_x=target_x,
        target_y=target_y,
        target_z=target_plane_z,
        predicted_t_remain=t_remain,
        sigma_x=sigma_x,
        sigma_y=sigma_y,
        model=state.model,
        source_count=len(state.source_observations),
        inlier_count=state.inlier_count,
        residual_m=state.residual_m,
    )


def estimate_projectile_state(
    sorted_observations: list[BallObservation],
    *,
    gravity_mps2: float,
    method: TrajectoryPredictionMethod,
    weighted_window_size: int = DEFAULT_WEIGHTED_WINDOW_SIZE,
    min_weighted_fit_points: int = DEFAULT_MIN_WEIGHTED_FIT_POINTS,
    ransac_window_size: int = DEFAULT_RANSAC_WINDOW_SIZE,
    min_ransac_points: int = DEFAULT_MIN_RANSAC_POINTS,
    ransac_subset_size: int = DEFAULT_RANSAC_SUBSET_SIZE,
    ransac_iterations: int | None = None,
    ransac_threshold_m: float = DEFAULT_RANSAC_THRESHOLD_METERS,
) -> ProjectileStateEstimate | None:
    two_frame = fit_two_frame(sorted_observations)
    if two_frame is None:
        return None
    if method == "two-frame":
        return two_frame

    weighted = fit_weighted_window(
        sorted_observations,
        gravity_mps2=gravity_mps2,
        weighted_window_size=weighted_window_size,
        min_weighted_fit_points=min_weighted_fit_points,
    )
    if method == "weighted-ls":
        return weighted

    ransac = fit_ransac_guard(
        sorted_observations,
        gravity_mps2=gravity_mps2,
        weighted_window_size=weighted_window_size,
        min_weighted_fit_points=min_weighted_fit_points,
        ransac_window_size=ransac_window_size,
        min_ransac_points=min_ransac_points,
        ransac_subset_size=ransac_subset_size,
        ransac_iterations=ransac_iterations,
        ransac_threshold_m=ransac_threshold_m,
    )
    if method == "ransac-ls":
        return ransac
    if method != "auto":
        return None

    if ransac is not None:
        return ransac
    if weighted is not None:
        return weighted
    return two_frame


def fit_two_frame(sorted_observations: list[BallObservation]) -> ProjectileStateEstimate | None:
    if len(sorted_observations) < 2:
        return None
    previous = sorted_observations[-2]
    current = sorted_observations[-1]
    dt_s = (current.stamp_ns - previous.stamp_ns) / NANOSECONDS_PER_SECOND
    if not math.isfinite(dt_s) or dt_s <= 0.0:
        return None

    state = ProjectileStateEstimate(
        position_m=Vector3(current.x, current.y, current.z),
        velocity_mps=Vector3(
            (current.x - previous.x) / dt_s,
            (current.y - previous.y) / dt_s,
            (current.z - previous.z) / dt_s,
        ),
        source_observations=(previous, current),
        model="projectile-3d-two-frame-constant-gravity",
        residual_m=0.0,
        inlier_count=2,
    )
    return state


def fit_weighted_window(
    sorted_observations: list[BallObservation],
    *,
    gravity_mps2: float,
    weighted_window_size: int,
    min_weighted_fit_points: int,
) -> ProjectileStateEstimate | None:
    window = sorted_observations[-weighted_window_size:]
    if len(window) < min_weighted_fit_points:
        return None

    fit = fit_fixed_gravity(
        window,
        gravity_mps2=gravity_mps2,
        reference_ns=sorted_observations[-1].stamp_ns,
        weighted=True,
    )
    if fit is None:
        return None

    return ProjectileStateEstimate(
        position_m=fit.position_m,
        velocity_mps=fit.velocity_mps,
        source_observations=tuple(window),
        model="projectile-3d-weighted-ls9-constant-gravity",
        residual_m=fit.residual_m,
        inlier_count=len(window),
    )


def fit_ransac_guard(
    sorted_observations: list[BallObservation],
    *,
    gravity_mps2: float,
    weighted_window_size: int,
    min_weighted_fit_points: int,
    ransac_window_size: int,
    min_ransac_points: int,
    ransac_subset_size: int,
    ransac_iterations: int | None,
    ransac_threshold_m: float,
) -> ProjectileStateEstimate | None:
    window = sorted_observations[-ransac_window_size:]
    if len(window) < min_ransac_points or len(window) < ransac_subset_size:
        return None

    reference_ns = sorted_observations[-1].stamp_ns
    best: tuple[FitResult, tuple[BallObservation, ...], int] | None = None
    for subset in candidate_subsets(window, ransac_subset_size, ransac_iterations):
        candidate = fit_fixed_gravity(
            subset,
            gravity_mps2=gravity_mps2,
            reference_ns=reference_ns,
            weighted=False,
        )
        if candidate is None:
            continue

        inliers = tuple(
            point
            for point in window
            if trajectory_residual_m(
                point,
                reference_ns=reference_ns,
                position_m=candidate.position_m,
                velocity_mps=candidate.velocity_mps,
                gravity_mps2=gravity_mps2,
            )
            <= ransac_threshold_m
        )
        if len(inliers) < min_weighted_fit_points:
            continue

        fit_samples = inliers[-weighted_window_size:]
        refined = fit_fixed_gravity(
            list(fit_samples),
            gravity_mps2=gravity_mps2,
            reference_ns=reference_ns,
            weighted=True,
        )
        if refined is None:
            continue

        if (
            best is None
            or len(inliers) > best[2]
            or (len(inliers) == best[2] and refined.residual_m < best[0].residual_m)
        ):
            best = (refined, fit_samples, len(inliers))

    if best is None:
        return None
    fit, fit_samples, inlier_count = best
    if inlier_count < max(min_weighted_fit_points, math.ceil(len(window) * 0.5)):
        return None

    return ProjectileStateEstimate(
        position_m=fit.position_m,
        velocity_mps=fit.velocity_mps,
        source_observations=tuple(fit_samples),
        model="projectile-3d-weighted-ls9-ransac-constant-gravity",
        residual_m=fit.residual_m,
        inlier_count=inlier_count,
    )


def fit_fixed_gravity(
    samples: list[BallObservation] | tuple[BallObservation, ...],
    *,
    gravity_mps2: float,
    reference_ns: int,
    weighted: bool,
) -> FitResult | None:
    if len(samples) < 2:
        return None

    sorted_samples = sorted(samples, key=lambda item: item.stamp_ns)
    taus = [(sample.stamp_ns - reference_ns) / NANOSECONDS_PER_SECOND for sample in sorted_samples]
    weights = [
        1.0
        if not weighted
        else math.exp(-max(0.0, (reference_ns - sample.stamp_ns) / NANOSECONDS_PER_SECOND) / 0.18)
        * (0.6 + (index + 1) / len(sorted_samples))
        for index, sample in enumerate(sorted_samples)
    ]

    x_fit = weighted_line_fit(taus, [sample.x for sample in sorted_samples], weights)
    y_fit = weighted_line_fit(taus, [sample.y for sample in sorted_samples], weights)
    z_fit = weighted_line_fit(
        taus,
        [
            sample.z + 0.5 * gravity_mps2 * tau * tau
            for sample, tau in zip(sorted_samples, taus, strict=True)
        ],
        weights,
    )
    if x_fit is None or y_fit is None or z_fit is None:
        return None

    position_m = Vector3(x_fit[0], y_fit[0], z_fit[0])
    velocity_mps = Vector3(x_fit[1], y_fit[1], z_fit[1])
    residual_m = sum(
        trajectory_residual_m(
            point,
            reference_ns=reference_ns,
            position_m=position_m,
            velocity_mps=velocity_mps,
            gravity_mps2=gravity_mps2,
        )
        for point in sorted_samples
    ) / len(sorted_samples)

    return FitResult(position_m=position_m, velocity_mps=velocity_mps, residual_m=residual_m)


def weighted_line_fit(xs: list[float], ys: list[float], weights: list[float]) -> tuple[float, float] | None:
    weight_sum = 0.0
    weighted_x_sum = 0.0
    weighted_y_sum = 0.0
    weighted_x2_sum = 0.0
    weighted_xy_sum = 0.0

    for x, y, weight in zip(xs, ys, weights, strict=True):
        if not all(math.isfinite(value) for value in (x, y, weight)):
            return None
        weight_sum += weight
        weighted_x_sum += weight * x
        weighted_y_sum += weight * y
        weighted_x2_sum += weight * x * x
        weighted_xy_sum += weight * x * y

    denominator = weight_sum * weighted_x2_sum - weighted_x_sum * weighted_x_sum
    if abs(denominator) < 1e-12:
        return None

    slope = (weight_sum * weighted_xy_sum - weighted_x_sum * weighted_y_sum) / denominator
    intercept = (weighted_y_sum - slope * weighted_x_sum) / weight_sum
    return intercept, slope


def candidate_subsets(
    items: list[BallObservation],
    subset_size: int,
    iteration_limit: int | None,
) -> list[list[BallObservation]]:
    subsets: list[list[BallObservation]] = []
    indices: list[int] = []
    limit = iteration_limit
    if limit is None and len(items) > DEFAULT_RANSAC_WINDOW_SIZE:
        limit = 240

    def visit(start: int) -> None:
        if limit is not None and len(subsets) >= limit:
            return
        if len(indices) == subset_size:
            subsets.append([items[index] for index in indices])
            return

        remaining = subset_size - len(indices)
        for index in range(start, len(items) - remaining + 1):
            indices.append(index)
            visit(index + 1)
            indices.pop()
            if limit is not None and len(subsets) >= limit:
                return

    visit(0)
    return subsets


def trajectory_residual_m(
    point: BallObservation,
    *,
    reference_ns: int,
    position_m: Vector3,
    velocity_mps: Vector3,
    gravity_mps2: float,
) -> float:
    t_s = (point.stamp_ns - reference_ns) / NANOSECONDS_PER_SECOND
    predicted = projectile_point(position_m, velocity_mps, t_s, gravity_mps2)
    return math.dist((predicted.x, predicted.y, predicted.z), (point.x, point.y, point.z))


def projectile_point(position_m: Vector3, velocity_mps: Vector3, t_s: float, gravity_mps2: float) -> Vector3:
    return Vector3(
        x=position_m.x + velocity_mps.x * t_s,
        y=position_m.y + velocity_mps.y * t_s,
        z=position_m.z + velocity_mps.z * t_s - 0.5 * gravity_mps2 * t_s * t_s,
    )


def solve_landing_time_sec(
    *,
    z0: float,
    vz0: float,
    landing_surface_z: float,
    gravity_mps2: float,
) -> float | None:
    relative_z = z0 - landing_surface_z
    discriminant = vz0 * vz0 + 2.0 * gravity_mps2 * relative_z
    if discriminant < 0.0:
        return None

    sqrt_discriminant = math.sqrt(discriminant)
    candidates = [
        value
        for value in (
            (vz0 + sqrt_discriminant) / gravity_mps2,
            (vz0 - sqrt_discriminant) / gravity_mps2,
        )
        if value > 0.0
    ]
    return min(candidates) if candidates else None


def axis_residual_rms(
    samples: tuple[BallObservation, ...],
    *,
    reference_ns: int,
    intercept: float,
    slope: float,
    axis: Literal["x", "y"],
) -> float:
    if not samples:
        return 0.0

    total = 0.0
    for sample in samples:
        t_s = (sample.stamp_ns - reference_ns) / NANOSECONDS_PER_SECOND
        value = sample.x if axis == "x" else sample.y
        residual = value - (intercept + slope * t_s)
        total += residual * residual
    return math.sqrt(total / len(samples))


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
