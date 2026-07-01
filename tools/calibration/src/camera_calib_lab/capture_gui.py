from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from pathlib import Path
from time import monotonic
from typing import Any

import cv2

from camera_calib_lab.capture_artifacts import (
    mono_manifest,
    mono_session_json,
    save_mono_frame,
    save_stereo_pair,
    stereo_manifest,
    stereo_session_json,
    write_mono_summary,
    write_stereo_summary,
)
from camera_calib_lab.capture_overlay import (
    charuco_auto_preview_frame,
    preview_status_lines,
    status_line_for_quality,
    status_line_for_stereo_quality,
    stereo_charuco_preview_frame,
    stereo_preview_status_lines,
)
from camera_calib_lab.capture_quality import (
    AutoCaptureQuality,
    evaluate_frame_quality,
    quality_with_stability,
    required_charuco_corners,
    should_auto_capture,
    stereo_pair_quality,
)
from camera_calib_lab.capture_types import (
    CaptureConfig,
    OpenCVCamera,
    ToolConfig,
    fresh_output_dir,
    load_config,
    write_json,
)
from camera_calib_lab.charuco_detection import create_charuco_board, create_detector, detect_charuco
from camera_calib_lab.v4l2_controls import v4l2_controls_snapshot


QUIT_KEYS = {27, ord("q"), ord("Q")}
CAPTURE_KEY = ord(" ")
CALIBRATE_KEYS = {ord("c"), ord("C")}


def run_mono_charuco_gui(
    *,
    config_path: Path,
    output_path: Path,
    calibration_output: Path | None,
    views: int,
    device: str | int,
    camera_id: str | None = None,
) -> dict[str, Any]:
    config = capture_config_with_options(load_config(config_path), views, camera_id=camera_id)
    output = fresh_output_dir(output_path)
    output.mkdir(parents=True, exist_ok=True)
    board = create_charuco_board(config.target)
    detector = create_detector(board)
    source = OpenCVCamera(device or 0, config.camera)
    v4l2_controls = v4l2_controls_snapshot(device or 0)
    records: list[dict[str, Any]] = []
    bucket_counts: dict[str, int] = defaultdict(int)
    recent_qualities: deque[AutoCaptureQuality] = deque(maxlen=max(1, int(config.capture.stability_frames) - 1))
    last_capture_at = -1.0e9
    last_capture_bucket: str | None = None
    active_bucket: str | None = None
    active_bucket_since = 0.0
    total_frame_count = 0
    qualified_frame_count = 0
    required_corners = required_charuco_corners(config.target, config.capture)
    window_name = "CameraCalibLab ChArUco Auto Capture"
    mouse_state = mouse_state_dict()
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    install_mouse_callback(window_name, mouse_state)
    try:
        while True:
            frame = source.read()
            detection = detect_charuco(frame, board, detector)
            base_quality = evaluate_frame_quality(
                frame=frame,
                detection=detection,
                required_corners=required_corners,
                min_sharpness=config.capture.min_sharpness,
                position_bins=(config.capture.position_bins_x, config.capture.position_bins_y),
            )
            frame_quality = quality_with_stability(
                base_quality,
                tuple(recent_qualities),
                config.capture.stability_frames,
                config.capture.stable_center_delta,
                config.capture.stable_area_delta,
            )
            now = monotonic()
            total_frame_count += 1
            dwell_seconds = 0.0
            if frame_quality.accepted and frame_quality.position_bucket is not None:
                if active_bucket != frame_quality.position_bucket:
                    active_bucket = frame_quality.position_bucket
                    active_bucket_since = now
                dwell_seconds = max(0.0, now - active_bucket_since)
                qualified_frame_count += 1
            else:
                active_bucket = None
                active_bucket_since = now
            ready = len(records) >= config.capture.views
            auto_saved = False
            if should_auto_capture(
                frame_quality,
                bucket_counts,
                now,
                last_capture_at,
                config.capture.min_capture_interval_s,
                config.capture.max_views_per_bucket,
                last_capture_bucket=last_capture_bucket,
                dwell_seconds=dwell_seconds,
                dwell_capture_s=config.capture.dwell_capture_s,
            ):
                records.append(save_mono_frame(output, frame, detection, frame_quality, config.camera.camera_id, len(records)))
                bucket_counts[str(frame_quality.position_bucket)] += 1
                last_capture_at = now
                last_capture_bucket = str(frame_quality.position_bucket)
                active_bucket_since = now
                dwell_seconds = 0.0
                auto_saved = True
                ready = len(records) >= config.capture.views
            status = status_line_for_quality(
                frame_quality,
                auto_saved=auto_saved,
                bucket_count=bucket_counts.get(str(frame_quality.position_bucket), 0) if frame_quality.position_bucket else 0,
                max_views_per_bucket=config.capture.max_views_per_bucket,
                same_bucket_as_last_capture=frame_quality.position_bucket == last_capture_bucket,
                dwell_seconds=dwell_seconds,
                dwell_capture_s=config.capture.dwell_capture_s,
            )
            preview, button_bounds = charuco_auto_preview_frame(
                frame,
                detection.points,
                preview_status_lines(
                    target_id=config.target.profile,
                    saved_count=len(records),
                    target_count=config.capture.views,
                    total_frame_count=total_frame_count,
                    qualified_frame_count=qualified_frame_count,
                    quality=frame_quality,
                    status=status,
                    ready=ready,
                    dwell_seconds=dwell_seconds,
                    dwell_capture_s=config.capture.dwell_capture_s,
                ),
                ready,
                bucket_counts,
                (config.capture.position_bins_x, config.capture.position_bins_y),
                frame_quality.position_bucket,
            )
            mouse_state["bounds"] = button_bounds
            mouse_state["enabled"] = ready
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(30) & 0xFF
            recent_qualities.append(base_quality)
            if key in QUIT_KEYS:
                break
            if ready and (key in CALIBRATE_KEYS or bool(mouse_state["clicked"])):
                mouse_state["clicked"] = True
                break
            if key == CAPTURE_KEY and frame_quality.accepted and not auto_saved:
                records.append(save_mono_frame(output, frame, detection, frame_quality, config.camera.camera_id, len(records), manual=True))
                if frame_quality.position_bucket is not None:
                    bucket_counts[str(frame_quality.position_bucket)] += 1
                    last_capture_bucket = str(frame_quality.position_bucket)
                last_capture_at = now
                active_bucket_since = now
    finally:
        source.release()
        destroy_window(window_name)
    manifest = mono_manifest(
        output=output,
        config=config,
        device=device,
        v4l2_controls=v4l2_controls,
        records=records,
        bucket_counts=dict(bucket_counts),
        total_frame_count=total_frame_count,
        qualified_frame_count=qualified_frame_count,
        calibrate_requested=bool(len(records) >= config.capture.views and mouse_state["clicked"]),
        calibration_output=calibration_output,
    )
    write_json(output / "session.json", mono_session_json(output, config, device, records, v4l2_controls))
    write_json(output / "manifest.json", manifest)
    write_mono_summary(output / "summary.md", manifest)
    write_json(output / "auto_gui_result.json", manifest)
    return manifest


def run_stereo_charuco_gui(
    *,
    config_path: Path,
    output_path: Path,
    calibration_output: Path | None,
    views: int,
    left_device: str | int,
    right_device: str | int,
) -> dict[str, Any]:
    config = capture_config_with_options(load_config(config_path), views, camera_id=None)
    output = fresh_output_dir(output_path)
    output.mkdir(parents=True, exist_ok=True)
    board = create_charuco_board(config.target)
    detector = create_detector(board)
    left_source = OpenCVCamera(left_device or 0, config.camera)
    right_source = OpenCVCamera(right_device or 1, config.camera)
    left_v4l2_controls = v4l2_controls_snapshot(left_device or 0)
    right_v4l2_controls = v4l2_controls_snapshot(right_device or 1)
    pair_records: list[dict[str, Any]] = []
    bucket_counts: dict[str, int] = defaultdict(int)
    recent_left: deque[AutoCaptureQuality] = deque(maxlen=max(1, int(config.capture.stability_frames) - 1))
    recent_right: deque[AutoCaptureQuality] = deque(maxlen=max(1, int(config.capture.stability_frames) - 1))
    last_capture_at = -1.0e9
    last_capture_bucket: str | None = None
    active_bucket: str | None = None
    active_bucket_since = 0.0
    total_pair_frame_count = 0
    qualified_pair_count = 0
    required_corners = required_charuco_corners(config.target, config.capture)
    window_name = "CameraCalibLab Stereo ChArUco Auto Capture"
    mouse_state = mouse_state_dict()
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    install_mouse_callback(window_name, mouse_state)
    try:
        while True:
            left_frame = left_source.read()
            right_frame = right_source.read()
            left_detection = detect_charuco(left_frame, board, detector)
            right_detection = detect_charuco(right_frame, board, detector)
            left_base = evaluate_frame_quality(
                frame=left_frame,
                detection=left_detection,
                required_corners=required_corners,
                min_sharpness=config.capture.min_sharpness,
                position_bins=(config.capture.position_bins_x, config.capture.position_bins_y),
            )
            right_base = evaluate_frame_quality(
                frame=right_frame,
                detection=right_detection,
                required_corners=required_corners,
                min_sharpness=config.capture.min_sharpness,
                position_bins=(config.capture.position_bins_x, config.capture.position_bins_y),
            )
            left_quality = quality_with_stability(
                left_base,
                tuple(recent_left),
                config.capture.stability_frames,
                config.capture.stable_center_delta,
                config.capture.stable_area_delta,
            )
            right_quality = quality_with_stability(
                right_base,
                tuple(recent_right),
                config.capture.stability_frames,
                config.capture.stable_center_delta,
                config.capture.stable_area_delta,
            )
            pair_quality = stereo_pair_quality(left_quality, right_quality)
            now = monotonic()
            total_pair_frame_count += 1
            dwell_seconds = 0.0
            if pair_quality.accepted and pair_quality.position_bucket is not None:
                if active_bucket != pair_quality.position_bucket:
                    active_bucket = pair_quality.position_bucket
                    active_bucket_since = now
                dwell_seconds = max(0.0, now - active_bucket_since)
                qualified_pair_count += 1
            else:
                active_bucket = None
                active_bucket_since = now
            ready = len(pair_records) >= config.capture.views
            auto_saved = False
            if should_auto_capture(
                pair_quality,
                bucket_counts,
                now,
                last_capture_at,
                config.capture.min_capture_interval_s,
                config.capture.max_views_per_bucket,
                last_capture_bucket=last_capture_bucket,
                dwell_seconds=dwell_seconds,
                dwell_capture_s=config.capture.dwell_capture_s,
            ):
                pair_records.append(save_stereo_pair(output, left_frame, right_frame, left_detection, right_detection, left_quality, right_quality, len(pair_records)))
                bucket_counts[str(pair_quality.position_bucket)] += 1
                last_capture_at = now
                last_capture_bucket = str(pair_quality.position_bucket)
                active_bucket_since = now
                dwell_seconds = 0.0
                auto_saved = True
                ready = len(pair_records) >= config.capture.views
            status = status_line_for_stereo_quality(
                pair_quality,
                auto_saved=auto_saved,
                bucket_count=bucket_counts.get(str(pair_quality.position_bucket), 0) if pair_quality.position_bucket else 0,
                max_views_per_bucket=config.capture.max_views_per_bucket,
                same_bucket_as_last_capture=pair_quality.position_bucket == last_capture_bucket,
                dwell_seconds=dwell_seconds,
                dwell_capture_s=config.capture.dwell_capture_s,
            )
            preview, button_bounds = stereo_charuco_preview_frame(
                left_frame=left_frame,
                right_frame=right_frame,
                left_points=left_detection.points,
                right_points=right_detection.points,
                lines=stereo_preview_status_lines(
                    target_id=config.target.profile,
                    saved_count=len(pair_records),
                    target_count=config.capture.views,
                    total_pair_frame_count=total_pair_frame_count,
                    qualified_pair_count=qualified_pair_count,
                    left_quality=left_quality,
                    right_quality=right_quality,
                    status=status,
                    ready=ready,
                    dwell_seconds=dwell_seconds,
                    dwell_capture_s=config.capture.dwell_capture_s,
                ),
                calibrate_enabled=ready,
                bucket_counts=dict(bucket_counts),
                position_bins=(config.capture.position_bins_x, config.capture.position_bins_y),
                current_bucket=pair_quality.position_bucket,
            )
            mouse_state["bounds"] = button_bounds
            mouse_state["enabled"] = ready
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(30) & 0xFF
            recent_left.append(left_base)
            recent_right.append(right_base)
            if key in QUIT_KEYS:
                break
            if ready and (key in CALIBRATE_KEYS or bool(mouse_state["clicked"])):
                mouse_state["clicked"] = True
                break
            if key == CAPTURE_KEY and pair_quality.accepted and not auto_saved:
                pair_records.append(
                    save_stereo_pair(
                        output,
                        left_frame,
                        right_frame,
                        left_detection,
                        right_detection,
                        left_quality,
                        right_quality,
                        len(pair_records),
                        manual=True,
                    )
                )
                if pair_quality.position_bucket is not None:
                    bucket_counts[str(pair_quality.position_bucket)] += 1
                    last_capture_bucket = str(pair_quality.position_bucket)
                last_capture_at = now
                active_bucket_since = now
    finally:
        left_source.release()
        right_source.release()
        destroy_window(window_name)
    manifest = stereo_manifest(
        output=output,
        config=config,
        left_device=left_device,
        right_device=right_device,
        left_v4l2_controls=left_v4l2_controls,
        right_v4l2_controls=right_v4l2_controls,
        pair_records=pair_records,
        bucket_counts=dict(bucket_counts),
        total_pair_frame_count=total_pair_frame_count,
        qualified_pair_count=qualified_pair_count,
        calibrate_requested=bool(len(pair_records) >= config.capture.views and mouse_state["clicked"]),
        calibration_output=calibration_output,
    )
    write_json(
        output / "session.json",
        stereo_session_json(
            output,
            config,
            left_device,
            right_device,
            pair_records,
            left_v4l2_controls,
            right_v4l2_controls,
        ),
    )
    write_json(output / "manifest.json", manifest)
    write_stereo_summary(output / "summary.md", manifest)
    write_json(output / "auto_gui_result.json", manifest)
    return manifest


def capture_config_with_options(config: ToolConfig, views: int, *, camera_id: str | None) -> ToolConfig:
    capture = config.capture if views <= 0 or views == config.capture.views else capture_config_with_views(config.capture, views)
    camera = config.camera if camera_id in {None, ""} else replace(config.camera, camera_id=str(camera_id))
    if capture is config.capture and camera is config.camera:
        return config
    return ToolConfig(target=config.target, camera=camera, capture=capture)


def capture_config_with_views(capture: CaptureConfig, views: int) -> CaptureConfig:
    return CaptureConfig(
        views=int(views),
        min_corners=capture.min_corners,
        min_corner_coverage=capture.min_corner_coverage,
        min_sharpness=capture.min_sharpness,
        min_capture_interval_s=capture.min_capture_interval_s,
        max_views_per_bucket=capture.max_views_per_bucket,
        position_bins_x=capture.position_bins_x,
        position_bins_y=capture.position_bins_y,
        stability_frames=capture.stability_frames,
        stable_center_delta=capture.stable_center_delta,
        stable_area_delta=capture.stable_area_delta,
        dwell_capture_s=capture.dwell_capture_s,
    )


def mouse_state_dict() -> dict[str, Any]:
    return {"clicked": False, "enabled": False, "bounds": None}


def install_mouse_callback(window_name: str, state: dict[str, Any]) -> None:
    def handle_mouse(event: int, x: int, y: int, _flags: int, _userdata: Any) -> None:
        bounds = state.get("bounds")
        if event != cv2.EVENT_LBUTTONDOWN or not state.get("enabled") or bounds is None:
            return
        x0, y0, x1, y1 = bounds
        if x0 <= x <= x1 and y0 <= y <= y1:
            state["clicked"] = True

    try:
        cv2.setMouseCallback(window_name, handle_mouse)
    except cv2.error:
        return


def destroy_window(window_name: str) -> None:
    try:
        cv2.destroyWindow(window_name)
    except cv2.error:
        return
