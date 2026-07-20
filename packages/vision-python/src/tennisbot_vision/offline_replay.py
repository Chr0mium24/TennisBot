from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import bisect
import json
import statistics
import subprocess
import time

import cv2
import numpy as np

from tennisbot_camera.capture import CapturedFrame
from tennisbot_camera.config import load_camera_config
from tennisbot_camera.recording import TestRecordingSink, detection_payload

from .calibration import RuntimeStereoCalibration
from .detection import YoloBallDetector
from .matching import StereoBallMatcher
from .render import render_gui
from .types import StereoBallMatch, StereoMatchDiagnostics


@dataclass(frozen=True)
class ResolvedStereoVideos:
    recording: Path | None
    left_video: Path
    right_video: Path


@dataclass(frozen=True)
class ReplayFramePair:
    pair_id: int
    left_index: int
    right_index: int
    delta_ms: float | None
    timestamp_s: float | None


@dataclass(frozen=True)
class TrajectoryPrediction:
    sample_count: int
    horizon_s: float
    point_3d_m: np.ndarray
    velocity_mps: np.ndarray


@dataclass(frozen=True)
class TextAnchor:
    x: int
    y: int


def resolve_stereo_videos(
    *,
    recording: Path | None,
    left_video: Path | None,
    right_video: Path | None,
) -> ResolvedStereoVideos:
    if recording is None:
        if left_video is None or right_video is None:
            raise ValueError("--left-video and --right-video are required when --recording is not provided")
        return ResolvedStereoVideos(None, left_video, right_video)

    if left_video is not None and right_video is not None:
        return ResolvedStereoVideos(recording, _resolve_under(recording, left_video), _resolve_under(recording, right_video))
    if left_video is not None or right_video is not None:
        raise ValueError("--left-video and --right-video must be provided together")

    left = _video_from_session(recording, "cam1")
    right = _video_from_session(recording, "cam2")
    return ResolvedStereoVideos(recording, left, right)


def validate_frame_selection(frame_start: int, frame_end: int | None, stride: int) -> None:
    if frame_start < 0:
        raise ValueError("--frame-start must be non-negative")
    if frame_end is not None and frame_end < frame_start:
        raise ValueError("--frame-end must be greater than or equal to --frame-start")
    if stride <= 0:
        raise ValueError("--stride must be positive")


def build_frame_pairs(
    *,
    sync: str,
    frame_start: int,
    frame_end: int | None,
    stride: int,
    left_video: Path,
    right_video: Path,
    left_frame_count: int,
    right_frame_count: int,
    fps: float,
    max_pair_delta_ms: float,
) -> list[ReplayFramePair]:
    validate_frame_selection(frame_start, frame_end, stride)
    max_inclusive = min(left_frame_count, right_frame_count) - 1
    if max_inclusive < 0:
        return []
    if frame_end is not None:
        max_inclusive = min(max_inclusive, frame_end)

    if sync == "frame-index":
        return [
            ReplayFramePair(
                pair_id=index,
                left_index=index,
                right_index=index,
                delta_ms=0.0,
                timestamp_s=index / fps if fps > 0 else None,
            )
            for index in range(frame_start, max_inclusive + 1, stride)
        ]

    if sync != "pts":
        raise ValueError(f"unsupported sync mode: {sync}")

    left_timestamps = probe_video_timestamps(left_video)
    right_timestamps = probe_video_timestamps(right_video)
    max_inclusive = min(max_inclusive, len(left_timestamps) - 1)
    pairs: list[ReplayFramePair] = []
    for left_index in range(frame_start, max_inclusive + 1, stride):
        left_ts = left_timestamps[left_index]
        right_index, delta_ms = _nearest_timestamp_index(right_timestamps, left_ts)
        if right_index is None or abs(delta_ms) > max_pair_delta_ms:
            continue
        pairs.append(
            ReplayFramePair(
                pair_id=left_index,
                left_index=left_index,
                right_index=right_index,
                delta_ms=delta_ms,
                timestamp_s=left_ts,
            )
        )
    return pairs


def run_offline_stereo_replay(args: Any) -> int:
    resolved = resolve_stereo_videos(
        recording=args.recording,
        left_video=args.left_video,
        right_video=args.right_video,
    )
    _require_file(resolved.left_video)
    _require_file(resolved.right_video)
    _require_file(args.calibration_package / "package.json")
    validate_frame_selection(args.frame_start, args.frame_end, args.stride)

    left_cap = cv2.VideoCapture(str(resolved.left_video))
    right_cap = cv2.VideoCapture(str(resolved.right_video))
    try:
        if not left_cap.isOpened():
            raise RuntimeError(f"cannot open left video: {resolved.left_video}")
        if not right_cap.isOpened():
            raise RuntimeError(f"cannot open right video: {resolved.right_video}")

        source_size = _capture_size(left_cap)
        right_source_size = _capture_size(right_cap)
        if source_size != right_source_size:
            raise RuntimeError(f"left/right video sizes differ: {source_size} vs {right_source_size}")

        source_fps = float(left_cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if source_fps <= 0:
            source_fps = float(args.output_fps)
        left_count = int(left_cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        right_count = int(right_cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if left_count <= 0 or right_count <= 0:
            raise RuntimeError("cannot determine video frame counts")

        base_calibration = RuntimeStereoCalibration.from_package(args.calibration_package)
        inference_size = base_calibration.source_image_size if args.resize_to_calibration else source_size
        calibration = RuntimeStereoCalibration.from_package(args.calibration_package, frame_size=inference_size)
        pairs = build_frame_pairs(
            sync=args.sync,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            stride=args.stride,
            left_video=resolved.left_video,
            right_video=resolved.right_video,
            left_frame_count=left_count,
            right_frame_count=right_count,
            fps=source_fps,
            max_pair_delta_ms=args.max_pair_delta_ms,
        )

        model = YoloBallDetector(
            args.model,
            confidence_threshold=args.conf,
            iou_threshold=args.iou,
            imgsz=args.imgsz,
            max_detections=args.max_detections,
            device=args.yolo_device,
            class_id=0,
            tile=False,
            tile_width=2048,
            tile_height=1216,
            tile_overlap=160,
        )
        matcher = StereoBallMatcher(
            calibration,
            max_epipolar_error_px=args.max_epipolar_error_px,
            min_disparity_px=args.min_disparity_px,
            max_disparity_px=args.max_disparity_px,
            max_depth_m=args.max_depth_m,
        )

        sink = None
        session_dir = None
        trajectory_file = None
        if args.record:
            sink = TestRecordingSink(
                root=args.record_root,
                session_name=args.record_session or _default_session_name(resolved.recording, args.frame_start, args.frame_end),
                camera_ids=("cam1", "cam2"),
                fps=args.output_fps,
                frame_size=inference_size,
                overlay=args.record_overlay,
                test_kind="replay",
            )
            session_dir = sink.session_dir
            if args.predict_trajectory:
                trajectory_file = (session_dir / "trajectory.ndjson").open("a", encoding="utf-8", buffering=1)

        started = time.perf_counter()
        summary = _Summary()
        trajectory_samples: list[tuple[float, np.ndarray]] = []
        last_prediction: TrajectoryPrediction | None = None
        records: list[dict[str, Any]] = []

        for processed_index, pair in enumerate(pairs, start=1):
            left_frame = _read_frame(left_cap, pair.left_index)
            right_frame = _read_frame(right_cap, pair.right_index)
            if inference_size != source_size:
                left_frame = cv2.resize(left_frame, inference_size, interpolation=cv2.INTER_AREA)
                right_frame = cv2.resize(right_frame, inference_size, interpolation=cv2.INTER_AREA)

            begin = time.perf_counter()
            left_detections, right_detections = model.detect_pair(left_frame, right_frame)
            latency_ms = (time.perf_counter() - begin) * 1000.0
            match = matcher.select(left_detections, right_detections)

            timestamp_s = pair.timestamp_s if pair.timestamp_s is not None else pair.left_index / source_fps
            prediction = None
            if args.predict_trajectory and match is not None:
                trajectory_samples.append((timestamp_s, match.point_3d_m.copy()))
                prediction = linear_trajectory_prediction(trajectory_samples, args.trajectory_horizon_s)
                last_prediction = prediction

            record = replay_payload(pair, left_detections, right_detections, match, matcher.last_diagnostics, latency_ms, prediction)
            summary.add(record, match, latency_ms)
            records.append(record)

            overlay = None
            if args.gui or args.record_overlay:
                overlay = render_gui(
                    left_frame,
                    right_frame,
                    left_detections,
                    right_detections,
                    match,
                    matcher.last_diagnostics,
                    fps=0.0,
                    frame_id=pair.left_index,
                    display_camera_width=args.display_camera_width,
                    plot_depth_m=args.max_depth_m,
                    plot_x_m=args.plot_x_m,
                )
                if prediction is not None:
                    draw_trajectory_prediction(overlay, prediction)

            if sink is not None:
                monotonic_ns = int(timestamp_s * 1_000_000_000)
                left_captured = CapturedFrame("cam1", pair.left_index, monotonic_ns, monotonic_ns, left_frame)
                right_captured = CapturedFrame("cam2", pair.right_index, monotonic_ns, monotonic_ns, right_frame)
                sink.record_stereo(
                    pair.pair_id,
                    left_captured,
                    right_captured,
                    int(round((pair.delta_ms or 0.0) * 1_000_000.0)),
                    {
                        "cam1": [detection_payload(item) for item in left_detections],
                        "cam2": [detection_payload(item) for item in right_detections],
                    },
                    None if match is None else match_payload(match),
                    overlay,
                )
                if trajectory_file is not None and prediction is not None:
                    trajectory_file.write(json.dumps({"pair_id": pair.pair_id, **trajectory_payload(prediction)}, sort_keys=True) + "\n")

            if args.json:
                print(json.dumps(record, sort_keys=True), flush=True)
            if args.gui and overlay is not None and _show("TennisBot replay stereo", overlay):
                break
            if args.progress_every > 0 and processed_index % args.progress_every == 0 and not args.json:
                print(f"progress processed={processed_index} matched={summary.matched_pairs}", flush=True)

        elapsed_s = time.perf_counter() - started
        output = summary_payload(
            args=args,
            resolved=resolved,
            session_dir=session_dir,
            source_size=source_size,
            inference_size=inference_size,
            source_fps=source_fps,
            selected_pairs=len(pairs),
            elapsed_s=elapsed_s,
            summary=summary,
            last_prediction=last_prediction,
        )
        if session_dir is not None:
            (session_dir / "summary.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif args.json:
            print(json.dumps(output, sort_keys=True), flush=True)
        else:
            print(json.dumps(output, indent=2, sort_keys=True), flush=True)
        if sink is not None and not args.json:
            print(f"recorded_session={sink.session_dir}", flush=True)
        return 0
    finally:
        left_cap.release()
        right_cap.release()
        cv2.destroyAllWindows()
        if "trajectory_file" in locals() and trajectory_file is not None:
            trajectory_file.close()
        if "sink" in locals() and sink is not None:
            sink.close()


def probe_video_timestamps(path: Path) -> list[float]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "frame=best_effort_timestamp_time",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    timestamps = [float(line) for line in completed.stdout.splitlines() if _is_float(line)]
    if not timestamps:
        raise RuntimeError(f"ffprobe did not return frame timestamps for {path}")
    return timestamps


def linear_trajectory_prediction(
    samples: list[tuple[float, np.ndarray]],
    horizon_s: float,
    *,
    window: int = 5,
) -> TrajectoryPrediction | None:
    if len(samples) < 2:
        return None
    recent = samples[-window:]
    times = np.asarray([item[0] for item in recent], dtype=np.float64)
    points = np.asarray([item[1] for item in recent], dtype=np.float64)
    t0 = float(times[-1])
    centered = times - t0
    if float(np.ptp(centered)) <= 1e-9:
        return None
    design = np.column_stack([centered, np.ones_like(centered)])
    velocity, intercept = np.linalg.lstsq(design, points, rcond=None)[0]
    predicted = intercept + velocity * horizon_s
    return TrajectoryPrediction(
        sample_count=len(recent),
        horizon_s=float(horizon_s),
        point_3d_m=predicted,
        velocity_mps=velocity,
    )


def draw_trajectory_prediction(image: np.ndarray, prediction: TrajectoryPrediction) -> None:
    x, y, z = (float(value) for value in prediction.point_3d_m)
    vx, vy, vz = (float(value) for value in prediction.velocity_mps)
    anchors = trajectory_prediction_text_anchors(image_width=image.shape[1], image_height=image.shape[0], panel_width=440)
    color = (80, 210, 255)
    muted = (165, 175, 185)
    left = max(0, anchors[0].x - 10)
    top = max(0, anchors[0].y - 22)
    right_panel_left = max(0, image.shape[1] - 440)
    right = min(right_panel_left - 10, left + 650)
    bottom = min(image.shape[0] - 6, anchors[-1].y + 12)
    if right > left and bottom > top:
        region = image[top:bottom, left:right]
        tint = region.copy()
        cv2.rectangle(tint, (0, 0), (region.shape[1], region.shape[0]), (0, 0, 0), -1)
        cv2.addWeighted(tint, 0.48, region, 0.52, 0.0, region)
    cv2.putText(image, f"linear pred +{prediction.horizon_s:.2f}s", (anchors[0].x, anchors[0].y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 1, cv2.LINE_AA)
    cv2.putText(image, f"p: {x:+.2f} {y:+.2f} {z:+.2f} m", (anchors[1].x, anchors[1].y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
    cv2.putText(image, f"v: {vx:+.2f} {vy:+.2f} {vz:+.2f} m/s  n={prediction.sample_count}", (anchors[2].x, anchors[2].y),
        cv2.FONT_HERSHEY_SIMPLEX, 0.46, muted, 1, cv2.LINE_AA)


def trajectory_prediction_text_anchors(*, image_width: int, image_height: int, panel_width: int) -> tuple[TextAnchor, TextAnchor, TextAnchor]:
    right_panel_left = max(0, image_width - panel_width)
    x = 18 if right_panel_left > 180 else 8
    base_y = max(76, image_height - 64)
    return (
        TextAnchor(x, base_y - 40),
        TextAnchor(x, base_y - 18),
        TextAnchor(x, base_y + 4),
    )


def replay_payload(
    pair: ReplayFramePair,
    left_detections: list[Any],
    right_detections: list[Any],
    match: StereoBallMatch | None,
    diagnostics: StereoMatchDiagnostics,
    latency_ms: float,
    prediction: TrajectoryPrediction | None,
) -> dict[str, Any]:
    payload = {
        "kind": "replay",
        "mode": "stereo",
        "pair_id": pair.pair_id,
        "left_frame": pair.left_index,
        "right_frame": pair.right_index,
        "pair_delta_ms": pair.delta_ms,
        "timestamp_s": pair.timestamp_s,
        "left_detections": len(left_detections),
        "right_detections": len(right_detections),
        "latency_ms": latency_ms,
        "triangulation": None if match is None else match_payload(match),
        "trajectory_prediction": None if prediction is None else trajectory_payload(prediction),
        "diagnostics": diagnostics_payload(diagnostics),
    }
    return payload


def match_payload(match: StereoBallMatch) -> dict[str, Any]:
    x, y, z = (float(value) for value in match.point_3d_m)
    return {
        "x_m": x,
        "y_m": y,
        "z_m": z,
        "disparity_px": float(match.disparity_px),
        "epipolar_error_px": float(match.epipolar_error_px),
        "reprojection_error_px": float(match.reprojection_error_px),
        "confidence": float(match.confidence),
        "cost": float(match.cost),
    }


def diagnostics_payload(diagnostics: StereoMatchDiagnostics) -> dict[str, Any]:
    return {
        "evaluated_candidate_count": diagnostics.evaluated_candidate_count,
        "rejected_by_epipolar_count": diagnostics.rejected_by_epipolar_count,
        "rejected_by_disparity_count": diagnostics.rejected_by_disparity_count,
        "rejected_by_triangulation_count": diagnostics.rejected_by_triangulation_count,
        "rejected_by_depth_count": diagnostics.rejected_by_depth_count,
        "best_cost": diagnostics.best_cost,
        "candidates": diagnostics.candidates,
    }


def trajectory_payload(prediction: TrajectoryPrediction) -> dict[str, Any]:
    return {
        "sample_count": prediction.sample_count,
        "horizon_s": prediction.horizon_s,
        "point_3d_m": [float(value) for value in prediction.point_3d_m],
        "velocity_mps": [float(value) for value in prediction.velocity_mps],
    }


def summary_payload(
    *,
    args: Any,
    resolved: ResolvedStereoVideos,
    session_dir: Path | None,
    source_size: tuple[int, int],
    inference_size: tuple[int, int],
    source_fps: float,
    selected_pairs: int,
    elapsed_s: float,
    summary: _Summary,
    last_prediction: TrajectoryPrediction | None,
) -> dict[str, Any]:
    return {
        "kind": "replay",
        "mode": "stereo",
        "recording": None if resolved.recording is None else str(resolved.recording),
        "left_video": str(resolved.left_video),
        "right_video": str(resolved.right_video),
        "calibration_package": str(args.calibration_package),
        "model": str(args.model),
        "session_dir": None if session_dir is None else str(session_dir),
        "overlay_video": None if session_dir is None or not args.record_overlay else str(session_dir / "overlay.mp4"),
        "frame_start": args.frame_start,
        "frame_end": args.frame_end,
        "frame_end_inclusive": True,
        "stride": args.stride,
        "sync": args.sync,
        "max_pair_delta_ms": args.max_pair_delta_ms,
        "source_frame_size": {"width": source_size[0], "height": source_size[1]},
        "inference_frame_size": {"width": inference_size[0], "height": inference_size[1]},
        "source_fps": source_fps,
        "output_fps": args.output_fps,
        "selected_pairs": selected_pairs,
        "processed_pairs": summary.processed_pairs,
        "matched_pairs": summary.matched_pairs,
        "left_detection_frames": summary.left_detection_frames,
        "right_detection_frames": summary.right_detection_frames,
        "both_detection_frames": summary.both_detection_frames,
        "match_rate_processed": summary.matched_pairs / summary.processed_pairs if summary.processed_pairs else 0.0,
        "latency_ms_mean": statistics.fmean(summary.latencies_ms) if summary.latencies_ms else None,
        "latency_ms_median": statistics.median(summary.latencies_ms) if summary.latencies_ms else None,
        "epipolar_error_px_median": statistics.median(summary.epipolar_errors) if summary.epipolar_errors else None,
        "epipolar_error_px_max": max(summary.epipolar_errors) if summary.epipolar_errors else None,
        "depth_m_median": statistics.median(summary.depths) if summary.depths else None,
        "depth_m_min": min(summary.depths) if summary.depths else None,
        "depth_m_max": max(summary.depths) if summary.depths else None,
        "predict_trajectory": bool(args.predict_trajectory),
        "last_trajectory_prediction": None if last_prediction is None else trajectory_payload(last_prediction),
        "elapsed_s": elapsed_s,
        "processed_fps_wall": summary.processed_pairs / elapsed_s if elapsed_s > 0 else 0.0,
    }


class _Summary:
    def __init__(self) -> None:
        self.processed_pairs = 0
        self.matched_pairs = 0
        self.left_detection_frames = 0
        self.right_detection_frames = 0
        self.both_detection_frames = 0
        self.latencies_ms: list[float] = []
        self.epipolar_errors: list[float] = []
        self.depths: list[float] = []

    def add(self, record: dict[str, Any], match: StereoBallMatch | None, latency_ms: float) -> None:
        self.processed_pairs += 1
        self.left_detection_frames += int(record["left_detections"] > 0)
        self.right_detection_frames += int(record["right_detections"] > 0)
        self.both_detection_frames += int(record["left_detections"] > 0 and record["right_detections"] > 0)
        self.latencies_ms.append(latency_ms)
        if match is not None:
            self.matched_pairs += 1
            self.epipolar_errors.append(float(match.epipolar_error_px))
            self.depths.append(float(match.point_3d_m[2]))


def _video_from_session(recording: Path, camera_id: str) -> Path:
    session_json = recording / "session.json"
    if session_json.is_file():
        payload = json.loads(session_json.read_text(encoding="utf-8"))
        streams = payload.get("streams")
        if isinstance(streams, dict) and camera_id in streams:
            return _stream_path(recording, streams[camera_id])

    for name in _camera_video_candidates(camera_id):
        matches = sorted(recording.glob(name))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"cannot find {camera_id} video under {recording}")


def _camera_video_candidates(camera_id: str) -> list[str]:
    candidates = [f"{camera_id}.mp4", f"{camera_id}.mkv", f"*_{camera_id}.mp4", f"*_{camera_id}.mkv"]
    try:
        device = Path(load_camera_config().camera(camera_id).device).name
    except Exception:
        device = "video0" if camera_id == "cam1" else "video2"
    candidates.extend([f"*_{device}.mkv", f"*_{device}.mp4", f"*{device}.mkv", f"*{device}.mp4"])
    return candidates


def _stream_path(recording: Path, value: Any) -> Path:
    if isinstance(value, str):
        return _resolve_under(recording, Path(value))
    if isinstance(value, dict):
        for key in ("file", "path", "output"):
            if key in value:
                return _resolve_under(recording, Path(str(value[key])))
    raise ValueError(f"unsupported recording stream entry: {value!r}")


def _resolve_under(base: Path, path: Path) -> Path:
    return path if path.is_absolute() else base / path


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def _capture_size(capture: cv2.VideoCapture) -> tuple[int, int]:
    return int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))


def _read_frame(capture: cv2.VideoCapture, index: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = capture.read()
    if not ok or frame is None:
        raise RuntimeError(f"cannot read frame {index}")
    return frame


def _nearest_timestamp_index(timestamps: list[float], target: float) -> tuple[int | None, float]:
    if not timestamps:
        return None, float("inf")
    insertion = bisect.bisect_left(timestamps, target)
    candidates = []
    if insertion < len(timestamps):
        candidates.append(insertion)
    if insertion > 0:
        candidates.append(insertion - 1)
    index = min(candidates, key=lambda item: abs(timestamps[item] - target))
    return index, (timestamps[index] - target) * 1000.0


def _default_session_name(recording: Path | None, frame_start: int, frame_end: int | None) -> str:
    source = "videos" if recording is None else recording.name
    end = "end" if frame_end is None else str(frame_end)
    return f"replay_{source}_{frame_start}_{end}"


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _show(window: str, image: np.ndarray) -> bool:
    cv2.imshow(window, image)
    return cv2.waitKey(1) & 0xFF in (27, ord("q"))
