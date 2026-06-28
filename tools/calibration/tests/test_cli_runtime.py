from __future__ import annotations

import json
from pathlib import Path

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
    gui_help = help_text(["gui"], capsys)
    package_help = help_text(["package"], capsys)

    assert "gui" in top_help
    assert "package" in top_help
    assert "gui mono" in top_help
    assert "gui stereo" in top_help
    assert "package verify" in top_help
    assert "mono" in gui_help
    assert "stereo" in gui_help
    assert "verify" in package_help
    assert "import-camera-calib-lab" in package_help


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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
