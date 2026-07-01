from __future__ import annotations

import math

import cv2
import numpy as np

from .types import BallDetection, StereoBallMatch, StereoMatchDiagnostics


def render_gui(
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    left_detections: list[BallDetection],
    right_detections: list[BallDetection],
    match: StereoBallMatch | None,
    diagnostics: StereoMatchDiagnostics,
    *,
    fps: float,
    frame_id: int,
    display_camera_width: int,
    plot_depth_m: float,
    plot_x_m: float,
) -> np.ndarray:
    left_overlay = left_frame.copy()
    right_overlay = right_frame.copy()
    draw_detections(left_overlay, left_detections, selected=match.left_detection if match else None)
    draw_detections(right_overlay, right_detections, selected=match.right_detection if match else None)

    left_display = resize_to_width(left_overlay, display_camera_width)
    right_display = resize_to_width(right_overlay, display_camera_width)
    if right_display.shape[0] != left_display.shape[0]:
        right_display = cv2.resize(
            right_display,
            (right_display.shape[1], left_display.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
    panel = render_position_panel(
        height=left_display.shape[0],
        width=440,
        match=match,
        diagnostics=diagnostics,
        fps=fps,
        frame_id=frame_id,
        left_count=len(left_detections),
        right_count=len(right_detections),
        plot_depth_m=plot_depth_m,
        plot_x_m=plot_x_m,
    )
    return np.hstack([left_display, right_display, panel])


def draw_detections(frame: np.ndarray, detections: list[BallDetection], *, selected: BallDetection | None) -> None:
    for detection in detections:
        color = (80, 220, 255)
        thickness = 2
        if selected is detection:
            color = (80, 255, 80)
            thickness = 3
        x1, y1, x2, y2 = (int(round(v)) for v in (detection.x1, detection.y1, detection.x2, detection.y2))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
        cv2.circle(frame, (int(round(detection.x)), int(round(detection.y))), 4, color, -1)
        put(frame, f"{detection.confidence:.2f}", x1, max(18, y1 - 6), 0.65, color, 2)


def render_position_panel(
    *,
    height: int,
    width: int,
    match: StereoBallMatch | None,
    diagnostics: StereoMatchDiagnostics,
    fps: float,
    frame_id: int,
    left_count: int,
    right_count: int,
    plot_depth_m: float,
    plot_x_m: float,
) -> np.ndarray:
    panel = np.full((height, width, 3), (24, 28, 32), dtype=np.uint8)
    text = (235, 240, 245)
    muted = (160, 170, 180)
    green = (90, 230, 130)
    yellow = (70, 210, 255)

    put(panel, "Stereo Ball", 18, 36, 0.85, text, 2)
    put(panel, f"frame {frame_id}   {fps:.1f} fps", 18, 68, 0.58, muted, 1)
    put(panel, f"detections L/R: {left_count}/{right_count}", 18, 94, 0.58, muted, 1)
    put(panel, "camera frame: x right, y down, z forward", 18, 122, 0.46, muted, 1)

    if match is None:
        put(panel, "No stereo match", 18, 170, 0.78, yellow, 2)
        put(panel, f"evaluated: {diagnostics.evaluated_candidate_count}", 18, 210, 0.54, muted, 1)
        put(panel, f"epipolar rejected: {diagnostics.rejected_by_epipolar_count}", 18, 236, 0.54, muted, 1)
        put(panel, f"disparity rejected: {diagnostics.rejected_by_disparity_count}", 18, 262, 0.54, muted, 1)
        put(panel, f"depth rejected: {diagnostics.rejected_by_depth_count}", 18, 288, 0.54, muted, 1)
        return panel

    x, y, z = (float(v) for v in match.point_3d_m)
    distance = math.sqrt(x * x + y * y + z * z)
    put(panel, f"x: {x:+.3f} m", 18, 166, 0.76, green, 2)
    put(panel, f"y: {y:+.3f} m", 18, 200, 0.76, green, 2)
    put(panel, f"z: {z:+.3f} m", 18, 234, 0.76, green, 2)
    put(panel, f"range: {distance:.3f} m", 18, 268, 0.64, text, 1)
    put(panel, f"disp: {match.disparity_px:.2f} px", 18, 296, 0.56, muted, 1)
    put(panel, f"epi: {match.epipolar_error_px:.2f} px", 18, 322, 0.56, muted, 1)
    put(panel, f"reproj: {match.reprojection_error_px:.2f} px", 18, 348, 0.56, muted, 1)
    put(panel, f"conf: {match.confidence:.2f}  cost: {match.cost:.2f}", 18, 374, 0.56, muted, 1)
    draw_xz_plot(panel, match.point_3d_m, plot_depth_m=plot_depth_m, plot_x_m=plot_x_m)
    return panel


def draw_xz_plot(panel: np.ndarray, point: np.ndarray, *, plot_depth_m: float, plot_x_m: float) -> None:
    left, top = 46, 410
    right, bottom = panel.shape[1] - 34, panel.shape[0] - 36
    if bottom <= top + 40:
        return

    cv2.rectangle(panel, (left, top), (right, bottom), (72, 80, 88), 1)
    center_x = (left + right) // 2
    cv2.line(panel, (center_x, top), (center_x, bottom), (72, 80, 88), 1)
    cv2.line(panel, (left, bottom), (right, bottom), (72, 80, 88), 1)
    put(panel, "X/Z meters", left, top - 14, 0.48, (160, 170, 180), 1)
    put(panel, f"{plot_depth_m:.0f}m", right - 42, top + 18, 0.42, (125, 135, 145), 1)
    put(panel, "0m", right - 30, bottom - 8, 0.42, (125, 135, 145), 1)

    x = float(np.clip(point[0], -plot_x_m, plot_x_m))
    z = float(np.clip(point[2], 0.0, plot_depth_m))
    px = int(round(center_x + (x / plot_x_m) * ((right - left) * 0.5)))
    py = int(round(bottom - (z / plot_depth_m) * (bottom - top)))
    cv2.circle(panel, (px, py), 8, (90, 230, 130), -1)
    cv2.circle(panel, (px, py), 12, (90, 230, 130), 1)


def resize_to_width(frame: np.ndarray, width: int) -> np.ndarray:
    if frame.shape[1] == width:
        return frame
    scale = width / frame.shape[1]
    height = max(1, int(round(frame.shape[0] * scale)))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def put(
    image: np.ndarray,
    text: str,
    x: int,
    y: int,
    scale: float,
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)
