from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

import cv2
import numpy as np
import yaml


LEFT_CAMERA_ID = "left"
RIGHT_CAMERA_ID = "right"
IMAGE_NAME = "image.png"


@dataclass(frozen=True)
class TargetConfig:
    profile: str = "dfoptix_charuco_14x9_square15mm_marker11_25mm"
    squares_x: int = 14
    squares_y: int = 9
    dictionary: str = "DICT_5X5_100"
    square_size_m: float = 0.015
    marker_size_m: float = 0.01125


@dataclass(frozen=True)
class CameraConfig:
    width_px: int = 1280
    height_px: int = 720
    fps: float = 30.0
    fourcc: str = "MJPG"


@dataclass(frozen=True)
class CaptureConfig:
    views: int = 30
    min_corners: int = 24
    min_sharpness: float = 30.0
    min_capture_interval_s: float = 0.6


@dataclass(frozen=True)
class ToolConfig:
    target: TargetConfig
    camera: CameraConfig
    capture: CaptureConfig


@dataclass(frozen=True)
class CharucoDetection:
    corners: np.ndarray | None
    ids: np.ndarray | None
    count: int
    mean_gray: float
    sharpness: float

    @property
    def accepted(self) -> bool:
        return self.count > 0


class OpenCVCamera:
    def __init__(self, device: str | int, config: CameraConfig) -> None:
        self.device = parse_device(device)
        self.capture = cv2.VideoCapture(self.device)
        if not self.capture.isOpened():
            raise RuntimeError(f"failed to open camera device: {device}")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(config.width_px))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(config.height_px))
        self.capture.set(cv2.CAP_PROP_FPS, float(config.fps))
        if config.fourcc:
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.fourcc[:4]))

    def read(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"failed to read frame from camera device: {self.device}")
        return frame

    def release(self) -> None:
        self.capture.release()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_device(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    return int(value) if value.isdigit() else value


def load_config(path: Path) -> ToolConfig:
    payload: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    camera = payload.get("camera") if isinstance(payload.get("camera"), dict) else {}
    capture = payload.get("capture") if isinstance(payload.get("capture"), dict) else {}
    return ToolConfig(
        target=TargetConfig(
            profile=str(target.get("profile", TargetConfig.profile)),
            squares_x=int(target.get("squares_x", TargetConfig.squares_x)),
            squares_y=int(target.get("squares_y", TargetConfig.squares_y)),
            dictionary=str(target.get("dictionary", TargetConfig.dictionary)),
            square_size_m=float(target.get("square_size_m", TargetConfig.square_size_m)),
            marker_size_m=float(target.get("marker_size_m", TargetConfig.marker_size_m)),
        ),
        camera=CameraConfig(
            width_px=int(camera.get("width_px", CameraConfig.width_px)),
            height_px=int(camera.get("height_px", CameraConfig.height_px)),
            fps=float(camera.get("fps", CameraConfig.fps)),
            fourcc=str(camera.get("fourcc", CameraConfig.fourcc)),
        ),
        capture=CaptureConfig(
            views=int(capture.get("views", CaptureConfig.views)),
            min_corners=int(capture.get("min_corners", CaptureConfig.min_corners)),
            min_sharpness=float(capture.get("min_sharpness", CaptureConfig.min_sharpness)),
            min_capture_interval_s=float(capture.get("min_capture_interval_s", CaptureConfig.min_capture_interval_s)),
        ),
    )


def create_charuco_board(target: TargetConfig) -> cv2.aruco.CharucoBoard:
    dictionary_id = getattr(cv2.aruco, target.dictionary)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    try:
        return cv2.aruco.CharucoBoard(
            (target.squares_x, target.squares_y),
            target.square_size_m,
            target.marker_size_m,
            dictionary,
        )
    except TypeError:
        return cv2.aruco.CharucoBoard_create(
            target.squares_x,
            target.squares_y,
            target.square_size_m,
            target.marker_size_m,
            dictionary,
        )


def create_detector(board: cv2.aruco.CharucoBoard) -> Any:
    if hasattr(cv2.aruco, "CharucoDetector"):
        return cv2.aruco.CharucoDetector(board)
    return None


def detect_charuco(frame: np.ndarray, board: cv2.aruco.CharucoBoard, detector: Any) -> CharucoDetection:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_gray = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    corners = None
    ids = None
    if detector is not None:
        result = detector.detectBoard(gray)
        corners = result[0] if len(result) > 0 else None
        ids = result[1] if len(result) > 1 else None
    else:
        marker_corners, marker_ids, _rejected = cv2.aruco.detectMarkers(gray, board.getDictionary())
        if marker_ids is not None and len(marker_ids) > 0:
            _count, corners, ids = cv2.aruco.interpolateCornersCharuco(marker_corners, marker_ids, gray, board)
    count = 0 if ids is None else int(len(ids))
    return CharucoDetection(corners=corners, ids=ids, count=count, mean_gray=mean_gray, sharpness=sharpness)


def detection_is_accepted(detection: CharucoDetection, capture: CaptureConfig) -> bool:
    return detection.count >= capture.min_corners and detection.sharpness >= capture.min_sharpness


def fresh_output_dir(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    for index in range(1, 1000):
        suffix = stamp if index == 1 else f"{stamp}_{index:02d}"
        candidate = path.with_name(f"{path.name}_{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate fresh output directory for {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preview_size(frame: np.ndarray, max_width: int = 960) -> tuple[int, int]:
    height, width = frame.shape[:2]
    if width <= max_width:
        return width, height
    scale = max_width / float(width)
    return max_width, max(1, int(height * scale))


def draw_preview(
    frame: np.ndarray,
    detection: CharucoDetection,
    *,
    saved: int,
    target: int,
    accepted: bool,
    label: str,
) -> np.ndarray:
    preview = frame.copy()
    if detection.corners is not None and detection.ids is not None and len(detection.ids) > 0:
        cv2.aruco.drawDetectedCornersCharuco(preview, detection.corners, detection.ids)
    color = (20, 180, 20) if accepted else (20, 20, 220)
    lines = [
        f"{label} saved {saved}/{target}",
        f"corners={detection.count} sharpness={detection.sharpness:.1f} mean={detection.mean_gray:.1f}",
        "space: manual save  c: finish/calibrate request  q/esc: quit",
    ]
    for index, line in enumerate(lines):
        y = 28 + index * 26
        cv2.putText(preview, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    size = preview_size(preview)
    return cv2.resize(preview, size, interpolation=cv2.INTER_AREA)


def save_mono_frame(output: Path, frame: np.ndarray, detection: CharucoDetection, index: int) -> dict[str, Any]:
    view_id = f"view{index + 1:03d}"
    view_dir = output / "cam1" / view_id
    view_dir.mkdir(parents=True, exist_ok=True)
    image_path = view_dir / IMAGE_NAME
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"failed to write {image_path}")
    return {
        "view_id": view_id,
        "camera_id": "cam1",
        "image": image_path.relative_to(output).as_posix(),
        "charuco_corner_count": detection.count,
        "mean_gray": detection.mean_gray,
        "sharpness": detection.sharpness,
    }


def save_stereo_pair(
    output: Path,
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    left_detection: CharucoDetection,
    right_detection: CharucoDetection,
    index: int,
) -> dict[str, Any]:
    view_id = f"view{index + 1:03d}"
    records = {}
    for camera_id, frame, detection in (
        (LEFT_CAMERA_ID, left_frame, left_detection),
        (RIGHT_CAMERA_ID, right_frame, right_detection),
    ):
        view_dir = output / camera_id / view_id
        view_dir.mkdir(parents=True, exist_ok=True)
        image_path = view_dir / IMAGE_NAME
        if not cv2.imwrite(str(image_path), frame):
            raise RuntimeError(f"failed to write {image_path}")
        records[camera_id] = {
            "image": image_path.relative_to(output).as_posix(),
            "charuco_corner_count": detection.count,
            "mean_gray": detection.mean_gray,
            "sharpness": detection.sharpness,
        }
    return {"view_id": view_id, **records}


def run_mono_charuco_gui(
    *,
    config_path: Path,
    output_path: Path,
    calibration_output: Path | None,
    views: int,
    device: str | int,
) -> dict[str, Any]:
    config = load_config(config_path)
    capture_config = CaptureConfig(
        views=views or config.capture.views,
        min_corners=config.capture.min_corners,
        min_sharpness=config.capture.min_sharpness,
        min_capture_interval_s=config.capture.min_capture_interval_s,
    )
    output = fresh_output_dir(output_path)
    output.mkdir(parents=True, exist_ok=True)
    board = create_charuco_board(config.target)
    detector = create_detector(board)
    source = OpenCVCamera(device or 0, config.camera)
    records: list[dict[str, Any]] = []
    calibrate_requested = False
    last_capture = -1.0e9
    window_name = "TennisBot ChArUco Mono Capture"
    try:
        while True:
            frame = source.read()
            detection = detect_charuco(frame, board, detector)
            accepted = detection_is_accepted(detection, capture_config)
            now = monotonic()
            if accepted and len(records) < capture_config.views and now - last_capture >= capture_config.min_capture_interval_s:
                records.append(save_mono_frame(output, frame, detection, len(records)))
                last_capture = now
            cv2.imshow(
                window_name,
                draw_preview(frame, detection, saved=len(records), target=capture_config.views, accepted=accepted, label="mono"),
            )
            key = cv2.waitKey(30) & 0xFF
            if key in {27, ord("q"), ord("Q")}:
                break
            if key == ord(" ") and accepted and len(records) < capture_config.views:
                records.append(save_mono_frame(output, frame, detection, len(records)))
                last_capture = now
            if key in {ord("c"), ord("C")}:
                calibrate_requested = True
                break
            if len(records) >= capture_config.views:
                calibrate_requested = True
                break
    finally:
        source.release()
        cv2.destroyWindow(window_name)
    manifest = session_manifest(
        kind="mono_charuco",
        output=output,
        config=config,
        records=records,
        calibrate_requested=calibrate_requested,
        calibration_output=calibration_output,
    )
    write_json(output / "manifest.json", manifest)
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
    config = load_config(config_path)
    capture_config = CaptureConfig(
        views=views or config.capture.views,
        min_corners=config.capture.min_corners,
        min_sharpness=config.capture.min_sharpness,
        min_capture_interval_s=config.capture.min_capture_interval_s,
    )
    output = fresh_output_dir(output_path)
    output.mkdir(parents=True, exist_ok=True)
    board = create_charuco_board(config.target)
    detector = create_detector(board)
    left_source = OpenCVCamera(left_device or 0, config.camera)
    right_source = OpenCVCamera(right_device or 1, config.camera)
    records: list[dict[str, Any]] = []
    calibrate_requested = False
    last_capture = -1.0e9
    window_name = "TennisBot ChArUco Stereo Capture"
    try:
        while True:
            left_frame = left_source.read()
            right_frame = right_source.read()
            left_detection = detect_charuco(left_frame, board, detector)
            right_detection = detect_charuco(right_frame, board, detector)
            accepted = detection_is_accepted(left_detection, capture_config) and detection_is_accepted(right_detection, capture_config)
            now = monotonic()
            if accepted and len(records) < capture_config.views and now - last_capture >= capture_config.min_capture_interval_s:
                records.append(save_stereo_pair(output, left_frame, right_frame, left_detection, right_detection, len(records)))
                last_capture = now
            left_preview = draw_preview(
                left_frame,
                left_detection,
                saved=len(records),
                target=capture_config.views,
                accepted=accepted,
                label="left",
            )
            right_preview = draw_preview(
                right_frame,
                right_detection,
                saved=len(records),
                target=capture_config.views,
                accepted=accepted,
                label="right",
            )
            if left_preview.shape[0] != right_preview.shape[0]:
                right_preview = cv2.resize(right_preview, (right_preview.shape[1], left_preview.shape[0]))
            cv2.imshow(window_name, np.hstack([left_preview, right_preview]))
            key = cv2.waitKey(30) & 0xFF
            if key in {27, ord("q"), ord("Q")}:
                break
            if key == ord(" ") and accepted and len(records) < capture_config.views:
                records.append(save_stereo_pair(output, left_frame, right_frame, left_detection, right_detection, len(records)))
                last_capture = now
            if key in {ord("c"), ord("C")}:
                calibrate_requested = True
                break
            if len(records) >= capture_config.views:
                calibrate_requested = True
                break
    finally:
        left_source.release()
        right_source.release()
        cv2.destroyWindow(window_name)
    manifest = session_manifest(
        kind="stereo_charuco",
        output=output,
        config=config,
        records=records,
        calibrate_requested=calibrate_requested,
        calibration_output=calibration_output,
    )
    write_json(output / "manifest.json", manifest)
    return manifest


def session_manifest(
    *,
    kind: str,
    output: Path,
    config: ToolConfig,
    records: list[dict[str, Any]],
    calibrate_requested: bool,
    calibration_output: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": "tennisbot.calibration_capture_session.v1",
        "created_at": utc_now_iso(),
        "kind": kind,
        "status": "ready" if records else "partial",
        "session_root": str(output),
        "target": {
            "profile": config.target.profile,
            "squares_x": config.target.squares_x,
            "squares_y": config.target.squares_y,
            "dictionary": config.target.dictionary,
            "square_size_m": config.target.square_size_m,
            "marker_size_m": config.target.marker_size_m,
        },
        "camera": {
            "width_px": config.camera.width_px,
            "height_px": config.camera.height_px,
            "fps": config.camera.fps,
            "fourcc": config.camera.fourcc,
        },
        "view_count": len(records),
        "calibrate_requested": calibrate_requested,
        "calibration_output": None if calibration_output is None else str(calibration_output),
        "calibration_status": "not_implemented_in_minimal_migration",
        "frames": records,
    }
