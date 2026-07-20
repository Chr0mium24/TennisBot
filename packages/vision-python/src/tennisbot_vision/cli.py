from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import cv2

from tennisbot_camera.capture import FrameSource, StereoFrameSource
from tennisbot_camera.config import load_camera_config
from tennisbot_camera.controls import apply_command

from .calibration import RuntimeStereoCalibration
from .communication import main as communication_main
from .detection import YoloBallDetector
from .matching import StereoBallMatcher
from .offline_replay import run_offline_stereo_replay, validate_frame_selection
from .render import draw_detections, render_gui, resize_to_width
from tennisbot_camera.recording import TestRecordingSink, detection_payload


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_MODEL = REPO_ROOT / "artifacts/models/tennis_ball_yolo/model.pt"
DEFAULT_CALIBRATION = REPO_ROOT / "artifacts/calibration/stereo_cam1_cam2"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="test.py", description="TennisBot vision and communication diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    yolo = sub.add_parser("yolo", help="mono or stereo YOLO diagnostics")
    yolo.add_argument("mode", choices=("mono", "stereo"))
    yolo.add_argument("camera_id", choices=("cam1", "cam2"), nargs="?")
    add_online_args(yolo)
    tri = sub.add_parser("triangulation", help="stereo YOLO matching and triangulation")
    tri.add_argument("mode", choices=("stereo",))
    add_online_args(tri)
    tri.add_argument("--calibration-package", type=Path, default=DEFAULT_CALIBRATION)
    replay = sub.add_parser("replay", help="offline stereo recording replay diagnostics")
    replay.add_argument("mode", choices=("stereo",))
    add_replay_args(replay)
    communication = sub.add_parser("communication", help="read-only ROS communication diagnostics")
    communication.add_argument("test", choices=("chassis-position",))
    communication.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def add_online_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--record-overlay", action="store_true")
    parser.add_argument("--record-root", type=Path, default=REPO_ROOT / "runs/test")
    parser.add_argument("--record-session")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--yolo-device", default=None)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def add_replay_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--recording", type=Path)
    parser.add_argument("--left-video", type=Path)
    parser.add_argument("--right-video", type=Path)
    parser.add_argument("--calibration-package", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--yolo-device", default=None)
    parser.add_argument("--max-detections", type=int, default=6)
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--sync", choices=("frame-index", "pts"), default="frame-index")
    parser.add_argument("--max-pair-delta-ms", type=float, default=10.0)
    parser.add_argument("--resize-to-calibration", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--record", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--record-overlay", action="store_true")
    parser.add_argument("--record-root", type=Path, default=REPO_ROOT / "runs/test")
    parser.add_argument("--record-session")
    parser.add_argument("--output-fps", type=float, default=10.0)
    parser.add_argument("--display-camera-width", type=int, default=720)
    parser.add_argument("--plot-x-m", type=float, default=4.0)
    parser.add_argument("--max-epipolar-error-px", type=float, default=6.0)
    parser.add_argument("--min-disparity-px", type=float, default=1.0)
    parser.add_argument("--max-disparity-px", type=float, default=1200.0)
    parser.add_argument("--max-depth-m", type=float, default=12.0)
    parser.add_argument("--predict-trajectory", action="store_true")
    parser.add_argument("--trajectory-horizon-s", type=float, default=0.33)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "communication":
        return communication_main(args.args)
    if args.record_overlay:
        args.record = True
    if args.command == "replay":
        if args.recording is None and (args.left_video is None or args.right_video is None):
            build_parser().error("replay stereo requires either --recording or both --left-video and --right-video")
        validate_frame_selection(args.frame_start, args.frame_end, args.stride)
        if args.max_pair_delta_ms < 0:
            build_parser().error("max-pair-delta-ms must be non-negative")
        if args.output_fps <= 0:
            build_parser().error("output-fps must be positive")
        if args.display_camera_width <= 0:
            build_parser().error("display-camera-width must be positive")
        if args.trajectory_horizon_s <= 0:
            build_parser().error("trajectory-horizon-s must be positive")
        if args.dry_run:
            return print_dry_run(args)
        return run_offline_stereo_replay(args)
    if args.command == "yolo" and args.mode == "mono" and args.camera_id is None:
        build_parser().error("yolo mono requires cam1 or cam2")
    if args.command == "yolo" and args.mode == "stereo" and args.camera_id is not None:
        build_parser().error("yolo stereo does not accept a camera id")
    if args.duration < 0 or args.max_frames < 0:
        build_parser().error("duration and max-frames must be non-negative")
    if args.dry_run:
        return print_dry_run(args)
    apply_test_controls(args)
    return run_mono(args) if args.mode == "mono" else run_stereo(args)


def detector(args) -> YoloBallDetector:
    return YoloBallDetector(args.model, confidence_threshold=args.conf, iou_threshold=args.iou, imgsz=args.imgsz,
        max_detections=6, device=args.yolo_device, class_id=0, tile=False, tile_width=2048, tile_height=1216, tile_overlap=160)


def apply_test_controls(args) -> None:
    config = load_camera_config()
    targets = (config.camera(args.camera_id),) if args.mode == "mono" else config.devices("stereo")
    for camera in targets:
        import subprocess
        subprocess.run(apply_command(camera.device, config.profile("test")), check=True)


def run_mono(args) -> int:
    config = load_camera_config()
    model = detector(args)
    meter = Meter()
    sink = None
    with FrameSource(config.camera(args.camera_id), config) as source:
        started = time.monotonic()
        count = 0
        try:
            while keep_running(args, started, count):
                frame = source.read()
                begin = time.perf_counter()
                detections = model.detect(frame.image)
                latency_ms = (time.perf_counter() - begin) * 1000
                payload = {"kind": "yolo", "mode": "mono", "camera_id": args.camera_id, "sequence": frame.sequence,
                    "detections": len(detections), "confidence": max((item.confidence for item in detections), default=None),
                    "fps": meter.update(), "latency_ms": latency_ms}
                emit(payload, args.json)
                overlay = None
                if args.gui or args.record_overlay:
                    overlay = frame.image.copy()
                    draw_detections(overlay, detections, selected=None)
                if args.record and sink is None:
                    sink = TestRecordingSink(root=args.record_root, session_name=args.record_session, camera_ids=(args.camera_id,),
                        fps=config.capture.fps, frame_size=(frame.image.shape[1], frame.image.shape[0]), overlay=args.record_overlay, test_kind="yolo")
                if sink is not None:
                    sink.record_mono(frame, [detection_payload(item) for item in detections], overlay)
                if args.gui and show(f"TennisBot YOLO {args.camera_id}", overlay):
                    break
                count += 1
        finally:
            if sink is not None:
                sink.close()
                print(f"recorded_session={sink.session_dir}")
            cv2.destroyAllWindows()
    return 0


def run_stereo(args) -> int:
    config = load_camera_config()
    model = detector(args)
    calibration = None
    matcher = None
    if args.command == "triangulation":
        calibration = RuntimeStereoCalibration.from_package(args.calibration_package, frame_size=(config.capture.width, config.capture.height))
        matcher = StereoBallMatcher(calibration, max_epipolar_error_px=6, min_disparity_px=1, max_disparity_px=1200, max_depth_m=12)
    meter = Meter()
    sink = None
    with StereoFrameSource(*config.devices("stereo"), config) as source:
        started = time.monotonic()
        count = 0
        try:
            while keep_running(args, started, count):
                pair_id, left, right, delta_ns = source.read()
                begin = time.perf_counter()
                left_detections, right_detections = model.detect_pair(left.image, right.image)
                latency_ms = (time.perf_counter() - begin) * 1000
                match = None if matcher is None else matcher.select(left_detections, right_detections)
                payload = stereo_payload(args.command, pair_id, left_detections, right_detections, match, delta_ns, meter.update(), latency_ms)
                emit(payload, args.json)
                overlay = None
                if args.gui or args.record_overlay:
                    if matcher is not None:
                        overlay = render_gui(left.image, right.image, left_detections, right_detections, match, matcher.last_diagnostics,
                            fps=payload["fps"], frame_id=pair_id, display_camera_width=720, plot_depth_m=10, plot_x_m=3)
                    else:
                        left_overlay, right_overlay = left.image.copy(), right.image.copy()
                        draw_detections(left_overlay, left_detections, selected=None)
                        draw_detections(right_overlay, right_detections, selected=None)
                        overlay = cv2.hconcat([
                            resize_to_width(left_overlay, 720),
                            resize_to_width(right_overlay, 720),
                        ])
                if args.record and sink is None:
                    sink = TestRecordingSink(root=args.record_root, session_name=args.record_session, camera_ids=("cam1", "cam2"),
                        fps=config.capture.fps, frame_size=(left.image.shape[1], left.image.shape[0]), overlay=args.record_overlay, test_kind=args.command)
                if sink is not None:
                    sink.record_stereo(pair_id, left, right, delta_ns,
                        {"cam1": [detection_payload(item) for item in left_detections], "cam2": [detection_payload(item) for item in right_detections]},
                        None if match is None else match_payload(match), overlay)
                if args.gui and show(f"TennisBot {args.command} stereo", overlay):
                    break
                count += 1
        finally:
            if sink is not None:
                sink.close()
                print(f"recorded_session={sink.session_dir}")
            cv2.destroyAllWindows()
    return 0


def stereo_payload(kind, pair_id, left, right, match, delta_ns, fps, latency_ms):
    payload = {"kind": kind, "mode": "stereo", "pair_id": pair_id, "left_detections": len(left),
        "right_detections": len(right), "pair_delta_ms": delta_ns / 1e6, "fps": fps, "latency_ms": latency_ms}
    if kind == "triangulation":
        payload["triangulation"] = None if match is None else match_payload(match)
    return payload


def match_payload(match):
    x, y, z = (float(value) for value in match.point_3d_m)
    return {"x_m": x, "y_m": y, "z_m": z, "disparity_px": match.disparity_px,
        "epipolar_error_px": match.epipolar_error_px, "reprojection_error_px": match.reprojection_error_px,
        "confidence": match.confidence}


def emit(payload, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, sort_keys=True), flush=True)
    else:
        values = " ".join(f"{key}={value}" for key, value in payload.items())
        print(values, flush=True)


def show(window: str, image) -> bool:
    cv2.imshow(window, image)
    return cv2.waitKey(1) & 0xFF in (27, ord("q"))


def keep_running(args, started: float, count: int) -> bool:
    return not ((args.duration > 0 and time.monotonic() - started >= args.duration) or (args.max_frames > 0 and count >= args.max_frames))


def print_dry_run(args) -> int:
    if args.command == "replay":
        print(json.dumps({"test": args.command, "mode": args.mode, "recording": None if args.recording is None else str(args.recording),
            "left_video": None if args.left_video is None else str(args.left_video),
            "right_video": None if args.right_video is None else str(args.right_video),
            "calibration_package": str(args.calibration_package), "frame_start": args.frame_start, "frame_end": args.frame_end,
            "frame_end_inclusive": True, "stride": args.stride, "sync": args.sync, "record": args.record,
            "record_overlay": args.record_overlay, "model": str(args.model), "predict_trajectory": args.predict_trajectory}, sort_keys=True))
        return 0
    config = load_camera_config()
    cameras = [args.camera_id] if args.mode == "mono" else ["cam1", "cam2"]
    print(json.dumps({"test": args.command, "mode": args.mode, "cameras": cameras, "devices": [config.camera(item).device for item in cameras],
        "gui": args.gui, "record": args.record, "record_overlay": args.record_overlay, "model": str(args.model)}, sort_keys=True))
    return 0


class Meter:
    def __init__(self) -> None:
        self.previous = None
        self.fps = 0.0

    def update(self) -> float:
        now = time.perf_counter()
        if self.previous is not None:
            instant = 1.0 / max(now - self.previous, 1e-6)
            self.fps = instant if self.fps == 0 else 0.15 * instant + 0.85 * self.fps
        self.previous = now
        return self.fps


if __name__ == "__main__":
    raise SystemExit(main())
