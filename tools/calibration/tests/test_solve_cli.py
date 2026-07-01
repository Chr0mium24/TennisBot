from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from camera_calib_lab.camera_preview import PreviewCamera, V4L2Control, draw_preview_frame
from camera_calib_lab.cli import main
from camera_calib_lab.capture_types import parse_device
from camera_calib_lab.solve import (
    MonoCameraPackage,
    SourceObservations,
    ViewObservation,
    detect_session_observations,
    target_payload,
    validate_stereo_source_devices,
)


class SolveCliTest(unittest.TestCase):
    def test_camera_brightness_help_is_available(self) -> None:
        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["camera", "brightness", "--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_camera_preview_help_is_available(self) -> None:
        with redirect_stdout(StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["camera", "preview", "--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_camera_preview_dry_run_reports_devices(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = main(["camera", "preview", "--dry-run", "--devices", "/dev/video0,/dev/video2"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "dry-run")
        self.assertEqual(report["width"], 3840)
        self.assertEqual(report["height"], 2160)
        self.assertEqual(report["fps"], 30.0)
        self.assertEqual([camera["device"] for camera in report["cameras"]], ["/dev/video0", "/dev/video2"])

    def test_camera_preview_dry_run_uses_visible_manual_defaults(self) -> None:
        controls = {
            "exposure_time_absolute": V4L2Control("exposure_time_absolute", 3, 2047, 1, 166, 166),
            "brightness": V4L2Control("brightness", -64, 64, 1, -5, -5),
        }
        output = StringIO()
        with patch("camera_calib_lab.camera_preview.read_v4l2_controls", return_value=controls):
            with redirect_stdout(output):
                code = main(["camera", "preview", "--dry-run", "--device", "/dev/video0"])
        self.assertEqual(code, 0)
        camera = json.loads(output.getvalue())["cameras"][0]
        self.assertEqual(camera["exposure_time_absolute"]["selected"], 2047)
        self.assertEqual(camera["brightness"]["selected"], 64)
        self.assertNotIn("gain", camera)

    def test_camera_preview_overlay_is_readable_after_4k_resize(self) -> None:
        frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
        camera = PreviewCamera(
            label="left",
            device="/dev/video0",
            source=None,  # type: ignore[arg-type]
            controls=SimpleNamespace(exposure_value=100, brightness_value=64),  # type: ignore[arg-type]
        )

        preview = draw_preview_frame(frame, camera, max_width=760)
        green_pixels = (preview[:, :, 1] > 180) & (preview[:, :, 0] < 120) & (preview[:, :, 2] < 120)
        green_rows = np.flatnonzero(green_pixels.any(axis=1))

        self.assertEqual(preview.shape[:2], (427, 760))
        self.assertGreater(int(green_pixels.sum()), 1500)
        self.assertGreater(int(green_rows[-1] - green_rows[0]), 70)

    def test_parse_dev_video_path_as_v4l2_index(self) -> None:
        self.assertEqual(parse_device("/dev/video2"), 2)
        self.assertEqual(parse_device("1"), 1)
        self.assertEqual(parse_device("/tmp/video"), "/tmp/video")

    def test_session_loader_reads_migrated_mono_session_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_session_json(
                root,
                {
                    "topology": "mono",
                    "target": target_payload({}),
                    "camera": {"camera_id": "cam1", "width_px": 960, "height_px": 640, "device": "/dev/video0"},
                    "dry_run": False,
                    "hardware_validated": True,
                    "frames": [
                        {
                            "view_id": "view001",
                            "camera_id": "cam1",
                            "frame_paths": ["cam1/view001/image.png"],
                            "frame_role": "passive",
                        }
                    ],
                },
            )

            with patched_session_detection():
                source = detect_session_observations(root, root / "missing.yaml")

            self.assertEqual(source.topology, "mono")
            self.assertEqual(len(source.views), 1)
            self.assertEqual(source.views[0].camera_id, "cam1")
            self.assertEqual(source.views[0].side, None)

    def test_session_loader_reads_migrated_stereo_session_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_session_json(
                root,
                {
                    "topology": "stereo",
                    "target": target_payload({}),
                    "stereo_rig": {
                        "left": {"camera_id": "left", "width_px": 960, "height_px": 640, "device": "/dev/video0"},
                        "right": {"camera_id": "right", "width_px": 960, "height_px": 640, "device": "/dev/video2"},
                    },
                    "dry_run": False,
                    "hardware_validated": True,
                    "frames": [
                        {
                            "view_id": "view001",
                            "camera_id": "left",
                            "frame_paths": ["left/view001/image.png"],
                            "frame_role": "passive",
                        },
                        {
                            "view_id": "view001",
                            "camera_id": "right",
                            "frame_paths": ["right/view001/image.png"],
                            "frame_role": "passive",
                        },
                    ],
                },
            )

            with patched_session_detection():
                source = detect_session_observations(root, root / "missing.yaml")

            self.assertEqual(source.topology, "stereo")
            self.assertEqual(source.pair_indices, [1])
            self.assertEqual(source.devices, {"left": "/dev/video0", "right": "/dev/video2"})
            self.assertEqual([view.side for view in source.views], ["left", "right"])

    def test_stereo_source_device_validation_accepts_equivalent_video_ids(self) -> None:
        source = SourceObservations(
            topology="stereo",
            source_path=Path("/session"),
            target={},
            dry_run=False,
            hardware_validated=True,
            views=[],
            pair_indices=[],
            devices={"left": "/dev/video0", "right": "/dev/video2"},
        )

        validate_stereo_source_devices(
            source,
            left_mono=mono_package("cam1", "0"),
            right_mono=mono_package("cam2", "/dev/video2"),
        )

    def test_stereo_source_device_validation_rejects_swapped_mono_packages(self) -> None:
        source = SourceObservations(
            topology="stereo",
            source_path=Path("/session"),
            target={},
            dry_run=False,
            hardware_validated=True,
            views=[],
            pair_indices=[],
            devices={"left": "/dev/video0", "right": "/dev/video2"},
        )

        with self.assertRaisesRegex(ValueError, "left mono package"):
            validate_stereo_source_devices(
                source,
                left_mono=mono_package("cam1", "/dev/video2"),
                right_mono=mono_package("cam2", "/dev/video0"),
            )

    def test_mono_solve_writes_runtime_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            observations = root / "mono_observations.json"
            output = root / "mono_package"
            write_mono_observations(observations, camera_id="cam1")

            code = run_cli(
                "solve",
                "mono",
                "--observations",
                str(observations),
                "--output",
                str(output),
                "--camera-id",
                "cam1",
                "--min-views",
                "4",
                "--max-rms-px",
                "1.0",
            )

            self.assertEqual(code, 0)
            package = read_json(output / "package.json")
            camera = read_json(output / "camera.json")
            verification = read_json(output / "verification.json")
            self.assertTrue(package["accepted"])
            self.assertEqual(package["schema_version"], "calibration.mono.v1")
            self.assertEqual(camera["schema_version"], "calibration.camera_intrinsics.v1")
            self.assertEqual(camera["camera_id"], "cam1")
            self.assertTrue(verification["accepted"])

    def test_mono_solve_stdout_is_concise_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            observations = root / "mono_observations.json"
            output = root / "mono_package"
            write_mono_observations(observations, camera_id="cam1")

            code, report = run_cli_output(
                "solve",
                "mono",
                "--observations",
                str(observations),
                "--output",
                str(output),
                "--camera-id",
                "cam1",
                "--min-views",
                "4",
                "--max-rms-px",
                "1.0",
            )

            self.assertEqual(code, 0)
            self.assertTrue(report.startswith("solve status=accepted "))
            self.assertIn("views=6/6", report)
            self.assertRegex(report, r"points=\d+")
            self.assertRegex(report, r"rms=\d+\.\d{4}px")
            self.assertIn(f"result={output.as_posix()}", report)
            self.assertNotIn('"schema_version"', report)

    def test_stereo_solve_writes_runtime_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mono_left_obs = root / "mono_left.json"
            mono_right_obs = root / "mono_right.json"
            stereo_obs = root / "stereo.json"
            left_pkg = root / "left_pkg"
            right_pkg = root / "right_pkg"
            stereo_pkg = root / "stereo_pkg"
            write_mono_observations(mono_left_obs, camera_id="cam1")
            write_mono_observations(mono_right_obs, camera_id="cam2")
            self.assertEqual(run_cli("solve", "mono", "--observations", str(mono_left_obs), "--output", str(left_pkg), "--camera-id", "cam1", "--min-views", "4"), 0)
            self.assertEqual(run_cli("solve", "mono", "--observations", str(mono_right_obs), "--output", str(right_pkg), "--camera-id", "cam2", "--min-views", "4"), 0)
            write_stereo_observations(stereo_obs)

            code = run_cli(
                "solve",
                "stereo",
                "--observations",
                str(stereo_obs),
                "--left-mono",
                str(left_pkg),
                "--right-mono",
                str(right_pkg),
                "--output",
                str(stereo_pkg),
                "--min-pairs",
                "4",
                "--max-rms-px",
                "1.0",
            )

            self.assertEqual(code, 0)
            package = read_json(stereo_pkg / "package.json")
            stereo = read_json(stereo_pkg / "stereo.json")
            rectification = read_json(stereo_pkg / "rectification.json")
            verification = read_json(stereo_pkg / "verification.json")
            self.assertTrue(package["accepted"])
            self.assertEqual(package["schema_version"], "calibration.stereo.v1")
            self.assertEqual(stereo["schema_version"], "calibration.stereo_extrinsics.v1")
            self.assertGreater(stereo["baseline_m"], 0)
            self.assertEqual(rectification["schema_version"], "calibration.rectification.v1")
            self.assertTrue(verification["accepted"])

    def test_stereo_solve_stdout_is_concise_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mono_left_obs = root / "mono_left.json"
            mono_right_obs = root / "mono_right.json"
            stereo_obs = root / "stereo.json"
            left_pkg = root / "left_pkg"
            right_pkg = root / "right_pkg"
            stereo_pkg = root / "stereo_pkg"
            write_mono_observations(mono_left_obs, camera_id="cam1")
            write_mono_observations(mono_right_obs, camera_id="cam2")
            self.assertEqual(run_cli("solve", "mono", "--observations", str(mono_left_obs), "--output", str(left_pkg), "--camera-id", "cam1", "--min-views", "4"), 0)
            self.assertEqual(run_cli("solve", "mono", "--observations", str(mono_right_obs), "--output", str(right_pkg), "--camera-id", "cam2", "--min-views", "4"), 0)
            write_stereo_observations(stereo_obs)

            code, report = run_cli_output(
                "solve",
                "stereo",
                "--observations",
                str(stereo_obs),
                "--left-mono",
                str(left_pkg),
                "--right-mono",
                str(right_pkg),
                "--output",
                str(stereo_pkg),
                "--min-pairs",
                "4",
                "--max-rms-px",
                "1.0",
            )

            self.assertEqual(code, 0)
            self.assertTrue(report.startswith("solve status=accepted "))
            self.assertIn("pairs=6/6", report)
            self.assertIn("points=left:", report)
            self.assertRegex(report, r"rms=\d+\.\d{4}px")
            self.assertIn("epipolar=", report)
            self.assertIn(f"result={stereo_pkg.as_posix()}", report)
            self.assertNotIn('"schema_version"', report)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cli(*args: str) -> int:
    code, _output = run_cli_output(*args)
    return code


def run_cli_output(*args: str) -> tuple[int, str]:
    output = StringIO()
    with redirect_stdout(output):
        code = main(list(args))
    return code, output.getvalue()


def write_session_json(root: Path, payload: dict) -> None:
    (root / "session.json").write_text(json.dumps(payload), encoding="utf-8")


def patched_session_detection():
    def fake_detect(image_path: Path, _board: object, _detector: object, camera_id: str, side: str | None, index: int) -> ViewObservation:
        object_points = charuco_object_points()
        image_points = np.zeros((len(object_points), 1, 2), dtype=np.float32)
        return ViewObservation(
            camera_id=camera_id,
            side=side,
            index=index,
            image_size=(960, 640),
            object_points=object_points,
            image_points=image_points,
            ids=np.arange(len(object_points), dtype=np.int32).reshape(-1, 1),
            path=str(image_path),
        )

    return patch.multiple(
        "camera_calib_lab.solve",
        create_charuco_board=lambda _target: object(),
        create_detector=lambda _board: object(),
        detect_image_observation=fake_detect,
    )


def mono_package(camera_id: str, source_device: str) -> MonoCameraPackage:
    return MonoCameraPackage(
        package_dir=Path(f"/artifacts/calibration/{camera_id}"),
        package_json={"accepted": True, "source_device": source_device},
        camera_json={
            "camera_id": camera_id,
            "camera_matrix": np.eye(3).tolist(),
            "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0],
        },
        camera_matrix=np.eye(3),
        dist_coeffs=np.zeros((5, 1), dtype=np.float64),
        source_device=source_device,
    )


def write_mono_observations(path: Path, *, camera_id: str) -> None:
    object_points = charuco_object_points()
    k = camera_matrix()
    dist = np.zeros((5, 1), dtype=np.float64)
    views = []
    for index, (rvec, tvec) in enumerate(board_poses(), start=1):
        image_points, _ = cv2.projectPoints(object_points, rvec, tvec, k, dist)
        views.append(view_payload(camera_id, None, index, object_points, image_points))
    payload = {
        "schema_version": "calibration.charuco_observations.v1",
        "topology": "mono",
        "session_id": "synthetic_mono",
        "session_path": str(path.parent),
        "target": target_payload({}),
        "dry_run": True,
        "hardware_validated": False,
        "accepted": True,
        "accepted_view_count": len(views),
        "total_view_count": len(views),
        "pairs": [],
        "views": views,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_stereo_observations(path: Path) -> None:
    object_points = charuco_object_points()
    k = camera_matrix()
    dist = np.zeros((5, 1), dtype=np.float64)
    rotation_left_to_right = cv2.Rodrigues(np.array([0.0, 0.015, 0.0], dtype=np.float64))[0]
    translation_left_to_right = np.array([[0.08], [0.0], [0.0]], dtype=np.float64)
    views = []
    pairs = []
    for index, (left_rvec, left_tvec) in enumerate(board_poses(), start=1):
        left_image, _ = cv2.projectPoints(object_points, left_rvec, left_tvec, k, dist)
        left_rotation = cv2.Rodrigues(left_rvec)[0]
        right_rotation = rotation_left_to_right @ left_rotation
        right_tvec = rotation_left_to_right @ left_tvec.reshape(3, 1) + translation_left_to_right
        right_rvec, _ = cv2.Rodrigues(right_rotation)
        right_image, _ = cv2.projectPoints(object_points, right_rvec, right_tvec, k, dist)
        views.append(view_payload("cam1", "left", index, object_points, left_image))
        views.append(view_payload("cam2", "right", index, object_points, right_image))
        pairs.append(
            {
                "index": index,
                "accepted": True,
                "left_corner_count": int(len(object_points)),
                "right_corner_count": int(len(object_points)),
                "left_rejection_reason": None,
                "right_rejection_reason": None,
            }
        )
    payload = {
        "schema_version": "calibration.charuco_observations.v1",
        "topology": "stereo",
        "session_id": "synthetic_stereo",
        "session_path": str(path.parent),
        "target": target_payload({}),
        "dry_run": True,
        "hardware_validated": False,
        "accepted": True,
        "accepted_view_count": len(views),
        "accepted_pair_count": len(pairs),
        "total_view_count": len(views),
        "total_pair_count": len(pairs),
        "pairs": pairs,
        "views": views,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def view_payload(
    camera_id: str,
    side: str | None,
    index: int,
    object_points: np.ndarray,
    image_points: np.ndarray,
) -> dict:
    return {
        "accepted": True,
        "camera_id": camera_id,
        "side": side,
        "index": index,
        "path": f"{camera_id}_{index:04d}.png",
        "image_size": {"width": 960, "height": 640},
        "corner_count": int(len(object_points)),
        "marker_count": 0,
        "ids": list(range(len(object_points))),
        "object_points": object_points.reshape(-1, 3).tolist(),
        "image_points": image_points.reshape(-1, 2).tolist(),
    }


def charuco_object_points() -> np.ndarray:
    points = []
    for y in range(1, 9):
        for x in range(1, 14):
            points.append([x * 0.015, y * 0.015, 0.0])
    return np.asarray(points, dtype=np.float32).reshape(-1, 1, 3)


def camera_matrix() -> np.ndarray:
    return np.asarray([[900.0, 0.0, 480.0], [0.0, 905.0, 320.0], [0.0, 0.0, 1.0]], dtype=np.float64)


def board_poses() -> list[tuple[np.ndarray, np.ndarray]]:
    return [
        (np.array([0.08, -0.04, 0.02], dtype=np.float64), np.array([[-0.09], [-0.06], [0.75]], dtype=np.float64)),
        (np.array([-0.06, 0.05, -0.03], dtype=np.float64), np.array([[-0.02], [0.00], [0.82]], dtype=np.float64)),
        (np.array([0.03, 0.08, 0.05], dtype=np.float64), np.array([[0.05], [-0.03], [0.90]], dtype=np.float64)),
        (np.array([-0.04, -0.06, 0.07], dtype=np.float64), np.array([[0.10], [0.04], [1.00]], dtype=np.float64)),
        (np.array([0.10, 0.03, -0.06], dtype=np.float64), np.array([[-0.06], [0.06], [1.12]], dtype=np.float64)),
        (np.array([-0.08, 0.02, 0.04], dtype=np.float64), np.array([[0.02], [-0.05], [1.22]], dtype=np.float64)),
    ]


if __name__ == "__main__":
    unittest.main()
