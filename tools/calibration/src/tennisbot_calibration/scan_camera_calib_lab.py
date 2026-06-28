from __future__ import annotations

from pathlib import Path
from typing import Any

from tennisbot_calibration.import_camera_calib_lab import QUALITY_WARNING_LIMITS, source_validation_failures
from tennisbot_calibration.io import read_json


STEREO_METRICS = (
    "stereo_rms_px",
    "epipolar_rms_px",
    "rectification_y_p95_px",
)
MONO_METRICS = (
    "calibration_rms_px",
    "accepted_views",
)


def scan_camera_calib_lab(root: Path, *, limit: int = 10) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(root.rglob("calibration.json")):
        try:
            payload = read_json(path)
        except (OSError, ValueError) as exc:
            skipped.append({"path": display_path(path, root), "reason": str(exc)})
            continue
        topology = payload.get("topology")
        if topology not in {"mono", "stereo"}:
            skipped.append({"path": display_path(path, root), "reason": f"unsupported topology: {topology!r}"})
            continue
        candidates.append(candidate_summary(path, root, payload))

    mono_candidates = sorted(
        (candidate for candidate in candidates if candidate["topology"] == "mono"),
        key=mono_sort_key,
    )
    stereo_candidates = sorted(
        (candidate for candidate in candidates if candidate["topology"] == "stereo"),
        key=stereo_sort_key,
    )
    limited_stereo = stereo_candidates[: max(limit, 0)]
    limited_mono = mono_candidates[: max(limit, 0)]
    return {
        "schema_version": "calibration.camera_calib_lab_scan.v1",
        "root": str(root),
        "counts": {
            "candidate_files": len(candidates),
            "mono_candidates": len(mono_candidates),
            "stereo_candidates": len(stereo_candidates),
            "skipped_files": len(skipped),
        },
        "recommended_stereo": limited_stereo[0] if limited_stereo else None,
        "stereo_candidates": limited_stereo,
        "mono_candidates": limited_mono,
        "skipped": skipped,
    }


def select_candidate(
    scan: dict[str, Any],
    *,
    topology: str,
    pattern: str | None,
) -> dict[str, Any]:
    if topology == "stereo" and pattern is None:
        candidate = scan.get("recommended_stereo")
        if isinstance(candidate, dict):
            return candidate
        raise ValueError("no recommended stereo candidate found")

    if not pattern:
        raise ValueError(f"{topology} selection requires a path pattern")

    key = "stereo_candidates" if topology == "stereo" else "mono_candidates"
    candidates = scan.get(key)
    if not isinstance(candidates, list):
        raise ValueError(f"scan payload does not contain {key}")
    matches = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict)
        and str(candidate.get("topology")) == topology
        and pattern in str(candidate.get("path"))
    ]
    if not matches:
        raise ValueError(f"no {topology} candidate path contains pattern {pattern!r}")
    return sorted(matches, key=lambda candidate: (not bool(candidate.get("accepted")), float(candidate.get("score", 0.0))))[0]


def candidate_path(root: Path, candidate: dict[str, Any]) -> Path:
    path = Path(str(candidate["path"]))
    if path.is_absolute():
        return path
    return root / path


def candidate_summary(path: Path, root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    failures = source_validation_failures(payload)
    topology = str(payload.get("topology"))
    warnings = quality_warnings(metrics) if topology == "stereo" else []
    return {
        "path": display_path(path, root),
        "topology": topology,
        "status": payload.get("status"),
        "accepted": payload.get("status") == "ready" and failures == [],
        "warning_count": len(warnings),
        "warnings": warnings,
        "validation_failures": failures,
        "result_id": payload.get("result_id"),
        "method_id": payload.get("method_id"),
        "created_at": payload.get("created_at"),
        "image_size": payload.get("image_size"),
        "metrics": selected_metrics(metrics, topology),
        "score": score_candidate(metrics, topology, failures, warnings),
    }


def selected_metrics(metrics: dict[str, Any], topology: str) -> dict[str, float | int | None]:
    names = STEREO_METRICS + ("baseline_m", "accepted_pairs", "matched_point_count_min")
    if topology == "mono":
        names = MONO_METRICS
    return {name: metric_number(metrics, name) for name in names}


def quality_warnings(metrics: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for name in STEREO_METRICS:
        value = metric_float(metrics, name)
        limit = QUALITY_WARNING_LIMITS.get(name)
        if value is not None and limit is not None and value > limit:
            warnings.append(f"{name}={value:.3f} exceeds runtime-quality review threshold {limit:.3f}")
    return warnings


def score_candidate(
    metrics: dict[str, Any],
    topology: str,
    failures: list[Any],
    warnings: list[str],
) -> float:
    if topology == "mono":
        rms = metric_float(metrics, "calibration_rms_px")
        accepted_views = metric_float(metrics, "accepted_views") or 0.0
        return missing_penalty(rms) + (rms or 0.0) - min(accepted_views, 200.0) / 1000.0 + len(failures) * 1000.0

    metric_values = [metric_float(metrics, name) for name in STEREO_METRICS]
    missing = sum(1 for value in metric_values if value is None)
    metric_sum = sum(value if value is not None else 1000.0 for value in metric_values)
    accepted_pairs = metric_float(metrics, "accepted_pairs") or 0.0
    matched_points = metric_float(metrics, "matched_point_count_min") or 0.0
    return (
        len(failures) * 10000.0
        + len(warnings) * 1000.0
        + missing * 1000.0
        + metric_sum
        - min(accepted_pairs, 500.0) / 100.0
        - min(matched_points, 1000.0) / 10000.0
    )


def mono_sort_key(candidate: dict[str, Any]) -> tuple[bool, float, str]:
    return (not bool(candidate["accepted"]), float(candidate["score"]), str(candidate["path"]))


def stereo_sort_key(candidate: dict[str, Any]) -> tuple[bool, int, float, str]:
    return (
        not bool(candidate["accepted"]),
        int(candidate["warning_count"]),
        float(candidate["score"]),
        str(candidate["path"]),
    )


def metric_number(metrics: dict[str, Any], name: str) -> float | int | None:
    value = metrics.get(name)
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_float(metrics: dict[str, Any], name: str) -> float | None:
    value = metric_number(metrics, name)
    if value is None:
        return None
    return float(value)


def missing_penalty(value: object) -> float:
    return 1000.0 if value is None else 0.0


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def write_scan_report(path: Path, scan: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CameraCalibLab Calibration Candidate Scan",
        "",
        f"- root: {scan['root']}",
        f"- candidate_files: {scan['counts']['candidate_files']}",
        f"- mono_candidates: {scan['counts']['mono_candidates']}",
        f"- stereo_candidates: {scan['counts']['stereo_candidates']}",
        f"- skipped_files: {scan['counts']['skipped_files']}",
        "",
        "## Recommended Stereo Candidate",
        "",
    ]
    recommended = scan.get("recommended_stereo")
    if isinstance(recommended, dict):
        lines.extend(candidate_lines(recommended))
    else:
        lines.append("No stereo candidate found.")
    lines.extend(["", "## Top Stereo Candidates", ""])
    lines.extend(table_lines(scan.get("stereo_candidates", []), stereo=True))
    lines.extend(["", "## Top Mono Candidates", ""])
    lines.extend(table_lines(scan.get("mono_candidates", []), stereo=False))
    if scan.get("skipped"):
        lines.extend(["", "## Skipped Files", ""])
        for item in scan["skipped"]:
            lines.append(f"- `{item['path']}`: {item['reason']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def candidate_lines(candidate: dict[str, Any]) -> list[str]:
    metrics = candidate.get("metrics", {})
    lines = [
        f"- path: `{candidate['path']}`",
        f"- accepted: {candidate['accepted']}",
        f"- warning_count: {candidate['warning_count']}",
        f"- score: {candidate['score']:.6f}",
    ]
    for name, value in metrics.items():
        lines.append(f"- {name}: {value}")
    warnings = candidate.get("warnings") or []
    if warnings:
        lines.append("- warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    return lines


def table_lines(candidates: list[dict[str, Any]], *, stereo: bool) -> list[str]:
    if not candidates:
        return ["No candidates."]
    if stereo:
        lines = [
            "| rank | path | accepted | warnings | stereo_rms_px | epipolar_rms_px | rectification_y_p95_px | baseline_m | score |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for index, candidate in enumerate(candidates, start=1):
            metrics = candidate["metrics"]
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(index),
                        f"`{candidate['path']}`",
                        str(candidate["accepted"]),
                        str(candidate["warning_count"]),
                        format_value(metrics.get("stereo_rms_px")),
                        format_value(metrics.get("epipolar_rms_px")),
                        format_value(metrics.get("rectification_y_p95_px")),
                        format_value(metrics.get("baseline_m")),
                        f"{candidate['score']:.6f}",
                    ]
                )
                + " |"
            )
        return lines

    lines = [
        "| rank | path | accepted | calibration_rms_px | accepted_views | score |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for index, candidate in enumerate(candidates, start=1):
        metrics = candidate["metrics"]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    f"`{candidate['path']}`",
                    str(candidate["accepted"]),
                    format_value(metrics.get("calibration_rms_px")),
                    format_value(metrics.get("accepted_views")),
                    f"{candidate['score']:.6f}",
                ]
            )
            + " |"
        )
    return lines


def format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
