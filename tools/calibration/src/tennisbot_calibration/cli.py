from __future__ import annotations

import argparse
import json
from pathlib import Path

from tennisbot_calibration.artifacts import write_mono_dry_run, write_stereo_dry_run
from tennisbot_calibration.import_camera_calib_lab import import_camera_calib_lab_package
from tennisbot_calibration.verify import verify_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tennisbot-calibration",
        description="TennisBot calibration artifact tooling.",
        epilog=(
            "Workflows: gui mono, gui stereo, package verify. "
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


def require_dry_run(dry_run: bool) -> None:
    if not dry_run:
        raise SystemExit("Wave 5 GUI runtime only supports --dry-run and does not open physical cameras.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
