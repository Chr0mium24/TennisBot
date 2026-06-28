from __future__ import annotations

import shutil
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import read_json, sha256_file, write_json

CONTRACT = "tennisbot.yolo-model-package"
CONTRACT_VERSION = "0.1.0"
PACKAGE_NAME = "tennis_ball_yolo"
DRY_RUN_MODEL_BYTES = b"tennisbot-yolo dry-run placeholder model\n"
REQUIRED_FILES = {
    "package.json",
    "metadata.json",
    "labels.json",
    "preprocessing.json",
    "postprocessing.json",
    "eval_report.md",
    "eval_metrics.json",
    "package_manifest.json",
}

RUNTIMES = {
    "pt": "ultralytics",
    "onnx": "onnxruntime",
    "rknn": "rknn",
}


@dataclass(frozen=True)
class ModelSource:
    key: str
    path: Path


class PackageVerificationError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_model_package(
    output_dir: Path,
    *,
    default_model: str = "onnx",
    model_pt: Path | None = None,
    model_onnx: Path | None = None,
    model_rknn: Path | None = None,
    dry_run: bool = False,
) -> Path:
    model_sources = [
        ModelSource("pt", model_pt) if model_pt is not None else None,
        ModelSource("onnx", model_onnx) if model_onnx is not None else None,
        ModelSource("rknn", model_rknn) if model_rknn is not None else None,
    ]
    supplied_models = [source for source in model_sources if source is not None]
    if dry_run and supplied_models:
        raise ValueError("--dry-run cannot be combined with supplied model files")
    if not dry_run and not supplied_models:
        raise ValueError("provide at least one model file or use --dry-run")
    if default_model not in RUNTIMES:
        raise ValueError(f"unsupported default model: {default_model}")

    output_dir = output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    if dry_run:
        dry_model = output_dir / "model.onnx"
        dry_model.write_bytes(DRY_RUN_MODEL_BYTES)
        models = {"onnx": _model_entry(dry_model, "onnx")}
        default_model = "onnx"
    else:
        models = {}
        for source in supplied_models:
            source_path = source.path.expanduser().resolve()
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            target = output_dir / f"model.{source.key}"
            shutil.copy2(source_path, target)
            models[source.key] = _model_entry(target, source.key)
        if default_model not in models:
            raise ValueError(f"default_model {default_model!r} does not reference a supplied model")

    labels = _labels_json()
    preprocessing = _preprocessing_json()
    postprocessing = _postprocessing_json()
    eval_metrics = _eval_metrics_json(dry_run=dry_run)
    created_at = utc_now_iso()
    package_json = _package_json(
        created_at=created_at,
        models=models,
        default_model=default_model,
        dry_run=dry_run,
    )

    write_json(output_dir / "package.json", package_json)
    write_json(output_dir / "metadata.json", package_json)
    write_json(output_dir / "labels.json", labels)
    write_json(output_dir / "preprocessing.json", preprocessing)
    write_json(output_dir / "postprocessing.json", postprocessing)
    write_json(output_dir / "eval_metrics.json", eval_metrics)
    (output_dir / "eval_report.md").write_text(_eval_report(dry_run=dry_run), encoding="utf-8")

    manifest = _manifest_json(output_dir=output_dir, created_at=created_at)
    write_json(output_dir / "package_manifest.json", manifest)
    return output_dir


def verify_model_package(package_dir: Path) -> None:
    package_dir = package_dir.resolve()
    errors: list[str] = []
    package_path = package_dir / "package.json"
    if not package_path.is_file():
        raise PackageVerificationError(["missing package.json"])

    package_json = _load_json(package_path, errors)
    if not isinstance(package_json, dict):
        raise PackageVerificationError(errors or ["package.json must be an object"])

    if package_json.get("contract") != CONTRACT:
        errors.append(f"unsupported contract: {package_json.get('contract')!r}")
    if package_json.get("contract_version") != CONTRACT_VERSION:
        errors.append(f"unsupported contract_version: {package_json.get('contract_version')!r}")

    labels_path = _package_file(package_dir, package_json.get("labels"), "labels.json")
    labels_json = _load_json(labels_path, errors)
    if not _has_tennis_ball_class_zero(labels_json):
        errors.append("labels.json.classes must include class id 0 named tennis_ball")

    preprocessing_path = _package_file(package_dir, package_json.get("preprocessing"), "preprocessing.json")
    preprocessing_json = _load_json(preprocessing_path, errors)
    if not _valid_input_size(preprocessing_json):
        errors.append("preprocessing.json.input_size must include positive numeric width and height")

    postprocessing_path = _package_file(package_dir, package_json.get("postprocessing"), "postprocessing.json")
    postprocessing_json = _load_json(postprocessing_path, errors)
    threshold = postprocessing_json.get("confidence_threshold") if isinstance(postprocessing_json, dict) else None
    if not is_finite_number(threshold) or not 0 <= threshold <= 1:
        errors.append("postprocessing.json.confidence_threshold must be between 0 and 1")

    models = package_json.get("models")
    default_model = package_json.get("default_model")
    if not isinstance(models, dict) or not models:
        errors.append("package.json.models must include at least one model entry")
    elif not isinstance(default_model, str) or default_model not in models:
        errors.append("package.json.default_model must reference an existing model entry")

    if isinstance(models, dict):
        for key, value in sorted(models.items()):
            _verify_model_entry(package_dir, str(key), value, errors)

    if errors:
        raise PackageVerificationError(errors)


def _model_entry(path: Path, key: str) -> dict[str, object]:
    return {
        "path": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "runtime": RUNTIMES[key],
    }


def _package_json(
    *,
    created_at: str,
    models: dict[str, dict[str, object]],
    default_model: str,
    dry_run: bool,
) -> dict[str, object]:
    return {
        "name": PACKAGE_NAME,
        "version": "0.1.0",
        "contract": CONTRACT,
        "contract_version": CONTRACT_VERSION,
        "created_at": created_at,
        "producer": {
            "tool": "tools/yolo",
            "source": "Wave 6 YOLO tool runtime",
        },
        "models": models,
        "default_model": default_model,
        "labels": "labels.json",
        "preprocessing": "preprocessing.json",
        "postprocessing": "postprocessing.json",
        "evaluation": {
            "report": "eval_report.md",
            "metrics": "eval_metrics.json",
        },
        "dry_run": dry_run,
        "inference_ready": not dry_run,
    }


def _labels_json() -> dict[str, object]:
    return {
        "classes": [
            {
                "id": 0,
                "name": "tennis_ball",
            }
        ],
        "format": "YOLO detect normalized xywh",
    }


def _preprocessing_json() -> dict[str, object]:
    return {
        "input_color": "RGB",
        "input_size": {
            "width": 1280,
            "height": 1280,
        },
        "resize": {
            "mode": "letterbox",
            "preserve_aspect_ratio": True,
            "stride": 32,
        },
        "normalization": {
            "scale": 1 / 255,
            "mean": [0.0, 0.0, 0.0],
            "std": [1.0, 1.0, 1.0],
        },
    }


def _postprocessing_json() -> dict[str, object]:
    return {
        "task": "single-class tennis ball detection",
        "box_format": "xyxy_pixels",
        "source_box_format": "YOLO normalized xywh",
        "class_id": 0,
        "confidence_threshold": 0.05,
        "nms_iou_threshold": 0.5,
        "max_detections": 10,
        "runtime_output": "detections",
    }


def _eval_metrics_json(*, dry_run: bool) -> dict[str, object]:
    return {
        "dry_run": dry_run,
        "inference_ready": not dry_run,
        "dataset": {
            "labels": 0,
            "positives": 0,
            "negatives": 0,
            "cameras": {
                "cam1": 0,
                "cam2": 0,
            },
        },
        "model": {
            "precision": None,
            "recall": None,
            "map50": None,
            "map50_95": None,
        },
    }


def _eval_report(*, dry_run: bool) -> str:
    if dry_run:
        return (
            "# Evaluation Report\n\n"
            "This is a dry-run runtime package generated for loader and contract validation only.\n\n"
            "The included model file is a deterministic placeholder and is non-inference. "
            "No training, inference, evaluation dataset, accuracy, precision, recall, or mAP is claimed.\n"
        )
    return (
        "# Evaluation Report\n\n"
        "No evaluation report was supplied by this package command. Model metrics are null in "
        "`eval_metrics.json` until a real evaluation report is attached by a later training workflow.\n"
    )


def _manifest_json(*, output_dir: Path, created_at: str) -> dict[str, object]:
    files = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "package_manifest.json":
            files.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return {
        "created_at": created_at,
        "files": files,
    }


def _load_json(path: Path, errors: list[str]) -> Any:
    if not path.is_file():
        errors.append(f"missing {path.name}")
        return None
    try:
        return read_json(path)
    except ValueError as exc:
        errors.append(f"malformed {path.name}: {exc}")
        return None


def _package_file(package_dir: Path, value: object, fallback: str) -> Path:
    if isinstance(value, str) and value:
        return package_dir / value
    return package_dir / fallback


def _has_tennis_ball_class_zero(labels_json: Any) -> bool:
    if not isinstance(labels_json, dict):
        return False
    classes = labels_json.get("classes")
    if not isinstance(classes, list):
        return False
    return any(
        isinstance(item, dict) and item.get("id") == 0 and item.get("name") == "tennis_ball"
        for item in classes
    )


def _valid_input_size(preprocessing_json: Any) -> bool:
    if not isinstance(preprocessing_json, dict):
        return False
    input_size = preprocessing_json.get("input_size")
    if not isinstance(input_size, dict):
        return False
    width = input_size.get("width")
    height = input_size.get("height")
    return is_finite_number(width) and is_finite_number(height) and width > 0 and height > 0


def _verify_model_entry(package_dir: Path, key: str, selected: Any, errors: list[str]) -> None:
    if not isinstance(selected, dict):
        errors.append(f"package.json.models.{key} must be an object")
        return
    model_path = selected.get("path")
    expected_sha256 = selected.get("sha256")
    expected_bytes = selected.get("bytes")
    runtime = selected.get("runtime")
    if not isinstance(model_path, str) or not model_path:
        errors.append(f"package.json.models.{key}.path must be a non-empty string")
        return
    if not isinstance(expected_sha256, str) or not expected_sha256:
        errors.append(f"package.json.models.{key}.sha256 must be a non-empty string")
    if not is_finite_number(expected_bytes):
        errors.append(f"package.json.models.{key}.bytes must be a finite number")
    if not isinstance(runtime, str) or not runtime:
        errors.append(f"package.json.models.{key}.runtime must be a non-empty string")

    full_path = package_dir / model_path
    if not full_path.is_file():
        errors.append(f"missing model file: {model_path}")
        return
    if is_finite_number(expected_bytes) and full_path.stat().st_size != expected_bytes:
        errors.append(f"model bytes mismatch: {model_path}")
    if isinstance(expected_sha256, str) and expected_sha256 and sha256_file(full_path) != expected_sha256:
        errors.append(f"model sha256 mismatch: {model_path}")


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
