from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennisbot_calibration.artifacts import write_mono_dry_run, write_stereo_dry_run
from tennisbot_calibration.capture_sessions import (
    capture_mono_session,
    capture_stereo_session,
    inspect_capture_session,
)
from tennisbot_calibration.charuco_detection import detect_charuco_session
from tennisbot_calibration.import_camera_calib_lab import import_camera_calib_lab_package
from tennisbot_calibration.mono_solve import solve_mono_calibration
from tennisbot_calibration.scan_camera_calib_lab import (
    candidate_path,
    scan_camera_calib_lab,
    select_candidate,
    write_scan_report,
)
from tennisbot_calibration.stereo_solve import solve_stereo_calibration
from tennisbot_calibration.target_generation import generate_charuco_target, record_target_print_check
from tennisbot_calibration.verify import verify_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tennisbot-calibration",
        description="TennisBot calibration artifact tooling.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Workflows:\n"
            "  capture mono\n"
            "  capture stereo\n"
            "  capture inspect\n"
            "  capture detect-charuco\n"
            "  calibrate mono\n"
            "  calibrate stereo\n"
            "  gui mono\n"
            "  gui stereo\n"
            "  target charuco\n"
            "  target record-print-check\n"
            "  package verify\n"
            "  package scan-camera-calib-lab\n"
            "  package import-scanned-camera-calib-lab\n\n"
            "Wave 5 GUI commands support dry-run/non-hardware output only."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    configure_capture(subparsers)
    configure_calibrate(subparsers)
    configure_gui(subparsers)
    configure_target(subparsers)
    configure_package(subparsers)
    return parser


def configure_capture(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    capture = subparsers.add_parser("capture", help="Capture calibration image sessions from local cameras.")
    capture_subparsers = capture.add_subparsers(dest="capture_command", required=True)

    mono = capture_subparsers.add_parser("mono", help="Capture a mono calibration image session.")
    mono.add_argument("--camera-id", required=True)
    mono.add_argument("--device", default="/dev/video0")
    mono.add_argument("--output", required=True)
    mono.add_argument("--frame-count", type=int, default=20)
    mono.add_argument("--interval-ms", type=int, default=500)
    mono.add_argument("--width", type=int, default=1280)
    mono.add_argument("--height", type=int, default=720)
    mono.add_argument("--fourcc", default="MJPG")
    mono.add_argument("--fps", type=int, default=30)
    mono.add_argument("--dry-run", action="store_true", help="Write deterministic synthetic frames instead of opening hardware.")
    mono.add_argument(
        "--prepare-uvc-controls",
        action="store_true",
        help="Apply the local high-brightness UVC exposure controls before real capture.",
    )
    mono.set_defaults(handler=capture_mono)

    stereo = capture_subparsers.add_parser("stereo", help="Capture a stereo calibration image-pair session.")
    stereo.add_argument("--left-camera-id", required=True)
    stereo.add_argument("--right-camera-id", required=True)
    stereo.add_argument("--left-device", default="/dev/video0")
    stereo.add_argument("--right-device", default="/dev/video2")
    stereo.add_argument("--output", required=True)
    stereo.add_argument("--pair-count", type=int, default=20)
    stereo.add_argument("--interval-ms", type=int, default=500)
    stereo.add_argument("--width", type=int, default=1280)
    stereo.add_argument("--height", type=int, default=720)
    stereo.add_argument("--fourcc", default="MJPG")
    stereo.add_argument("--fps", type=int, default=30)
    stereo.add_argument("--dry-run", action="store_true", help="Write deterministic synthetic frame pairs instead of opening hardware.")
    stereo.add_argument(
        "--prepare-uvc-controls",
        action="store_true",
        help="Apply the local high-brightness UVC exposure controls before real capture.",
    )
    stereo.set_defaults(handler=capture_stereo)

    inspect = capture_subparsers.add_parser("inspect", help="Inspect a captured session for basic image quality.")
    inspect.add_argument("--session", required=True, help="Capture session directory containing manifest.json.")
    inspect.add_argument("--output-report", default=None, help="Optional Markdown inspection report path.")
    inspect.set_defaults(handler=capture_inspect)

    detect_charuco = capture_subparsers.add_parser(
        "detect-charuco",
        help="Detect ChArUco observations from a captured session.",
    )
    detect_charuco.add_argument("--session", required=True, help="Capture session directory containing manifest.json.")
    detect_charuco.add_argument("--output", default=None, help="Observation JSON path; defaults to <session>/observations.json.")
    detect_charuco.add_argument("--output-report", default=None, help="Optional Markdown detection report path.")
    detect_charuco.add_argument("--min-corners", type=int, default=6, help="Minimum ChArUco corners required per view.")
    detect_charuco.set_defaults(handler=capture_detect_charuco)


def configure_calibrate(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    calibrate = subparsers.add_parser("calibrate", help="Solve calibration packages from accepted observations.")
    calibrate_subparsers = calibrate.add_subparsers(dest="calibrate_command", required=True)

    mono = calibrate_subparsers.add_parser("mono", help="Solve a mono camera calibration package.")
    mono.add_argument("--observations", required=True, help="ChArUco observations JSON from capture detect-charuco.")
    mono.add_argument("--output", required=True, help="Output mono package directory under artifacts/calibration.")
    mono.add_argument("--camera-id", default=None, help="Camera id to solve when observations contain multiple cameras.")
    mono.add_argument("--min-views", type=int, default=8)
    mono.add_argument("--max-rms-px", type=float, default=1.0)
    mono.set_defaults(handler=calibrate_mono)

    stereo = calibrate_subparsers.add_parser("stereo", help="Solve a stereo calibration package.")
    stereo.add_argument("--observations", required=True, help="Stereo ChArUco observations JSON from capture detect-charuco.")
    stereo.add_argument("--left-mono", required=True, help="Left mono package directory.")
    stereo.add_argument("--right-mono", required=True, help="Right mono package directory.")
    stereo.add_argument("--output", required=True, help="Output stereo package directory under artifacts/calibration.")
    stereo.add_argument("--min-pairs", type=int, default=8)
    stereo.add_argument("--min-common-corners", type=int, default=12)
    stereo.add_argument("--max-rms-px", type=float, default=2.0)
    stereo.set_defaults(handler=calibrate_stereo)


def configure_gui(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    gui = subparsers.add_parser("gui", help="Run local calibration review workflows.")
    gui_subparsers = gui.add_subparsers(dest="gui_command", required=True)

    mono = gui_subparsers.add_parser("mono", help="Create a mono calibration package through the GUI workflow.")
    mono.add_argument("--camera-id", required=True)
    mono.add_argument("--output", required=True)
    mono.add_argument("--dry-run", action="store_true", help="Write deterministic non-hardware review artifacts.")
    mono.set_defaults(handler=gui_mono)

    stereo = gui_subparsers.add_parser("stereo", help="Create a stereo calibration package through the GUI workflow.")
    stereo.add_argument("--left-camera-id", required=True)
    stereo.add_argument("--right-camera-id", required=True)
    stereo.add_argument("--output", required=True)
    stereo.add_argument("--dry-run", action="store_true", help="Write deterministic non-hardware review artifacts.")
    stereo.set_defaults(handler=gui_stereo)


def configure_target(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    target = subparsers.add_parser("target", help="Generate printable calibration targets.")
    target_subparsers = target.add_subparsers(dest="target_command", required=True)

    charuco = target_subparsers.add_parser("charuco", help="Generate the DFOptix ChArUco target sheet.")
    charuco.add_argument("--output", required=True, help="Output PNG path under artifacts/calibration_targets.")
    charuco.add_argument("--output-svg", default=None, help="Optional SVG sheet path; defaults to <output>.svg.")
    charuco.add_argument("--output-metadata", default=None, help="Optional metadata JSON path; defaults to <output>.json.")
    charuco.add_argument("--output-report", default=None, help="Optional Markdown report path.")
    charuco.add_argument("--dpi", type=int, default=300)
    charuco.add_argument("--margin-mm", type=float, default=10.0)
    charuco.set_defaults(handler=target_charuco)

    print_check = target_subparsers.add_parser(
        "record-print-check",
        help="Record the measured square size after printing the target.",
    )
    print_check.add_argument("--measured-square-mm", type=float, required=True)
    print_check.add_argument("--tolerance-mm", type=float, default=0.2)
    print_check.add_argument(
        "--target-metadata",
        default="../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
        help="Target metadata JSON used for printing.",
    )
    print_check.add_argument(
        "--output",
        default="../../artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json",
        help="Output print-check JSON path.",
    )
    print_check.add_argument("--output-report", default=None, help="Optional Markdown report path.")
    print_check.set_defaults(handler=target_record_print_check)


def configure_package(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    package = subparsers.add_parser("package", help="Import or verify calibration artifact packages.")
    package_subparsers = package.add_subparsers(dest="package_command", required=True)
    verify = package_subparsers.add_parser("verify", help="Verify a calibration package directory.")
    verify.add_argument("--path", required=True)
    verify.set_defaults(handler=package_verify)

    importer = package_subparsers.add_parser(
        "import-camera-calib-lab",
        help="Import existing CameraCalibLab mono/stereo JSON into a runtime stereo package.",
    )
    importer.add_argument("--cam1", required=True, help="Path to CameraCalibLab cam1 mono calibration.json.")
    importer.add_argument("--cam2", required=True, help="Path to CameraCalibLab cam2 mono calibration.json.")
    importer.add_argument("--stereo", required=True, help="Path to CameraCalibLab stereo calibration.json.")
    importer.add_argument("--output", required=True, help="Output package directory under artifacts/calibration.")
    importer.add_argument("--left-camera-id", default="cam1")
    importer.add_argument("--right-camera-id", default="cam2")
    importer.add_argument("--source-session", default=None)
    importer.set_defaults(handler=package_import_camera_calib_lab)

    scan = package_subparsers.add_parser(
        "scan-camera-calib-lab",
        help="Rank existing CameraCalibLab calibration.json outputs before import.",
    )
    scan.add_argument("--root", required=True, help="Directory to scan recursively for calibration.json files.")
    scan.add_argument("--limit", type=int, default=10, help="Maximum mono/stereo candidates to include in output.")
    scan.add_argument("--output-report", default=None, help="Optional Markdown report path.")
    scan.set_defaults(handler=package_scan_camera_calib_lab)

    scanned_import = package_subparsers.add_parser(
        "import-scanned-camera-calib-lab",
        help="Scan CameraCalibLab outputs, select candidates, import, and verify a runtime stereo package.",
    )
    scanned_import.add_argument("--root", required=True, help="Directory to scan recursively for calibration.json files.")
    scanned_import.add_argument("--cam1-pattern", required=True, help="Substring that selects the left mono candidate path.")
    scanned_import.add_argument("--cam2-pattern", required=True, help="Substring that selects the right mono candidate path.")
    scanned_import.add_argument(
        "--stereo-pattern",
        default=None,
        help="Optional substring that selects the stereo candidate path; defaults to the best ranked stereo candidate.",
    )
    scanned_import.add_argument("--output", required=True, help="Output package directory under artifacts/calibration.")
    scanned_import.add_argument("--left-camera-id", default="cam1")
    scanned_import.add_argument("--right-camera-id", default="cam2")
    scanned_import.add_argument("--limit", type=int, default=20, help="Maximum mono/stereo candidates considered.")
    scanned_import.add_argument("--output-report", default=None, help="Optional Markdown scan report path.")
    scanned_import.add_argument("--source-session", default=None)
    scanned_import.set_defaults(handler=package_import_scanned_camera_calib_lab)


def capture_mono(args: argparse.Namespace) -> int:
    manifest = capture_mono_session(
        camera_id=args.camera_id,
        device=args.device,
        output=Path(args.output),
        frame_count=args.frame_count,
        interval_ms=args.interval_ms,
        width=args.width,
        height=args.height,
        fourcc=args.fourcc,
        fps=args.fps,
        dry_run=args.dry_run,
        prepare_uvc_controls=args.prepare_uvc_controls,
    )
    print(json.dumps({"accepted": True, "output": args.output, "session": manifest}, indent=2, sort_keys=True))
    return 0


def capture_stereo(args: argparse.Namespace) -> int:
    manifest = capture_stereo_session(
        left_camera_id=args.left_camera_id,
        right_camera_id=args.right_camera_id,
        left_device=args.left_device,
        right_device=args.right_device,
        output=Path(args.output),
        pair_count=args.pair_count,
        interval_ms=args.interval_ms,
        width=args.width,
        height=args.height,
        fourcc=args.fourcc,
        fps=args.fps,
        dry_run=args.dry_run,
        prepare_uvc_controls=args.prepare_uvc_controls,
    )
    print(json.dumps({"accepted": True, "output": args.output, "session": manifest}, indent=2, sort_keys=True))
    return 0


def capture_inspect(args: argparse.Namespace) -> int:
    result = inspect_capture_session(
        session=Path(args.session),
        output_report=Path(args.output_report) if args.output_report else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


def capture_detect_charuco(args: argparse.Namespace) -> int:
    result = detect_charuco_session(
        session=Path(args.session),
        output=Path(args.output) if args.output else None,
        output_report=Path(args.output_report) if args.output_report else None,
        min_corners=args.min_corners,
    )
    print(json.dumps(charuco_detection_summary(result), indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


def charuco_detection_summary(result: dict[str, object]) -> dict[str, object]:
    views = result.get("views", [])
    assert isinstance(views, list)
    return {
        "accepted": result["accepted"],
        "accepted_pair_count": result["accepted_pair_count"],
        "accepted_view_count": result["accepted_view_count"],
        "output": result["output_path"],
        "recommendation": result["recommendation"],
        "session_id": result["session_id"],
        "topology": result["topology"],
        "total_pair_count": result["total_pair_count"],
        "total_view_count": result["total_view_count"],
        "views": [
            {
                "path": view["path"],
                "side": view["side"],
                "accepted": view["accepted"],
                "corner_count": view["corner_count"],
                "marker_count": view["marker_count"],
                "rejection_reason": view.get("rejection_reason"),
            }
            for view in views
        ],
    }


def calibrate_mono(args: argparse.Namespace) -> int:
    result = solve_mono_calibration(
        observations_path=Path(args.observations),
        output=Path(args.output),
        camera_id=args.camera_id,
        min_views=args.min_views,
        max_rms_px=args.max_rms_px,
    )
    verification = verify_package(Path(args.output))
    print(
        json.dumps(
            {
                "accepted": verification["accepted"],
                "output": args.output,
                "camera_id": result["package"]["camera_id"],
                "rms_reprojection_px": result["package"]["quality"]["rms_reprojection_px"],
                "accepted_view_count": result["package"]["quality"]["accepted_view_count"],
                "package": result["package"],
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verification["accepted"] else 1


def calibrate_stereo(args: argparse.Namespace) -> int:
    result = solve_stereo_calibration(
        observations_path=Path(args.observations),
        left_mono=Path(args.left_mono),
        right_mono=Path(args.right_mono),
        output=Path(args.output),
        min_pairs=args.min_pairs,
        min_common_corners=args.min_common_corners,
        max_rms_px=args.max_rms_px,
    )
    verification = verify_package(Path(args.output))
    print(
        json.dumps(
            {
                "accepted": verification["accepted"],
                "output": args.output,
                "camera_ids": result["package"]["camera_ids"],
                "stereo_rms_reprojection_px": result["package"]["quality"]["stereo_rms_reprojection_px"],
                "accepted_pair_count": result["package"]["quality"]["accepted_pair_count"],
                "baseline_m": result["stereo"]["baseline_m"],
                "package": result["package"],
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verification["accepted"] else 1


def gui_mono(args: argparse.Namespace) -> int:
    require_dry_run(args.dry_run)
    package = write_mono_dry_run(args.camera_id, Path(args.output))
    print(json.dumps({"accepted": True, "dry_run": True, "output": args.output, "package": package}, indent=2))
    return 0


def gui_stereo(args: argparse.Namespace) -> int:
    require_dry_run(args.dry_run)
    package = write_stereo_dry_run(args.left_camera_id, args.right_camera_id, Path(args.output))
    print(json.dumps({"accepted": True, "dry_run": True, "output": args.output, "package": package}, indent=2))
    return 0


def target_charuco(args: argparse.Namespace) -> int:
    metadata = generate_charuco_target(
        output=Path(args.output),
        output_svg=Path(args.output_svg) if args.output_svg else None,
        output_metadata=Path(args.output_metadata) if args.output_metadata else None,
        output_report=Path(args.output_report) if args.output_report else None,
        dpi=args.dpi,
        margin_mm=args.margin_mm,
    )
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


def target_record_print_check(args: argparse.Namespace) -> int:
    result = record_target_print_check(
        measured_square_mm=args.measured_square_mm,
        tolerance_mm=args.tolerance_mm,
        target_metadata=Path(args.target_metadata) if args.target_metadata else None,
        output=Path(args.output),
        output_report=Path(args.output_report) if args.output_report else None,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


def package_verify(args: argparse.Namespace) -> int:
    result = verify_package(Path(args.path))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] else 1


def package_import_camera_calib_lab(args: argparse.Namespace) -> int:
    package = import_camera_calib_lab_package(
        cam1_path=Path(args.cam1),
        cam2_path=Path(args.cam2),
        stereo_path=Path(args.stereo),
        output=Path(args.output),
        left_camera_id=args.left_camera_id,
        right_camera_id=args.right_camera_id,
        source_session=args.source_session,
    )
    verification = verify_package(Path(args.output))
    print(
        json.dumps(
            {
                "accepted": verification["accepted"],
                "dry_run": False,
                "hardware_validated": True,
                "output": args.output,
                "package": package,
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verification["accepted"] else 1


def package_scan_camera_calib_lab(args: argparse.Namespace) -> int:
    scan = scan_camera_calib_lab(Path(args.root), limit=args.limit)
    if args.output_report:
        write_scan_report(Path(args.output_report), scan)
    print(json.dumps(scan, indent=2, sort_keys=True))
    return 0


def package_import_scanned_camera_calib_lab(args: argparse.Namespace) -> int:
    root = Path(args.root)
    scan = scan_camera_calib_lab(root, limit=args.limit)
    if args.output_report:
        write_scan_report(Path(args.output_report), scan)
    cam1 = select_candidate(scan, topology="mono", pattern=args.cam1_pattern)
    cam2 = select_candidate(scan, topology="mono", pattern=args.cam2_pattern)
    stereo = select_candidate(scan, topology="stereo", pattern=args.stereo_pattern)
    stereo_path = candidate_path(root, stereo)
    package = import_camera_calib_lab_package(
        cam1_path=candidate_path(root, cam1),
        cam2_path=candidate_path(root, cam2),
        stereo_path=stereo_path,
        output=Path(args.output),
        left_camera_id=args.left_camera_id,
        right_camera_id=args.right_camera_id,
        source_session=args.source_session or str(stereo_path.parent),
    )
    verification = verify_package(Path(args.output))
    print(
        json.dumps(
            {
                "accepted": verification["accepted"],
                "dry_run": False,
                "hardware_validated": True,
                "output": args.output,
                "selected": {
                    "cam1": cam1,
                    "cam2": cam2,
                    "stereo": stereo,
                },
                "scan_counts": scan["counts"],
                "package": package,
                "verification": verification,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if verification["accepted"] else 1


def require_dry_run(dry_run: bool) -> None:
    if not dry_run:
        raise SystemExit("Wave 5 GUI runtime only supports --dry-run and does not open physical cameras.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
