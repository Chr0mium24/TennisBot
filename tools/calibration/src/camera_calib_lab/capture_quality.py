from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import cv2
import numpy as np

from camera_calib_lab.capture_types import CaptureConfig, CharucoDetection, TargetConfig


@dataclass(frozen=True)
class AutoCaptureQuality:
    accepted: bool
    reason: str
    mean_gray: float
    exposure_ok: bool
    sharpness: float
    corner_count: int
    required_corners: int
    center_x: float | None
    center_y: float | None
    area_ratio: float | None
    position_bucket: str | None
    stable: bool = False
    stable_frame_count: int = 0


def required_charuco_corners(target: TargetConfig, capture: CaptureConfig) -> int:
    full_count = max(0, (target.squares_x - 1) * (target.squares_y - 1))
    coverage = min(1.0, max(0.0, float(capture.min_corner_coverage)))
    coverage_count = int(ceil(full_count * coverage)) if full_count else 0
    return max(int(capture.min_corners), coverage_count)


def exposure_is_usable(mean_gray: float, minimum: float = 5.0, maximum: float = 250.0) -> bool:
    return minimum <= mean_gray <= maximum


def evaluate_frame_quality(
    *,
    frame: np.ndarray,
    detection: CharucoDetection,
    required_corners: int,
    min_sharpness: float,
    position_bins: tuple[int, int],
) -> AutoCaptureQuality:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    mean_gray = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    exposure_ok = exposure_is_usable(mean_gray)
    geometry = detection_geometry(detection.points, (int(gray.shape[1]), int(gray.shape[0])), position_bins)
    if detection.count < required_corners:
        return quality(False, f"need {required_corners} full corners", detection, mean_gray, exposure_ok, sharpness, required_corners, geometry)
    if not exposure_ok:
        return quality(False, "exposure check", detection, mean_gray, exposure_ok, sharpness, required_corners, geometry)
    if sharpness < min_sharpness:
        return quality(False, "sharpness check", detection, mean_gray, exposure_ok, sharpness, required_corners, geometry)
    if geometry["position_bucket"] is None:
        return quality(False, "missing position bucket", detection, mean_gray, exposure_ok, sharpness, required_corners, geometry)
    return quality(True, "accepted", detection, mean_gray, exposure_ok, sharpness, required_corners, geometry)


def quality(
    accepted: bool,
    reason: str,
    detection: CharucoDetection,
    mean_gray: float,
    exposure_ok: bool,
    sharpness: float,
    required_corners: int,
    geometry: dict[str, float | str | None],
) -> AutoCaptureQuality:
    return AutoCaptureQuality(
        accepted=accepted,
        reason=reason,
        mean_gray=mean_gray,
        exposure_ok=exposure_ok,
        sharpness=sharpness,
        corner_count=detection.count,
        required_corners=required_corners,
        center_x=float(geometry["center_x"]) if geometry["center_x"] is not None else None,
        center_y=float(geometry["center_y"]) if geometry["center_y"] is not None else None,
        area_ratio=float(geometry["area_ratio"]) if geometry["area_ratio"] is not None else None,
        position_bucket=str(geometry["position_bucket"]) if geometry["position_bucket"] is not None else None,
    )


def detection_geometry(
    points: tuple[tuple[float, float], ...],
    image_size: tuple[int, int],
    position_bins: tuple[int, int],
) -> dict[str, float | str | None]:
    if not points:
        return {"center_x": None, "center_y": None, "area_ratio": None, "position_bucket": None}
    width, height = image_size
    array = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    x_min, y_min = np.min(array, axis=0)
    x_max, y_max = np.max(array, axis=0)
    cx = ((x_min + x_max) * 0.5) / max(1.0, float(width))
    cy = ((y_min + y_max) * 0.5) / max(1.0, float(height))
    area_ratio = ((x_max - x_min) * (y_max - y_min)) / max(1.0, float(width * height))
    x_bins = max(1, int(position_bins[0]))
    y_bins = max(1, int(position_bins[1]))
    x_bin = min(x_bins - 1, max(0, int(cx * x_bins)))
    y_bin = min(y_bins - 1, max(0, int(cy * y_bins)))
    return {
        "center_x": float(cx),
        "center_y": float(cy),
        "area_ratio": float(area_ratio),
        "position_bucket": f"x{x_bin}:y{y_bin}",
    }


def quality_with_stability(
    quality: AutoCaptureQuality,
    recent_qualities: tuple[AutoCaptureQuality, ...],
    stability_frames: int,
    stable_center_delta: float,
    stable_area_delta: float,
) -> AutoCaptureQuality:
    required_history = max(0, int(stability_frames) - 1)
    if not quality.accepted:
        return quality
    if required_history == 0:
        return stable_quality(quality, 1)
    if len(recent_qualities) < required_history:
        return unstable_quality(quality, f"stabilizing {len(recent_qualities) + 1}/{stability_frames}", len(recent_qualities) + 1)
    if quality.center_x is None or quality.center_y is None or quality.area_ratio is None:
        return unstable_quality(quality, "missing stability geometry", len(recent_qualities) + 1)
    for previous in recent_qualities[-required_history:]:
        if not previous.accepted or previous.center_x is None or previous.center_y is None or previous.area_ratio is None:
            return unstable_quality(quality, "waiting for stable full-corner frames", len(recent_qualities) + 1)
        center_delta = max(abs(float(previous.center_x) - float(quality.center_x)), abs(float(previous.center_y) - float(quality.center_y)))
        if center_delta > stable_center_delta:
            return unstable_quality(quality, "hold steady", len(recent_qualities) + 1)
        area_scale = max(abs(float(previous.area_ratio)), abs(float(quality.area_ratio)), 1.0e-6)
        area_delta = abs(float(previous.area_ratio) - float(quality.area_ratio)) / area_scale
        if area_delta > stable_area_delta:
            return unstable_quality(quality, "hold distance steady", len(recent_qualities) + 1)
    return stable_quality(quality, len(recent_qualities) + 1)


def stable_quality(quality: AutoCaptureQuality, frame_count: int) -> AutoCaptureQuality:
    return AutoCaptureQuality(
        quality.accepted,
        "accepted",
        quality.mean_gray,
        quality.exposure_ok,
        quality.sharpness,
        quality.corner_count,
        quality.required_corners,
        quality.center_x,
        quality.center_y,
        quality.area_ratio,
        quality.position_bucket,
        stable=True,
        stable_frame_count=frame_count,
    )


def unstable_quality(quality: AutoCaptureQuality, reason: str, frame_count: int) -> AutoCaptureQuality:
    return AutoCaptureQuality(
        False,
        reason,
        quality.mean_gray,
        quality.exposure_ok,
        quality.sharpness,
        quality.corner_count,
        quality.required_corners,
        quality.center_x,
        quality.center_y,
        quality.area_ratio,
        quality.position_bucket,
        stable=False,
        stable_frame_count=frame_count,
    )


def should_auto_capture(
    quality: AutoCaptureQuality,
    bucket_counts: dict[str, int],
    now: float,
    last_capture_at: float,
    min_capture_interval_s: float,
    max_views_per_bucket: int,
    last_capture_bucket: str | None = None,
    dwell_seconds: float = 0.0,
    dwell_capture_s: float = 0.0,
) -> bool:
    if not quality.accepted or quality.position_bucket is None or not quality.stable:
        return False
    if now - last_capture_at < min_capture_interval_s:
        return False
    if dwell_capture_s > 0.0 and dwell_seconds >= dwell_capture_s:
        return True
    bucket = str(quality.position_bucket)
    return bucket != last_capture_bucket and bucket_counts.get(bucket, 0) < max_views_per_bucket


def stereo_pair_quality(left: AutoCaptureQuality, right: AutoCaptureQuality) -> AutoCaptureQuality:
    if not left.accepted:
        return pair_quality(False, f"left: {left.reason}", left, right)
    if not right.accepted:
        return pair_quality(False, f"right: {right.reason}", left, right)
    if left.position_bucket is None:
        return pair_quality(False, "left: missing position bucket", left, right)
    return pair_quality(True, "accepted", left, right)


def pair_quality(accepted: bool, reason: str, left: AutoCaptureQuality, right: AutoCaptureQuality) -> AutoCaptureQuality:
    return AutoCaptureQuality(
        accepted=accepted,
        reason=reason,
        mean_gray=min(float(left.mean_gray), float(right.mean_gray)),
        exposure_ok=bool(left.exposure_ok and right.exposure_ok),
        sharpness=min(float(left.sharpness), float(right.sharpness)),
        corner_count=min(int(left.corner_count), int(right.corner_count)),
        required_corners=max(int(left.required_corners), int(right.required_corners)),
        center_x=left.center_x,
        center_y=left.center_y,
        area_ratio=left.area_ratio,
        position_bucket=left.position_bucket,
        stable=bool(accepted and left.stable and right.stable),
        stable_frame_count=min(int(left.stable_frame_count), int(right.stable_frame_count)),
    )
