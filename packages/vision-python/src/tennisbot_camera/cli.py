from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

from .capture import FrameSource, StereoFrameSource
from .config import load_camera_config
from .controls import apply_command, print_json, report_payload, show_command, stable_aliases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="camera.py", description="TennisBot camera discovery and controls")
    parser.add_argument("--config", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="list configured and available cameras")
    list_parser.add_argument("--json", action="store_true")
    check = sub.add_parser("check", help="open/read and inspect configured cameras")
    check.add_argument("target", choices=["cam1", "cam2", "stereo"], nargs="?", default="stereo")
    check.add_argument("--profile", default="runtime")
    check.add_argument("--json", action="store_true")
    preview = sub.add_parser("preview", help="raw camera preview")
    preview.add_argument("target", choices=["cam1", "cam2", "stereo"])
    preview.add_argument("--duration", type=float)
    controls = sub.add_parser("controls", help="show or apply V4L2 controls")
    controls_sub = controls.add_subparsers(dest="operation", required=True)
    for operation in ("show", "apply"):
        item = controls_sub.add_parser(operation)
        item.add_argument("target", choices=["cam1", "cam2", "stereo"])
        item.add_argument("--profile", default="runtime")
        item.add_argument("--dry-run", action="store_true")
        item.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_camera_config(args.config)
    if args.command == "list":
        return command_list(config, args.json)
    if args.command == "check":
        return command_check(config, args)
    if args.command == "preview":
        return command_preview(config, args.target, args.duration)
    return command_controls(config, args)


def command_list(config, as_json: bool) -> int:
    configured = [
        {"camera_id": camera.camera_id, "role": camera.role, "device": camera.device,
         "exists": Path(camera.device).exists(), "stable_aliases": stable_aliases(Path(camera.device))}
        for camera in config.cameras.values()
    ]
    payload = {"configured": configured, "available": sorted(glob.glob("/dev/video*"))}
    if as_json:
        print_json(payload)
    else:
        for item in configured:
            state = "present" if item["exists"] else "missing"
            print(f"{item['camera_id']} ({item['role']}): {item['device']} [{state}]")
        print("available: " + (", ".join(payload["available"]) or "none"))
    return 0


def command_check(config, args) -> int:
    expected = config.profile(args.profile)
    reports = []
    failed = False
    for camera in config.devices(args.target):
        control = subprocess.run(show_command(camera.device), text=True, capture_output=True, check=False)
        report = report_payload(camera.camera_id, camera.device, control)
        try:
            with FrameSource(camera, config) as source:
                frame = source.read()
            report.update({"read_ok": True, "width": frame.image.shape[1], "height": frame.image.shape[0],
                           "brightness": float(frame.image.mean()), "profile": args.profile,
                           "expected_controls": dict(expected)})
        except RuntimeError as error:
            report.update({"read_ok": False, "read_error": str(error)})
            failed = True
        reports.append(report)
    if args.json:
        print_json(reports)
    else:
        for report in reports:
            print(f"{report['camera_id']} {report['device']}: " + ("OK" if report.get("read_ok") else "FAIL"))
            if report.get("read_ok"):
                print(f"  negotiated={report['width']}x{report['height']} brightness={report['brightness']:.2f}")
            else:
                print(f"  {report.get('read_error')}")
    return 1 if failed else 0


def command_controls(config, args) -> int:
    profile = config.profile(args.profile)
    reports = []
    failed = False
    for camera in config.devices(args.target):
        command = show_command(camera.device) if args.operation == "show" else apply_command(camera.device, profile)
        if args.dry_run:
            reports.append({"camera_id": camera.camera_id, "device": camera.device, "command": shlex.join(command)})
            continue
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        reports.append(report_payload(camera.camera_id, camera.device, result))
        failed = failed or result.returncode != 0
    if args.json:
        print_json(reports)
    else:
        for report in reports:
            print(report.get("command") or f"{report['camera_id']} {report['device']}: " + ("OK" if report["ok"] else "FAIL"))
            if args.operation == "show" and report.get("controls"):
                print(report["controls"].rstrip())
    return 1 if failed else 0


def command_preview(config, target: str, duration: float | None) -> int:
    import cv2
    started = time.monotonic()
    if target == "stereo":
        with StereoFrameSource(*config.devices(target), config) as source:
            while duration is None or time.monotonic() - started < duration:
                _, left, right, delta = source.read()
                canvas = cv2.hconcat([left.image, right.image])
                cv2.putText(canvas, f"pair delta {delta / 1e6:.2f} ms", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)
                cv2.imshow("TennisBot raw stereo", canvas)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    else:
        with FrameSource(config.camera(target), config) as source:
            while duration is None or time.monotonic() - started < duration:
                cv2.imshow(f"TennisBot raw {target}", source.read().image)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

