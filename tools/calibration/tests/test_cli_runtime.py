from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tennisbot_calibration.cli import main


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def help_text(args: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    with pytest.raises(SystemExit) as exc_info:
        main([*args, "--help"])
    assert exc_info.value.code == 0
    return capsys.readouterr().out


def test_cli_help_exposes_required_commands(capsys: pytest.CaptureFixture[str]) -> None:
    top_help = help_text([], capsys)
    capture_help = help_text(["capture"], capsys)
    calibrate_help = help_text(["calibrate"], capsys)
    gui_help = help_text(["gui"], capsys)
    package_help = help_text(["package"], capsys)

    assert "capture" in top_help
    assert "calibrate" in top_help
    assert "gui" in top_help
    assert "package" in top_help
    assert "capture mono" in top_help
    assert "capture stereo" in top_help
    assert "inspect" in capture_help
    assert "detect-charuco" in capture_help
    assert "mono" in calibrate_help
    assert "gui mono" in top_help
    assert "gui stereo" in top_help
    assert "package verify" in top_help
    assert "mono" in capture_help
    assert "stereo" in capture_help
    assert "mono" in gui_help
    assert "stereo" in gui_help
    assert "verify" in package_help
    assert "import-camera-calib-lab" in package_help
    assert "scan-camera-calib-lab" in package_help
    assert "import-scanned-camera-calib-lab" in package_help


def test_capture_mono_dry_run_writes_session_frames_and_manifest(tmp_path: Path) -> None:
    output = tmp_path / "cam1_session"

    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--device",
                "/dev/video0",
                "--output",
                str(output),
                "--frame-count",
                "3",
                "--interval-ms",
                "0",
                "--width",
                "64",
                "--height",
                "48",
                "--prepare-uvc-controls",
                "--dry-run",
            ]
        )
        == 0
    )

    manifest = read_json(output / "manifest.json")
    assert manifest["topology"] == "mono"
    assert manifest["camera_id"] == "cam1"
    assert manifest["dry_run"] is True
    assert manifest["hardware_validated"] is False
    assert manifest["frame_count"] == 3
    assert manifest["uvc_controls"] == [
        {
            "device": "/dev/video0",
            "status": "skipped",
            "controls": "brightness=64,gain=255,auto_exposure=1,exposure_time_absolute=2047",
            "detail": "dry-run session; v4l2-ctl was not executed.",
        }
    ]
    assert len(manifest["files"]) == 3
    for rel_path in manifest["files"]:  # type: ignore[union-attr]
        assert (output / str(rel_path)).is_file()
    assert (output / "summary.md").is_file()
    assert (output / "review.html").is_file()


def test_capture_inspect_accepts_dry_run_session(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cam1_session"
    report = tmp_path / "inspection.md"
    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--output",
                str(output),
                "--frame-count",
                "2",
                "--interval-ms",
                "0",
                "--width",
                "64",
                "--height",
                "48",
                "--dry-run",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["capture", "inspect", "--session", str(output), "--output-report", str(report)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["ready_for_target_detection"] is True
    assert payload["image_count"] == 2
    assert payload["read_image_count"] == 2
    assert (output / "inspection.json").is_file()
    assert "# Calibration Capture Session Inspection" in report.read_text(encoding="utf-8")


def test_capture_inspect_rejects_low_contrast_frame(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cam1_session"
    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--output",
                str(output),
                "--frame-count",
                "1",
                "--interval-ms",
                "0",
                "--width",
                "64",
                "--height",
                "48",
                "--dry-run",
            ]
        )
        == 0
    )
    capsys.readouterr()
    blank = np.full((48, 64, 3), 80, dtype=np.uint8)
    assert cv2.imwrite(str(output / "frames" / "cam1_0001.png"), blank)

    assert main(["capture", "inspect", "--session", str(output)]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is False
    assert payload["ready_for_target_detection"] is False
    assert "low contrast / likely blank frame" in payload["issues"][0]


def test_capture_detect_charuco_accepts_rendered_board(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cam1_session"
    observations = tmp_path / "observations.json"
    report = tmp_path / "detect.md"
    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--output",
                str(output),
                "--frame-count",
                "1",
                "--interval-ms",
                "0",
                "--width",
                "960",
                "--height",
                "640",
                "--dry-run",
            ]
        )
        == 0
    )
    capsys.readouterr()
    write_rendered_charuco(output / "frames" / "cam1_0001.png", image_size=(960, 640))

    assert (
        main(
            [
                "capture",
                "detect-charuco",
                "--session",
                str(output),
                "--output",
                str(observations),
                "--output-report",
                str(report),
                "--min-corners",
                "6",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["accepted_view_count"] == 1
    assert payload["views"][0]["accepted"] is True
    assert payload["views"][0]["corner_count"] >= 6
    assert observations.is_file()
    assert "# Calibration ChArUco Detection" in report.read_text(encoding="utf-8")


def test_capture_detect_charuco_rejects_session_without_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "cam1_session"
    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--output",
                str(output),
                "--frame-count",
                "1",
                "--interval-ms",
                "0",
                "--width",
                "160",
                "--height",
                "120",
                "--dry-run",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["capture", "detect-charuco", "--session", str(output), "--min-corners", "6"]) == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is False
    assert payload["accepted_view_count"] == 0
    assert "need at least 6" in payload["views"][0]["rejection_reason"]


def test_calibrate_mono_solves_rendered_charuco_observations(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = tmp_path / "cam1_session"
    observations = tmp_path / "observations.json"
    package_dir = tmp_path / "calibration" / "cam1"
    assert (
        main(
            [
                "capture",
                "mono",
                "--camera-id",
                "cam1",
                "--output",
                str(session),
                "--frame-count",
                "5",
                "--interval-ms",
                "0",
                "--width",
                "960",
                "--height",
                "640",
                "--dry-run",
            ]
        )
        == 0
    )
    capsys.readouterr()
    write_warped_charuco_session(session, camera_id="cam1", image_size=(960, 640))
    assert (
        main(
            [
                "capture",
                "detect-charuco",
                "--session",
                str(session),
                "--output",
                str(observations),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "calibrate",
                "mono",
                "--observations",
                str(observations),
                "--output",
                str(package_dir),
                "--min-views",
                "3",
                "--max-rms-px",
                "5",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["camera_id"] == "cam1"
    assert payload["accepted_view_count"] == 5
    assert payload["rms_reprojection_px"] < 5
    assert main(["package", "verify", "--path", str(package_dir)]) == 0
    camera = read_json(package_dir / "camera.json")
    assert camera["camera_id"] == "cam1"
    assert len(camera["camera_matrix"]) == 3
    assert (package_dir / "summary.md").is_file()


def test_capture_stereo_dry_run_writes_pair_session(tmp_path: Path) -> None:
    output = tmp_path / "stereo_session"

    assert (
        main(
            [
                "capture",
                "stereo",
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--left-device",
                "/dev/video0",
                "--right-device",
                "/dev/video2",
                "--output",
                str(output),
                "--pair-count",
                "2",
                "--interval-ms",
                "0",
                "--width",
                "64",
                "--height",
                "48",
                "--dry-run",
            ]
        )
        == 0
    )

    manifest = read_json(output / "manifest.json")
    assert manifest["topology"] == "stereo"
    assert manifest["camera_ids"] == ["cam1", "cam2"]
    assert manifest["dry_run"] is True
    assert manifest["hardware_validated"] is False
    assert manifest["pair_count"] == 2
    pairs = manifest["pairs"]
    assert isinstance(pairs, list)
    for pair in pairs:
        assert (output / str(pair["left"])).is_file()
        assert (output / str(pair["right"])).is_file()
    assert (output / "summary.md").is_file()
    assert (output / "review.html").is_file()


def test_mono_dry_run_writes_required_package_files_for_cam1(tmp_path: Path) -> None:
    output = tmp_path / "cam1"

    assert main(["gui", "mono", "--camera-id", "cam1", "--output", str(output), "--dry-run"]) == 0

    for name in (
        "package.json",
        "camera.json",
        "verification.json",
        "calibration_opencv.yaml",
        "summary.md",
        "review.html",
    ):
        assert (output / name).is_file()
    package = read_json(output / "package.json")
    camera = read_json(output / "camera.json")
    assert package["camera_id"] == "cam1"
    assert package["dry_run"] is True
    assert package["hardware_validated"] is False
    assert camera["camera_id"] == "cam1"
    assert "dry-run/non-hardware evidence only" in (output / "summary.md").read_text(encoding="utf-8")


def test_stereo_dry_run_writes_required_package_files_for_cam1_cam2(tmp_path: Path) -> None:
    output = tmp_path / "stereo_cam1_cam2"

    assert (
        main(
            [
                "gui",
                "stereo",
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--output",
                str(output),
                "--dry-run",
            ]
        )
        == 0
    )

    for name in (
        "package.json",
        "cam1.json",
        "cam2.json",
        "stereo.json",
        "rectification.json",
        "verification.json",
        "calibration_opencv.yaml",
        "summary.md",
        "review.html",
    ):
        assert (output / name).is_file()
    package = read_json(output / "package.json")
    assert package["camera_ids"] == ["cam1", "cam2"]
    assert package["dry_run"] is True
    assert package["hardware_validated"] is False


def test_package_verify_accepts_generated_dry_run_mono_and_stereo(tmp_path: Path) -> None:
    mono = tmp_path / "cam1"
    stereo = tmp_path / "stereo_cam1_cam2"
    assert main(["gui", "mono", "--camera-id", "cam1", "--output", str(mono), "--dry-run"]) == 0
    assert (
        main(
            [
                "gui",
                "stereo",
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--output",
                str(stereo),
                "--dry-run",
            ]
        )
        == 0
    )

    assert main(["package", "verify", "--path", str(mono)]) == 0
    assert main(["package", "verify", "--path", str(stereo)]) == 0


def test_package_verify_rejects_accepted_false(tmp_path: Path) -> None:
    output = tmp_path / "cam1"
    assert main(["gui", "mono", "--camera-id", "cam1", "--output", str(output), "--dry-run"]) == 0
    package_path = output / "package.json"
    package = read_json(package_path)
    assert isinstance(package["quality"], dict)
    package["quality"]["accepted"] = False  # type: ignore[index]
    package_path.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert main(["package", "verify", "--path", str(output)]) == 1


def test_package_verify_rejects_missing_required_file(tmp_path: Path) -> None:
    output = tmp_path / "cam1"
    assert main(["gui", "mono", "--camera-id", "cam1", "--output", str(output), "--dry-run"]) == 0
    (output / "camera.json").unlink()

    assert main(["package", "verify", "--path", str(output)]) == 1


def test_package_verify_rejects_stereo_rectification_not_accepted(tmp_path: Path) -> None:
    output = tmp_path / "stereo_cam1_cam2"
    assert (
        main(
            [
                "gui",
                "stereo",
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--output",
                str(output),
                "--dry-run",
            ]
        )
        == 0
    )
    verification_path = output / "verification.json"
    verification = read_json(verification_path)
    assert isinstance(verification["rectification"], dict)
    verification["rectification"]["accepted"] = False  # type: ignore[index]
    verification_path.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert main(["package", "verify", "--path", str(output)]) == 1


def test_generated_stereo_rectification_uses_row_major_matrices_and_matching_camera_ids(tmp_path: Path) -> None:
    output = tmp_path / "stereo_cam1_cam2"
    assert (
        main(
            [
                "gui",
                "stereo",
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--output",
                str(output),
                "--dry-run",
            ]
        )
        == 0
    )
    rectification = read_json(output / "rectification.json")

    assert rectification["left_camera_id"] == "cam1"
    assert rectification["right_camera_id"] == "cam2"
    assert len(rectification["r1"]) == 3
    assert all(isinstance(row, list) and len(row) == 3 for row in rectification["r1"])  # type: ignore[index]
    assert len(rectification["p1"]) == 3
    assert all(isinstance(row, list) and len(row) == 4 for row in rectification["p1"])  # type: ignore[index]
    assert len(rectification["q"]) == 4
    assert all(isinstance(row, list) and len(row) == 4 for row in rectification["q"])  # type: ignore[index]


def test_import_camera_calib_lab_writes_verified_runtime_stereo_package(tmp_path: Path) -> None:
    source = write_camera_calib_lab_fixture(tmp_path / "source")
    output = tmp_path / "stereo_cam1_cam2"

    assert (
        main(
            [
                "package",
                "import-camera-calib-lab",
                "--cam1",
                str(source["cam1"]),
                "--cam2",
                str(source["cam2"]),
                "--stereo",
                str(source["stereo"]),
                "--output",
                str(output),
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
            ]
        )
        == 0
    )

    assert main(["package", "verify", "--path", str(output)]) == 0
    package = read_json(output / "package.json")
    stereo = read_json(output / "stereo.json")
    rectification = read_json(output / "rectification.json")
    verification = read_json(output / "verification.json")

    assert package["dry_run"] is False
    assert package["hardware_validated"] is True
    assert package["camera_ids"] == ["cam1", "cam2"]
    assert stereo["baseline_m"] == pytest.approx(0.12)
    assert len(stereo["essential_matrix"]) == 3
    assert len(stereo["fundamental_matrix"]) == 3
    assert len(rectification["p1"]) == 3
    assert all(isinstance(row, list) and len(row) == 4 for row in rectification["p1"])  # type: ignore[index]
    assert len(rectification["q"]) == 4
    assert verification["rectification"]["accepted"] is True  # type: ignore[index]
    assert "Imported from CameraCalibLab" in (output / "summary.md").read_text(encoding="utf-8")


def test_scan_camera_calib_lab_ranks_candidates_and_writes_markdown(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "runs" / "calibrations"
    source = write_camera_calib_lab_fixture(tmp_path / "source")
    write_json_fixture(root / "cam1" / "calibration.json", read_json(source["cam1"]))
    write_json_fixture(root / "cam2" / "calibration.json", read_json(source["cam2"]))
    write_json_fixture(root / "selected" / "calibration.json", read_json(source["stereo"]))
    weak = read_json(source["stereo"])
    weak["result_id"] = "weak_stereo"
    weak["metrics"]["stereo_rms_px"] = 5.0  # type: ignore[index]
    weak["metrics"]["epipolar_rms_px"] = 8.0  # type: ignore[index]
    weak["metrics"]["rectification_y_p95_px"] = 4.0  # type: ignore[index]
    write_json_fixture(root / "weak" / "calibration.json", weak)
    report = tmp_path / "scan.md"

    assert (
        main(
            [
                "package",
                "scan-camera-calib-lab",
                "--root",
                str(root),
                "--limit",
                "3",
                "--output-report",
                str(report),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["mono_candidates"] == 2
    assert payload["counts"]["stereo_candidates"] == 2
    assert payload["recommended_stereo"]["path"] == "selected/calibration.json"
    assert payload["recommended_stereo"]["metrics"]["stereo_rms_px"] == pytest.approx(0.5)
    assert payload["stereo_candidates"][1]["warning_count"] == 3
    report_text = report.read_text(encoding="utf-8")
    assert "# CameraCalibLab Calibration Candidate Scan" in report_text
    assert "`selected/calibration.json`" in report_text
    assert "`weak/calibration.json`" in report_text


def test_import_scanned_camera_calib_lab_selects_candidates_before_import(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "runs" / "calibrations"
    source = write_camera_calib_lab_fixture(tmp_path / "source")
    write_json_fixture(root / "cam1_current" / "calibration.json", read_json(source["cam1"]))
    write_json_fixture(root / "cam2_current" / "calibration.json", read_json(source["cam2"]))
    write_json_fixture(root / "stereo_current" / "calibration.json", read_json(source["stereo"]))
    output = tmp_path / "artifact"
    report = tmp_path / "scan.md"

    assert (
        main(
            [
                "package",
                "import-scanned-camera-calib-lab",
                "--root",
                str(root),
                "--cam1-pattern",
                "cam1_current",
                "--cam2-pattern",
                "cam2_current",
                "--output",
                str(output),
                "--left-camera-id",
                "cam1",
                "--right-camera-id",
                "cam2",
                "--output-report",
                str(report),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["accepted"] is True
    assert payload["selected"]["cam1"]["path"] == "cam1_current/calibration.json"
    assert payload["selected"]["cam2"]["path"] == "cam2_current/calibration.json"
    assert payload["selected"]["stereo"]["path"] == "stereo_current/calibration.json"
    assert main(["package", "verify", "--path", str(output)]) == 0
    package = read_json(output / "package.json")
    assert package["source_session"].endswith("stereo_current")
    assert report.is_file()


def write_camera_calib_lab_fixture(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True)
    cam1 = root / "cam1.json"
    cam2 = root / "cam2.json"
    stereo = root / "stereo.json"
    camera_matrix_left = [
        [900.0, 0.0, 640.0],
        [0.0, 900.0, 360.0],
        [0.0, 0.0, 1.0],
    ]
    camera_matrix_right = [
        [910.0, 0.0, 642.0],
        [0.0, 908.0, 358.0],
        [0.0, 0.0, 1.0],
    ]
    write_json_fixture(
        cam1,
        {
            "topology": "mono",
            "status": "ready",
            "created_at": "2026-06-29T00:00:00Z",
            "result_id": "fixture_cam1",
            "method_id": "fixture_mono",
            "image_size": [1280, 720],
            "camera_matrix": camera_matrix_left,
            "dist_coeffs": [0.01, -0.02, 0.0, 0.0, 0.0],
            "metrics": {"accepted_views": 20, "calibration_rms_px": 0.2},
            "validation": {"failures": [], "metrics": {"view_count": 20}},
        },
    )
    write_json_fixture(
        cam2,
        {
            "topology": "mono",
            "status": "ready",
            "created_at": "2026-06-29T00:00:00Z",
            "result_id": "fixture_cam2",
            "method_id": "fixture_mono",
            "image_size": [1280, 720],
            "camera_matrix": camera_matrix_right,
            "dist_coeffs": [0.011, -0.018, 0.0, 0.0, 0.0],
            "metrics": {"accepted_views": 22, "calibration_rms_px": 0.24},
            "validation": {"failures": [], "metrics": {"view_count": 22}},
        },
    )
    write_json_fixture(
        stereo,
        {
            "topology": "stereo",
            "status": "ready",
            "created_at": "2026-06-29T00:00:00Z",
            "result_id": "fixture_stereo",
            "method_id": "fixture_stereo",
            "image_size": [1280, 720],
            "rotation": [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            "translation": [0.12, 0.0, 0.0],
            "metrics": {
                "accepted_pairs": 18,
                "baseline_m": 0.12,
                "epipolar_rms_px": 0.4,
                "matched_point_count_min": 96,
                "rectification_y_p95_px": 0.6,
                "stereo_rms_px": 0.5,
            },
            "validation": {"failures": [], "metrics": {"pair_count": 18}},
        },
    )
    return {"cam1": cam1, "cam2": cam2, "stereo": stereo}


def write_json_fixture(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_rendered_charuco(path: Path, *, image_size: tuple[int, int]) -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    board = cv2.aruco.CharucoBoard((14, 9), 0.015, 0.011, dictionary)
    image = board.generateImage(image_size, marginSize=40)
    assert cv2.imwrite(str(path), image)


def write_warped_charuco_session(session: Path, *, camera_id: str, image_size: tuple[int, int]) -> None:
    width, height = image_size
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    board = cv2.aruco.CharucoBoard((14, 9), 0.015, 0.011, dictionary)
    texture = board.generateImage(image_size, marginSize=40)
    full_mask = np.full_like(texture, 255)
    source = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    quads = [
        [[80, 60], [860, 50], [880, 570], [95, 590]],
        [[55, 90], [885, 70], [840, 585], [120, 560]],
        [[120, 55], [830, 95], [900, 600], [70, 540]],
        [[90, 70], [900, 55], [850, 545], [100, 610]],
        [[65, 65], [835, 45], [915, 590], [145, 575]],
    ]
    for index, quad in enumerate(quads, start=1):
        homography = cv2.getPerspectiveTransform(source, np.float32(quad))
        image = np.full((height, width), 255, np.uint8)
        warped = cv2.warpPerspective(texture, homography, image_size, borderValue=255)
        mask = cv2.warpPerspective(full_mask, homography, image_size)
        image[mask > 0] = warped[mask > 0]
        assert cv2.imwrite(str(session / "frames" / f"{camera_id}_{index:04d}.png"), image)
