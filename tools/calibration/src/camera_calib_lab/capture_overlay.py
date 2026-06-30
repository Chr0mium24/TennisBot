from __future__ import annotations

import cv2
import numpy as np

from camera_calib_lab.capture_quality import AutoCaptureQuality
from camera_calib_lab.capture_types import preview_display_size, resized_preview_frame


ButtonBounds = tuple[int, int, int, int]


def charuco_auto_preview_frame(
    frame: np.ndarray,
    points: tuple[tuple[float, float], ...],
    lines: list[str],
    calibrate_enabled: bool,
    bucket_counts: dict[str, int] | None = None,
    position_bins: tuple[int, int] = (1, 1),
    current_bucket: str | None = None,
) -> tuple[np.ndarray, ButtonBounds]:
    display_size = preview_display_size(frame.shape)
    preview = resized_preview_frame(frame, display_size)
    preview = draw_position_bucket_overlay(preview, bucket_counts or {}, position_bins, current_bucket)
    display_points = scaled_points(points, frame.shape, display_size)
    if display_points:
        preview = draw_detection_points(preview, display_points)
    preview = draw_status_overlay(preview, lines)
    button_bounds = calibrate_button_bounds(preview.shape)
    preview = draw_calibrate_button(preview, button_bounds, calibrate_enabled)
    return preview, button_bounds


def stereo_charuco_preview_frame(
    *,
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    left_points: tuple[tuple[float, float], ...],
    right_points: tuple[tuple[float, float], ...],
    lines: list[str],
    calibrate_enabled: bool,
    bucket_counts: dict[str, int] | None = None,
    position_bins: tuple[int, int] = (1, 1),
    current_bucket: str | None = None,
) -> tuple[np.ndarray, ButtonBounds]:
    pane_size = stereo_preview_pane_size(left_frame.shape)
    left_preview = resized_preview_frame(left_frame, pane_size)
    left_preview = draw_position_bucket_overlay(left_preview, bucket_counts or {}, position_bins, current_bucket)
    right_preview = resized_preview_frame(right_frame, pane_size)
    left_display_points = scaled_points(left_points, left_frame.shape, pane_size)
    right_display_points = scaled_points(right_points, right_frame.shape, pane_size)
    if left_display_points:
        left_preview = draw_detection_points(left_preview, left_display_points)
    if right_display_points:
        right_preview = draw_detection_points(right_preview, right_display_points)
    left_preview = draw_camera_label(left_preview, "LEFT")
    right_preview = draw_camera_label(right_preview, "RIGHT")
    preview = np.hstack([left_preview, right_preview])
    cv2.line(preview, (pane_size[0], 0), (pane_size[0], preview.shape[0]), (245, 245, 245), 2, cv2.LINE_AA)
    preview = draw_status_overlay(preview, lines)
    button_bounds = calibrate_button_bounds(preview.shape)
    preview = draw_calibrate_button(preview, button_bounds, calibrate_enabled)
    return preview, button_bounds


def draw_position_bucket_overlay(
    frame: np.ndarray,
    bucket_counts: dict[str, int],
    position_bins: tuple[int, int],
    current_bucket: str | None,
) -> np.ndarray:
    output = frame.copy()
    height, width = int(output.shape[0]), int(output.shape[1])
    x_bins = max(1, int(position_bins[0]))
    y_bins = max(1, int(position_bins[1]))
    for bucket, count in bucket_counts.items():
        if count <= 0:
            continue
        cell = position_bucket_cell(bucket)
        if cell is None:
            continue
        x_index, y_index = cell
        if not (0 <= x_index < x_bins and 0 <= y_index < y_bins):
            continue
        x0, y0, x1, y1 = position_bucket_bounds(width, height, x_bins, y_bins, x_index, y_index)
        layer = output.copy()
        alpha = min(0.46, 0.12 + 0.07 * int(count))
        cv2.rectangle(layer, (x0, y0), (x1, y1), (0, 0, 0), thickness=-1)
        output = cv2.addWeighted(layer, alpha, output, 1.0 - alpha, 0.0)
    grid_layer = output.copy()
    for x_index in range(1, x_bins):
        x = int(round(width * x_index / x_bins))
        cv2.line(grid_layer, (x, 0), (x, height), (235, 235, 235), thickness=1, lineType=cv2.LINE_AA)
    for y_index in range(1, y_bins):
        y = int(round(height * y_index / y_bins))
        cv2.line(grid_layer, (0, y), (width, y), (235, 235, 235), thickness=1, lineType=cv2.LINE_AA)
    output = cv2.addWeighted(grid_layer, 0.18, output, 0.82, 0.0)
    current_cell = position_bucket_cell(current_bucket)
    if current_cell is not None:
        x_index, y_index = current_cell
        if 0 <= x_index < x_bins and 0 <= y_index < y_bins:
            x0, y0, x1, y1 = position_bucket_bounds(width, height, x_bins, y_bins, x_index, y_index)
            cv2.rectangle(output, (x0 + 2, y0 + 2), (x1 - 2, y1 - 2), (80, 220, 255), thickness=3, lineType=cv2.LINE_AA)
    return output


def position_bucket_cell(bucket: str | None) -> tuple[int, int] | None:
    if bucket is None:
        return None
    parts = bucket.split(":")
    if len(parts) != 2 or not parts[0].startswith("x") or not parts[1].startswith("y"):
        return None
    try:
        return int(parts[0][1:]), int(parts[1][1:])
    except ValueError:
        return None


def position_bucket_bounds(width: int, height: int, x_bins: int, y_bins: int, x_index: int, y_index: int) -> tuple[int, int, int, int]:
    x0 = int(round(width * x_index / x_bins))
    y0 = int(round(height * y_index / y_bins))
    x1 = int(round(width * (x_index + 1) / x_bins))
    y1 = int(round(height * (y_index + 1) / y_bins))
    return x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)


def preview_status_lines(
    *,
    target_id: str,
    saved_count: int,
    target_count: int,
    total_frame_count: int,
    qualified_frame_count: int,
    quality: AutoCaptureQuality,
    status: str,
    ready: bool,
    dwell_seconds: float,
    dwell_capture_s: float,
) -> list[str]:
    return [
        f"target={target_id}",
        f"saved={saved_count:02d} target={target_count:02d} total={total_frame_count} qualified={qualified_frame_count}",
        f"corners={quality.corner_count}/{quality.required_corners} status={status}",
        f"mean={quality.mean_gray:.1f} sharp={quality.sharpness:.1f} pos={quality.position_bucket or '-'} "
        f"stable={quality.stable_frame_count} dwell={dwell_seconds:.1f}/{dwell_capture_s:.1f}s",
        "move board through image buckets; hold steady; space=save; c/click=calibrate; q/esc=finish"
        if not ready
        else "READY: c/click=calibrate; keep collecting or q/esc=finish",
    ]


def stereo_preview_status_lines(
    *,
    target_id: str,
    saved_count: int,
    target_count: int,
    total_pair_frame_count: int,
    qualified_pair_count: int,
    left_quality: AutoCaptureQuality,
    right_quality: AutoCaptureQuality,
    status: str,
    ready: bool,
    dwell_seconds: float,
    dwell_capture_s: float,
) -> list[str]:
    return [
        f"target={target_id}",
        f"pairs={saved_count:02d}/{target_count:02d} total={total_pair_frame_count} qualified={qualified_pair_count}",
        f"L corners={left_quality.corner_count}/{left_quality.required_corners} "
        f"R corners={right_quality.corner_count}/{right_quality.required_corners} status={status}",
        f"L sharp={left_quality.sharpness:.1f} R sharp={right_quality.sharpness:.1f} "
        f"pos={left_quality.position_bucket or '-'} stable={min(left_quality.stable_frame_count, right_quality.stable_frame_count)} "
        f"dwell={dwell_seconds:.1f}/{dwell_capture_s:.1f}s",
        "move board through left-image buckets; hold steady; space=save pair; c/click=calibrate; q/esc=finish"
        if not ready
        else "READY: c/click=calibrate; keep collecting pairs or q/esc=finish",
    ]


def status_line_for_quality(
    quality: AutoCaptureQuality,
    auto_saved: bool,
    bucket_count: int = 0,
    max_views_per_bucket: int = 0,
    same_bucket_as_last_capture: bool = False,
    dwell_seconds: float = 0.0,
    dwell_capture_s: float = 0.0,
) -> str:
    if auto_saved:
        return "auto-saved"
    if not quality.accepted:
        return quality.reason
    if bucket_count < max_views_per_bucket and not same_bucket_as_last_capture:
        return "accepted; waiting interval"
    remaining = max(0.0, dwell_capture_s - dwell_seconds)
    return f"accepted; hold {remaining:.1f}s or move"


def status_line_for_stereo_quality(
    quality: AutoCaptureQuality,
    auto_saved: bool,
    bucket_count: int = 0,
    max_views_per_bucket: int = 0,
    same_bucket_as_last_capture: bool = False,
    dwell_seconds: float = 0.0,
    dwell_capture_s: float = 0.0,
) -> str:
    if auto_saved:
        return "auto-saved stereo pair"
    if not quality.accepted:
        return quality.reason
    if bucket_count < max_views_per_bucket and not same_bucket_as_last_capture:
        return "accepted pair; waiting interval"
    remaining = max(0.0, dwell_capture_s - dwell_seconds)
    return f"accepted pair; hold {remaining:.1f}s or move"


def scaled_points(points: tuple[tuple[float, float], ...], frame_shape: tuple[int, ...], display_size: tuple[int, int]) -> tuple[tuple[float, float], ...]:
    if not points:
        return ()
    source_height, source_width = int(frame_shape[0]), int(frame_shape[1])
    display_width, display_height = display_size
    scale_x = display_width / source_width
    scale_y = display_height / source_height
    return tuple((float(x) * scale_x, float(y) * scale_y) for x, y in points)


def draw_status_overlay(frame: np.ndarray, lines: list[str]) -> np.ndarray:
    output = frame.copy()
    for index, line in enumerate(lines):
        origin = (16, 28 + 26 * index)
        cv2.putText(output, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), thickness=5, lineType=cv2.LINE_AA)
        cv2.putText(output, line, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), thickness=2, lineType=cv2.LINE_AA)
    return output


def draw_detection_points(frame: np.ndarray, points: tuple[tuple[float, float], ...]) -> np.ndarray:
    output = frame.copy()
    for index, (x, y) in enumerate(points):
        color = ((37 * index) % 255, (149 + 19 * index) % 255, (230 - 11 * index) % 255)
        center = (int(round(x)), int(round(y)))
        cv2.circle(output, center, 5, color, thickness=-1, lineType=cv2.LINE_AA)
        cv2.circle(output, center, 7, (255, 255, 255), thickness=1, lineType=cv2.LINE_AA)
    return output


def calibrate_button_bounds(frame_shape: tuple[int, ...]) -> ButtonBounds:
    height, width = int(frame_shape[0]), int(frame_shape[1])
    button_width = min(220, max(160, width // 5))
    button_height = 54
    margin = 18
    return width - button_width - margin, height - button_height - margin, width - margin, height - margin


def draw_calibrate_button(frame: np.ndarray, bounds: ButtonBounds, enabled: bool) -> np.ndarray:
    output = frame.copy()
    x0, y0, x1, y1 = bounds
    fill = (36, 130, 72) if enabled else (65, 65, 65)
    border = (220, 255, 230) if enabled else (150, 150, 150)
    label = "Calibrate" if enabled else "Collecting"
    cv2.rectangle(output, (x0, y0), (x1, y1), fill, thickness=-1)
    cv2.rectangle(output, (x0, y0), (x1, y1), border, thickness=2)
    text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.72, 2)
    tx = x0 + max(8, (x1 - x0 - text_size[0]) // 2)
    ty = y0 + max(text_size[1] + 4, (y1 - y0 + text_size[1]) // 2)
    cv2.putText(output, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 245, 245), 2, cv2.LINE_AA)
    return output


def stereo_preview_pane_size(frame_shape: tuple[int, ...]) -> tuple[int, int]:
    source_height, source_width = int(frame_shape[0]), int(frame_shape[1])
    max_total_width = 1280
    max_height = 720
    pane_width = min(max_total_width // 2, max(1, source_width))
    pane_height = max(1, int(round(source_height * pane_width / max(1, source_width))))
    if pane_height > max_height:
        pane_height = max_height
        pane_width = max(1, int(round(source_width * pane_height / max(1, source_height))))
    return pane_width, pane_height


def draw_camera_label(frame: np.ndarray, label: str) -> np.ndarray:
    output = frame.copy()
    cv2.putText(output, label, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(output, label, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 245, 245), 2, cv2.LINE_AA)
    return output
