from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennisbot_calibration.artifacts import write_mono_dry_run, write_stereo_dry_run
from tennisbot_calibration.import_camera_calib_lab import import_camera_calib_lab_package
from tennisbot_calibration.scan_camera_calib_lab import (
    candidate_path,
    scan_camera_calib_lab,
    select_candidate,
    write_scan_report,
)
from tennisbot_calibration.verify import verify_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tennisbot-calibration",
        description="TennisBot calibration artifact tooling.",
        epilog=(
            "Workflows: gui mono, gui stereo, package verify, package scan-camera-calib-lab, "
            "package import-scanned-camera-calib-lab. "
            "Wave 5 GUI commands support dry-run/non-hardware output only."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    configure_gui(subparsers)
    configure_package(subparsers)
    return parser


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
