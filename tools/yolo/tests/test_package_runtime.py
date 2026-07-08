from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tennisbot_yolo.package import (
    REQUIRED_FILES,
    PackageVerificationError,
    create_model_package,
    verify_model_package,
)
from tennisbot_yolo.cli import resolve_cli_path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tennisbot_yolo.cli", *args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_resolve_cli_path_uses_current_working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert resolve_cli_path(Path("relative/path")) == tmp_path / "relative" / "path"


def test_cli_help_exposes_package_create_and_verify() -> None:
    help_result = run_cli("--help")
    package_help = run_cli("package", "--help")
    detect_help = run_cli("detect-gui", "--help")
    sprites_help = run_cli("sprites", "--help")
    augment_help = run_cli("augment", "--help")
    benchmark_help = run_cli("benchmark", "--help")
    benchmark_final_raw_split_help = run_cli("benchmark", "build-final-raw-split", "--help")
    benchmark_final_raw_eval_help = run_cli("benchmark", "eval-final-raw", "--help")
    benchmark_roi_help = run_cli("benchmark", "roi-sample", "--help")
    benchmark_roi_track_help = run_cli("benchmark", "roi-track", "--help")

    assert help_result.returncode == 0
    assert "package" in help_result.stdout
    assert "detect-gui" in help_result.stdout
    assert "sprites" in help_result.stdout
    assert "augment" in help_result.stdout
    assert "benchmark" in help_result.stdout
    assert package_help.returncode == 0
    assert "create" in package_help.stdout
    assert "verify" in package_help.stdout
    assert detect_help.returncode == 0
    assert "--devices" in detect_help.stdout
    assert sprites_help.returncode == 0
    assert "extract" in sprites_help.stdout
    assert "review" in sprites_help.stdout
    assert augment_help.returncode == 0
    assert "copy-paste" in augment_help.stdout
    assert benchmark_help.returncode == 0
    assert "tiles" in benchmark_help.stdout
    assert "build-final-raw-split" in benchmark_help.stdout
    assert benchmark_final_raw_split_help.returncode == 0
    assert "--fixed-cloudy-negative-holdout-count" in benchmark_final_raw_split_help.stdout
    assert "eval-final-raw" in benchmark_help.stdout
    assert benchmark_final_raw_eval_help.returncode == 0
    assert "--conf-values" in benchmark_final_raw_eval_help.stdout
    assert "roi-sample" in benchmark_help.stdout
    assert "roi-track" in benchmark_help.stdout
    assert benchmark_roi_help.returncode == 0
    assert "--roi-profile" in benchmark_roi_help.stdout
    assert benchmark_roi_track_help.returncode == 0
    assert "--roi-width" in benchmark_roi_track_help.stdout
    assert "--roi-model" in benchmark_roi_track_help.stdout


def test_benchmark_tiles_dry_run_does_not_require_model_or_detector_dependencies() -> None:
    result = run_cli(
        "benchmark",
        "tiles",
        "--dry-run",
        "--frame-width",
        "3840",
        "--frame-height",
        "2160",
        "--tile-profile",
        "tile_1536x864:1536:864:160",
        "--imgsz-values",
        "960,1280",
    )

    assert result.returncode == 0
    assert "tile_1536x864" in result.stdout
    assert "960" in result.stdout
    assert "1280" in result.stdout
    assert "9 (3x3)" in result.stdout


def test_benchmark_roi_sample_dry_run_does_not_require_model_or_detector_dependencies(tmp_path: Path) -> None:
    sample_list = tmp_path / "val.txt"
    sample_list.write_text("/tmp/frame_000001.jpg\n/tmp/frame_000002.jpg\n", encoding="utf-8")

    result = run_cli(
        "benchmark",
        "roi-sample",
        "--dry-run",
        "--sample-list",
        str(sample_list),
        "--sample-limit",
        "1",
        "--full-imgsz-values",
        "416,512",
        "--roi-profile",
        "roi_test:960:540:512",
    )

    assert result.returncode == 0
    assert "samples=1" in result.stdout
    assert "416,512" in result.stdout
    assert "roi_test" in result.stdout


def test_benchmark_roi_track_dry_run_does_not_require_model_or_detector_dependencies(tmp_path: Path) -> None:
    (tmp_path / "session_cam1_frame_000002.jpg").write_bytes(b"not an image")
    (tmp_path / "session_cam1_frame_000001.jpg").write_bytes(b"not an image")

    result = run_cli(
        "benchmark",
        "roi-track",
        "--dry-run",
        "--sequence-glob",
        str(tmp_path / "session_cam1_frame_*.jpg"),
        "--sample-limit",
        "1",
    )

    assert result.returncode == 0
    assert "samples=1" in result.stdout
    assert "session_cam1_frame_000001.jpg" in result.stdout


def test_benchmark_build_final_raw_split_generates_manifest_without_detector_dependencies(tmp_path: Path) -> None:
    from PIL import Image

    auto_images = tmp_path / "auto" / "images"
    auto_labels = tmp_path / "auto" / "labels"
    fixed_images = tmp_path / "fixed_source" / "images"
    fixed_labels = tmp_path / "fixed_source" / "labels"
    for directory in (auto_images, auto_labels, fixed_images, fixed_labels):
        directory.mkdir(parents=True)

    def write_image_and_label(image_path: Path, label_path: Path, label: str) -> None:
        Image.new("RGB", (100, 100), color=(30, 40, 50)).save(image_path)
        label_path.write_text(label, encoding="utf-8")

    write_image_and_label(
        auto_images / "indoor_ball_sample_cam1_frame_000000.jpg",
        auto_labels / "indoor_ball_sample_cam1_frame_000000.txt",
        "",
    )
    write_image_and_label(
        auto_images / "indoor_ball_sample02_cam1_frame_000000.jpg",
        auto_labels / "indoor_ball_sample02_cam1_frame_000000.txt",
        "0 0.5 0.5 0.50 0.50\n",
    )
    write_image_and_label(
        fixed_images / "20260707_141324_cam1_frame_000000.jpg",
        fixed_labels / "20260707_141324_cam1_frame_000000.txt",
        "0 0.5 0.5 0.10 0.10\n",
    )
    write_image_and_label(
        fixed_images / "20260707_140826_cam1_frame_000000.jpg",
        fixed_labels / "20260707_140826_cam1_frame_000000.txt",
        "0 0.5 0.5 0.30 0.30\n",
    )
    write_image_and_label(
        fixed_images / "cloudy_background_cam1_frame_000000.jpg",
        fixed_labels / "cloudy_background_cam1_frame_000000.txt",
        "",
    )
    write_image_and_label(
        fixed_images / "cloudy_background_cam1_frame_000001.jpg",
        fixed_labels / "cloudy_background_cam1_frame_000001.txt",
        "",
    )

    output_dir = tmp_path / "split"
    result = run_cli(
        "benchmark",
        "build-final-raw-split",
        "--auto-exposure-images-root",
        str(auto_images),
        "--fixed-exposure-source-root",
        str(tmp_path / "fixed_source"),
        "--output-dir",
        str(output_dir),
        "--auto-benchmark-session",
        "indoor_ball_sample_cam1",
        "--fixed-benchmark-session",
        "20260707_141324_cam1",
        "--fixed-cloudy-negative-holdout-count",
        "1",
        "--seed",
        "7",
    )

    assert result.returncode == 0, result.stderr + result.stdout
    summary = read_json(output_dir / "summary.json")
    assert summary["split_counts"] == {"benchmark": 3, "train_pool": 3}
    assert summary["bucket_counts"]["benchmark:auto_exposure:empty"] == 1
    assert summary["bucket_counts"]["benchmark:fixed_exposure:small"] == 1
    assert summary["bucket_counts"]["train_pool:auto_exposure:large"] == 1
    assert summary["bucket_counts"]["train_pool:fixed_exposure:medium"] == 1

    manifest = output_dir / "manifest.jsonl"
    assert summary["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    benchmark_paths = set((output_dir / "benchmark.txt").read_text(encoding="utf-8").splitlines())
    train_pool_paths = set((output_dir / "train_pool.txt").read_text(encoding="utf-8").splitlines())
    assert len(benchmark_paths & train_pool_paths) == 0


def test_benchmark_eval_final_raw_dry_run_does_not_require_model_or_detector_dependencies(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {
            "box_count": 1,
            "dataset": "auto_exposure",
            "height": 100,
            "image": "/tmp/auto.jpg",
            "label": "/tmp/auto.txt",
            "max_box_dim_px": 60.0,
            "positive": True,
            "reason": "session_holdout",
            "session": "auto_session",
            "split": "benchmark",
            "target_bucket": "large",
            "width": 100,
        },
        {
            "box_count": 0,
            "dataset": "fixed_exposure",
            "height": 100,
            "image": "/tmp/fixed.jpg",
            "label": "/tmp/fixed.txt",
            "max_box_dim_px": None,
            "positive": False,
            "reason": "default_train_pool",
            "session": "fixed_session",
            "split": "train_pool",
            "target_bucket": "empty",
            "width": 100,
        },
    ]
    manifest.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    result = run_cli(
        "benchmark",
        "eval-final-raw",
        "--dry-run",
        "--manifest",
        str(manifest),
        "--split",
        "benchmark",
        "--conf-values",
        "0.25,0.05",
    )

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["records"] == 1
    assert summary["dataset_counts"] == {"auto_exposure": 1}
    assert summary["bucket_counts"] == {"large": 1}


def test_detect_gui_dry_run_does_not_require_camera_or_detector_dependencies(tmp_path: Path) -> None:
    model = tmp_path / "model.pt"
    result = run_cli(
        "detect-gui",
        "--dry-run",
        "--devices",
        "/dev/video0,/dev/video2",
        "--model",
        str(model),
    )

    assert result.returncode == 0
    assert "detect_gui=dry-run" in result.stdout
    assert "devices=/dev/video0,/dev/video2" in result.stdout


def test_dry_run_package_writes_required_files_and_marks_non_inference(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)

    assert REQUIRED_FILES.issubset({path.name for path in output.iterdir()})
    package_json = read_json(output / "package.json")
    metrics = read_json(output / "eval_metrics.json")
    report = (output / "eval_report.md").read_text(encoding="utf-8")

    assert package_json["dry_run"] is True
    assert package_json["inference_ready"] is False
    assert metrics["dry_run"] is True
    assert metrics["inference_ready"] is False
    assert "non-inference" in report
    assert "No training, inference" in report
    assert (output / package_json["models"]["onnx"]["path"]).is_file()


def test_package_creation_from_onnx_records_bytes_and_sha256(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.onnx"
    fixture.write_bytes(b"fake onnx bytes")

    output = create_model_package(
        tmp_path / "package",
        model_onnx=fixture,
        default_model="onnx",
    )
    package_json = read_json(output / "package.json")
    model_entry = package_json["models"]["onnx"]

    assert model_entry["bytes"] == len(b"fake onnx bytes")
    assert model_entry["sha256"] == hashlib.sha256(b"fake onnx bytes").hexdigest()
    assert model_entry["runtime"] == "onnxruntime"


def test_package_creation_accepts_supplied_eval_files(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.onnx"
    metrics = tmp_path / "eval_metrics.json"
    report = tmp_path / "eval_report.md"
    fixture.write_bytes(b"fake onnx bytes")
    metrics.write_text(
        json.dumps(
            {
                "dry_run": False,
                "inference_ready": True,
                "dataset": {"labels": 109, "positives": 109, "negatives": 0},
                "model": {"precision": None, "recall": None, "map50": None, "map50_95": None},
                "static_smoke": {"detected_at_threshold": 109, "threshold": 0.05},
            }
        ),
        encoding="utf-8",
    )
    report.write_text("# Eval\n\nStatic smoke report.\n", encoding="utf-8")

    output = create_model_package(
        tmp_path / "package",
        model_onnx=fixture,
        default_model="onnx",
        eval_metrics=metrics,
        eval_report=report,
    )

    assert read_json(output / "eval_metrics.json")["static_smoke"]["detected_at_threshold"] == 109
    assert "Static smoke report" in (output / "eval_report.md").read_text(encoding="utf-8")


def test_package_verification_accepts_generated_packages(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)

    verify_model_package(output)


def test_package_verification_rejects_missing_selected_model_file(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    (output / "model.onnx").unlink()

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "missing model file" in str(exc_info.value)


def test_package_verification_rejects_checksum_mismatch(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    (output / "model.onnx").write_bytes(b"changed")

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "model sha256 mismatch" in str(exc_info.value)


def test_package_verification_checks_all_declared_model_files(tmp_path: Path) -> None:
    pt_fixture = tmp_path / "fixture.pt"
    onnx_fixture = tmp_path / "fixture.onnx"
    pt_fixture.write_bytes(b"fake pt bytes")
    onnx_fixture.write_bytes(b"fake onnx bytes")
    output = create_model_package(
        tmp_path / "package",
        model_pt=pt_fixture,
        model_onnx=onnx_fixture,
        default_model="onnx",
    )
    (output / "model.pt").unlink()

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "missing model file: model.pt" in str(exc_info.value)


def test_package_verification_rejects_boolean_model_bytes(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    package_json = read_json(output / "package.json")
    package_json["models"]["onnx"]["bytes"] = True
    (output / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "package.json.models.onnx.bytes must be a finite number" in str(exc_info.value)


def test_package_verification_rejects_labels_without_class_zero_tennis_ball(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    labels = read_json(output / "labels.json")
    labels["classes"] = [{"id": 1, "name": "tennis_ball"}]
    (output / "labels.json").write_text(json.dumps(labels), encoding="utf-8")

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "labels.json.classes must include class id 0 named tennis_ball" in str(exc_info.value)


def test_package_verification_rejects_out_of_range_confidence_threshold(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    postprocessing = read_json(output / "postprocessing.json")
    postprocessing["confidence_threshold"] = 1.5
    (output / "postprocessing.json").write_text(json.dumps(postprocessing), encoding="utf-8")

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "postprocessing.json.confidence_threshold must be between 0 and 1" in str(exc_info.value)


def test_package_verification_rejects_malformed_preprocessing_input_size(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    preprocessing = read_json(output / "preprocessing.json")
    preprocessing["input_size"] = {"width": 1280}
    (output / "preprocessing.json").write_text(json.dumps(preprocessing), encoding="utf-8")

    with pytest.raises(PackageVerificationError) as exc_info:
        verify_model_package(output)

    assert "preprocessing.json.input_size must include positive numeric width and height" in str(exc_info.value)


def test_generated_package_metadata_is_shaped_for_wave4_runtime_loader(tmp_path: Path) -> None:
    output = create_model_package(tmp_path / "package", dry_run=True)
    package_json = read_json(output / "package.json")
    labels_json = read_json(output / "labels.json")
    preprocessing_json = read_json(output / "preprocessing.json")
    postprocessing_json = read_json(output / "postprocessing.json")

    assert package_json["contract"] == "tennisbot.yolo-model-package"
    assert package_json["default_model"] == "onnx"
    assert package_json["models"]["onnx"].keys() >= {"path", "sha256", "bytes", "runtime"}
    assert labels_json == {
        "classes": [{"id": 0, "name": "tennis_ball"}],
        "format": "YOLO detect normalized xywh",
    }
    assert preprocessing_json["input_color"] == "RGB"
    assert preprocessing_json["input_size"] == {"width": 1280, "height": 1280}
    assert preprocessing_json["resize"]["mode"] == "letterbox"
    assert postprocessing_json["class_id"] == 0
    assert postprocessing_json["confidence_threshold"] == 0.05
