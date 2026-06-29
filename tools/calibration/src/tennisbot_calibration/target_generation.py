from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.capture_sessions import now_utc
from tennisbot_calibration.charuco_detection import DEFAULT_CHARUCO_PROFILE, charuco_board
from tennisbot_calibration.io import write_json

MM_PER_METER = 1000.0
MM_PER_INCH = 25.4


def generate_charuco_target(
    *,
    output: Path,
    output_svg: Path | None = None,
    output_metadata: Path | None = None,
    output_report: Path | None = None,
    dpi: int = 300,
    margin_mm: float = 10.0,
) -> dict[str, Any]:
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    if margin_mm < 0:
        raise ValueError("margin_mm must be non-negative")

    target = {"type": "charuco", **DEFAULT_CHARUCO_PROFILE}
    board = charuco_board(target)
    board_width_mm = int(target["squares_x"]) * float(target["square_size_m"]) * MM_PER_METER
    board_height_mm = int(target["squares_y"]) * float(target["square_size_m"]) * MM_PER_METER
    board_width_px = mm_to_pixels(board_width_mm, dpi)
    board_height_px = mm_to_pixels(board_height_mm, dpi)
    margin_px = mm_to_pixels(margin_mm, dpi)
    board_image = board.generateImage((board_width_px, board_height_px), marginSize=0)
    sheet = np.full(
        (board_height_px + 2 * margin_px, board_width_px + 2 * margin_px),
        255,
        dtype=np.uint8,
    )
    sheet[margin_px : margin_px + board_height_px, margin_px : margin_px + board_width_px] = board_image

    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), sheet):
        raise RuntimeError(f"failed to write target PNG: {output}")

    svg_path = output_svg or output.with_suffix(".svg")
    metadata_path = output_metadata or output.with_suffix(".json")
    write_svg_sheet(
        svg_path,
        png_bytes=output.read_bytes(),
        width_mm=board_width_mm + 2 * margin_mm,
        height_mm=board_height_mm + 2 * margin_mm,
    )

    metadata = {
        "schema_version": "calibration.target_sheet.v1",
        "created_at": now_utc(),
        "accepted": True,
        "target": target,
        "dpi": dpi,
        "margin_mm": margin_mm,
        "board_size_mm": {"width": board_width_mm, "height": board_height_mm},
        "sheet_size_mm": {
            "width": board_width_mm + 2 * margin_mm,
            "height": board_height_mm + 2 * margin_mm,
        },
        "image_size_px": {"width": int(sheet.shape[1]), "height": int(sheet.shape[0])},
        "files": {
            "png": str(output),
            "svg": str(svg_path),
            "metadata": str(metadata_path),
        },
        "print_instructions": [
            "Print the SVG at 100% scale with no fit-to-page scaling.",
            "After printing, measure one square; it should be 15.0 mm.",
            "Use this same target for mono cam1, mono cam2, and stereo captures.",
        ],
    }
    write_json(metadata_path, metadata)
    if output_report is not None:
        write_target_report(output_report, metadata)
    return metadata


def record_target_print_check(
    *,
    measured_square_mm: float,
    output: Path,
    output_report: Path | None = None,
    target_metadata: Path | None = None,
    expected_square_mm: float = 15.0,
    tolerance_mm: float = 0.2,
) -> dict[str, Any]:
    if measured_square_mm <= 0:
        raise ValueError("measured_square_mm must be positive")
    if expected_square_mm <= 0:
        raise ValueError("expected_square_mm must be positive")
    if tolerance_mm < 0:
        raise ValueError("tolerance_mm must be non-negative")

    delta_mm = abs(measured_square_mm - expected_square_mm)
    accepted = delta_mm <= tolerance_mm
    result = {
        "schema_version": "calibration.target_print_check.v1",
        "created_at": now_utc(),
        "target_metadata": str(target_metadata) if target_metadata else "../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
        "expected_square_mm": expected_square_mm,
        "measured_square_mm": measured_square_mm,
        "tolerance_mm": tolerance_mm,
        "delta_mm": round(delta_mm, 4),
        "accepted": accepted,
        "next_step": (
            "Proceed to cam1 mono, cam2 mono, and stereo calibration captures."
            if accepted
            else "Fix printer scaling and reprint the target before camera capture."
        ),
    }
    write_json(output, result)
    if output_report is not None:
        write_target_print_check_report(output_report, result)
    return result


def mm_to_pixels(mm: float, dpi: int) -> int:
    return max(1, int(round((mm / MM_PER_INCH) * dpi)))


def write_svg_sheet(path: Path, *, png_bytes: bytes, width_mm: float, height_mm: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = base64.b64encode(png_bytes).decode("ascii")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:.3f}mm" height="{height_mm:.3f}mm" viewBox="0 0 {width_mm:.3f} {height_mm:.3f}">
  <image href="data:image/png;base64,{encoded}" x="0" y="0" width="{width_mm:.3f}" height="{height_mm:.3f}" preserveAspectRatio="none"/>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def write_target_report(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = metadata["target"]
    lines = [
        "# Calibration ChArUco Target Sheet",
        "",
        f"- created_at: {metadata['created_at']}",
        f"- type: {target['type']}",
        f"- profile: {target['profile']}",
        f"- dictionary: {target['dictionary']}",
        f"- squares: {target['squares_x']} x {target['squares_y']}",
        f"- square_size_mm: {float(target['square_size_m']) * MM_PER_METER:.3f}",
        f"- marker_size_mm: {float(target['marker_size_m']) * MM_PER_METER:.3f}",
        f"- board_size_mm: {metadata['board_size_mm']['width']:.3f} x {metadata['board_size_mm']['height']:.3f}",
        f"- sheet_size_mm: {metadata['sheet_size_mm']['width']:.3f} x {metadata['sheet_size_mm']['height']:.3f}",
        f"- dpi: {metadata['dpi']}",
        f"- margin_mm: {metadata['margin_mm']}",
        "",
        "## Files",
        "",
        f"- png: `{metadata['files']['png']}`",
        f"- svg: `{metadata['files']['svg']}`",
        f"- metadata: `{metadata['files']['metadata']}`",
        "",
        "## Print Check",
        "",
        "- Print the SVG at 100% scale with no fit-to-page scaling.",
        "- Measure one printed square; it should be 15.0 mm.",
        "- Keep the target flat, sharp, and visible in both camera views.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_target_print_check_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Calibration Target Print Check",
        "",
        f"- created_at: {result['created_at']}",
        f"- accepted: {result['accepted']}",
        f"- target_metadata: `{result['target_metadata']}`",
        f"- expected_square_mm: {result['expected_square_mm']}",
        f"- measured_square_mm: {result['measured_square_mm']}",
        f"- tolerance_mm: {result['tolerance_mm']}",
        f"- delta_mm: {result['delta_mm']}",
        f"- next_step: {result['next_step']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
