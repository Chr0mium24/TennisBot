from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import select
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from typing import Sequence, TextIO

from .config import RecordingConfig, format_control_value, safe_label
from tennisbot_camera.config import load_camera_config


CONTROL_NAMES = (
    "brightness",
    "contrast",
    "saturation",
    "white_balance_automatic",
    "white_balance_temperature",
    "gamma",
    "gain",
    "power_line_frequency",
    "sharpness",
    "backlight_compensation",
    "auto_exposure",
    "exposure_time_absolute",
    "focus_automatic_continuous",
    "focus_absolute",
)


@dataclass(frozen=True)
class SingleRecordingPlan:
    timestamp: str
    out_dir: Path
    output: Path
    metadata: Path
    set_format_command: list[str]
    set_controls_command: list[str]
    record_command: list[str]
    controls_string: str
    container: str
    duration: float | None
    sample_fps: float | None


@dataclass(frozen=True)
class DualRecordingPlan:
    timestamp: str
    out_dir: Path
    outputs: tuple[Path, Path]
    log_files: tuple[Path, Path]
    set_format_commands: tuple[list[str], list[str]]
    set_controls_commands: tuple[list[str], list[str]]
    record_commands: tuple[list[str], list[str]]
    single_process_command: list[str]
    preview_command: list[str]
    ffplay_command: list[str]
    controls_string: str
    soft_sync_base_epoch: str | None
    soft_sync_base_time_utc: str | None


def build_single_plan(
    config: RecordingConfig,
    *,
    device: str,
    out_root: Path,
    container: str,
    duration: float | None,
    sample_fps: float | None,
    timestamp: str | None = None,
) -> SingleRecordingPlan:
    if container not in {"mkv", "mjpg"}:
        raise ValueError("--container must be mkv or mjpg")
    if container != "mkv" and sample_fps is not None:
        raise ValueError("--sample-fps is only supported with --container mkv")
    timestamp = timestamp or local_timestamp()
    out_dir = out_root / timestamp
    extension = "mkv" if container == "mkv" else "mjpg"
    output = out_dir / f"{timestamp}_{safe_label(config.single.output_label)}.{extension}"
    metadata = output.with_suffix(".controls.txt")
    set_format = build_set_format_command(config, device)
    set_controls = build_set_controls_command(config, device)
    if container == "mkv":
        record = build_single_ffmpeg_command(config, device, output, duration=duration, sample_fps=sample_fps)
    else:
        record = build_single_mjpg_command(config, device, output, duration=duration)
    return SingleRecordingPlan(
        timestamp=timestamp,
        out_dir=out_dir,
        output=output,
        metadata=metadata,
        set_format_command=set_format,
        set_controls_command=set_controls,
        record_command=record,
        controls_string=config.v4l2_controls_string(),
        container=container,
        duration=duration,
        sample_fps=sample_fps,
    )


def build_dual_plan(
    config: RecordingConfig,
    *,
    devices: tuple[str, str],
    out_root: Path,
    preview: bool,
    soft_sync: bool,
    duration: float | None,
    timestamp: str | None = None,
) -> DualRecordingPlan:
    timestamp = timestamp or local_timestamp()
    out_dir = unique_plan_dir(out_root / timestamp)
    labels = tuple(device_label(device) for device in devices)
    outputs = (
        out_dir / f"{timestamp}_{labels[0]}.mkv",
        out_dir / f"{timestamp}_{labels[1]}.mkv",
    )
    log_files = (outputs[0].with_suffix(".ffmpeg.log"), outputs[1].with_suffix(".ffmpeg.log"))
    set_format_commands = (
        build_set_format_command(config, devices[0]),
        build_set_format_command(config, devices[1]),
    )
    set_controls_commands = (
        build_set_controls_command(config, devices[0]),
        build_set_controls_command(config, devices[1]),
    )
    base_epoch = f"{time.time():.9f}" if soft_sync else None
    base_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if soft_sync else None
    record_commands = (
        build_dual_ffmpeg_command(config, devices[0], outputs[0], soft_sync_base_epoch=base_epoch, soft_sync_base_time_utc=base_time_utc, duration=duration),
        build_dual_ffmpeg_command(config, devices[1], outputs[1], soft_sync_base_epoch=base_epoch, soft_sync_base_time_utc=base_time_utc, duration=duration),
    )
    single_process_command = build_dual_single_process_command(
        config,
        devices,
        outputs,
        soft_sync_base_epoch=base_epoch,
        soft_sync_base_time_utc=base_time_utc,
        duration=duration,
    )
    preview_command = build_dual_preview_ffmpeg_command(
        config,
        devices,
        outputs,
        soft_sync_base_epoch=base_epoch,
        soft_sync_base_time_utc=base_time_utc,
        duration=duration,
    )
    ffplay_command = [
        "ffplay",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "nobuffer",
        "-flags",
        "low_delay",
        "-framedrop",
        "-window_title",
        "Dual camera preview - press q to stop",
        f"udp://127.0.0.1:{config.preview.port}?fifo_size=1000000&overrun_nonfatal=1",
    ]
    return DualRecordingPlan(
        timestamp=timestamp,
        out_dir=out_dir,
        outputs=outputs,
        log_files=log_files,
        set_format_commands=set_format_commands,
        set_controls_commands=set_controls_commands,
        record_commands=record_commands,
        single_process_command=single_process_command,
        preview_command=preview_command,
        ffplay_command=ffplay_command,
        controls_string=config.v4l2_controls_string(),
        soft_sync_base_epoch=base_epoch,
        soft_sync_base_time_utc=base_time_utc,
    )


def build_set_format_command(config: RecordingConfig, device: str) -> list[str]:
    return [
        "v4l2-ctl",
        "-d",
        device,
        f"--set-fmt-video=width={config.capture.width},height={config.capture.height},pixelformat={config.capture.pixel_format}",
        f"--set-parm={format_number(config.capture.fps)}",
    ]


def build_set_controls_command(config: RecordingConfig, device: str) -> list[str]:
    return ["v4l2-ctl", "-d", device, f"--set-ctrl={config.v4l2_controls_string()}"]


def build_single_ffmpeg_command(
    config: RecordingConfig,
    device: str,
    output: Path,
    *,
    duration: float | None,
    sample_fps: float | None,
) -> list[str]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-n",
        "-f",
        "v4l2",
        "-input_format",
        config.capture.input_format,
        "-video_size",
        config.capture.video_size,
        "-framerate",
        format_number(config.capture.fps),
        "-i",
        device,
    ]
    if duration is not None:
        command.extend(["-t", format_number(duration)])
    if sample_fps is None:
        command.extend(["-map", "0:v:0", "-c:v", "copy", "-an", "-f", "matroska", str(output)])
    else:
        command.extend(
            [
                "-vf",
                f"fps={format_number(sample_fps)}",
                "-map",
                "0:v:0",
                "-c:v",
                "mjpeg",
                "-q:v",
                "3",
                "-an",
                "-f",
                "matroska",
                str(output),
            ]
        )
    return command


def build_single_mjpg_command(config: RecordingConfig, device: str, output: Path, *, duration: float | None) -> list[str]:
    command = ["v4l2-ctl", "-d", device, "--stream-mmap=4"]
    if duration is not None:
        command.append(f"--stream-count={int(config.capture.fps * duration)}")
    command.append(f"--stream-to={output}")
    return command


def build_dual_ffmpeg_command(
    config: RecordingConfig,
    device: str,
    output: Path,
    *,
    soft_sync_base_epoch: str | None,
    soft_sync_base_time_utc: str | None,
    duration: float | None,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-n"]
    command.extend(soft_sync_global_args(soft_sync_base_epoch))
    command.extend(
        [
            "-thread_queue_size",
            str(config.recording.thread_queue_size),
            *soft_sync_input_args(soft_sync_base_epoch),
            "-f",
            "v4l2",
            "-input_format",
            config.capture.input_format,
            "-video_size",
            config.capture.video_size,
            "-framerate",
            format_number(config.capture.fps),
            "-i",
            device,
        ]
    )
    if duration is not None:
        command.extend(["-t", format_number(duration)])
    command.extend(
        [
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            *soft_sync_output_args(soft_sync_base_epoch, soft_sync_base_time_utc),
            "-f",
            "matroska",
            str(output),
        ]
    )
    return command


def build_dual_single_process_command(
    config: RecordingConfig,
    devices: tuple[str, str],
    outputs: tuple[Path, Path],
    *,
    soft_sync_base_epoch: str | None,
    soft_sync_base_time_utc: str | None,
    duration: float | None,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-n"]
    command.extend(soft_sync_global_args(soft_sync_base_epoch))
    for device in devices:
        command.extend(
            [
                "-thread_queue_size",
                str(config.recording.thread_queue_size),
                *soft_sync_input_args(soft_sync_base_epoch),
                "-f",
                "v4l2",
                "-input_format",
                config.capture.input_format,
                "-video_size",
                config.capture.video_size,
                "-framerate",
                format_number(config.capture.fps),
                "-i",
                device,
            ]
        )
    if duration is not None:
        command.extend(["-t", format_number(duration)])
    for index, output in enumerate(outputs):
        command.extend(
            [
                "-map",
                f"{index}:v:0",
                "-c:v",
                "copy",
                "-an",
                *soft_sync_output_args(soft_sync_base_epoch, soft_sync_base_time_utc),
                "-f",
                "matroska",
                str(output),
            ]
        )
    return command


def build_dual_preview_ffmpeg_command(
    config: RecordingConfig,
    devices: tuple[str, str],
    outputs: tuple[Path, Path],
    *,
    soft_sync_base_epoch: str | None,
    soft_sync_base_time_utc: str | None,
    duration: float | None,
) -> list[str]:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-n"]
    command.extend(soft_sync_global_args(soft_sync_base_epoch))
    for device in devices:
        command.extend(
            [
                "-thread_queue_size",
                str(config.recording.thread_queue_size),
                *soft_sync_input_args(soft_sync_base_epoch),
                "-f",
                "v4l2",
                "-input_format",
                config.capture.input_format,
                "-video_size",
                config.capture.video_size,
                "-framerate",
                format_number(config.capture.fps),
                "-i",
                device,
            ]
        )
    if duration is not None:
        command.extend(["-t", format_number(duration)])
    command.extend(
        [
            "-filter_complex",
            (
                f"[0:v]fps={format_number(config.preview.fps)},scale={config.preview.width}:-2,setpts=PTS-STARTPTS[p0];"
                f"[1:v]fps={format_number(config.preview.fps)},scale={config.preview.width}:-2,setpts=PTS-STARTPTS[p1];"
                "[p0][p1]hstack=inputs=2,format=yuv420p[preview]"
            ),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            *soft_sync_output_args(soft_sync_base_epoch, soft_sync_base_time_utc),
            "-f",
            "matroska",
            str(outputs[0]),
            "-map",
            "1:v:0",
            "-c:v",
            "copy",
            "-an",
            *soft_sync_output_args(soft_sync_base_epoch, soft_sync_base_time_utc),
            "-f",
            "matroska",
            str(outputs[1]),
            "-map",
            "[preview]",
            "-an",
            "-c:v",
            "mpeg2video",
            "-q:v",
            "5",
            "-f",
            "mpegts",
            f"udp://127.0.0.1:{config.preview.port}?pkt_size=1316",
        ]
    )
    return command


def record_single(plan: SingleRecordingPlan, config: RecordingConfig, *, dry_run: bool) -> int:
    print_single_plan(plan)
    if dry_run:
        return 0
    require_command("v4l2-ctl")
    if plan.container == "mkv":
        require_command("ffmpeg")
    plan.out_dir.mkdir(parents=True, exist_ok=True)
    run_checked(plan.set_format_command)
    run_checked(plan.set_controls_command)
    if config.capture.settle_seconds > 0:
        time.sleep(config.capture.settle_seconds)
    write_single_metadata(plan, config)
    status = run_foreground(plan.record_command)
    write_packet_timing_logs(plan.out_dir, ((canonical_camera_id(plan.set_format_command[2]), plan.output),))
    print_saved_videos((plan.output,))
    return status


def record_dual(
    plan: DualRecordingPlan,
    config: RecordingConfig,
    *,
    devices: tuple[str, str],
    dry_run: bool,
    preview: bool,
    parallel_capture: bool,
) -> int:
    print_dual_plan(plan, preview=preview, parallel_capture=parallel_capture)
    if dry_run:
        return 0
    require_command("v4l2-ctl")
    require_command("ffmpeg")
    if preview:
        require_command("ffplay")
    plan.out_dir.mkdir(parents=True, exist_ok=True)
    for command in plan.set_format_commands:
        run_checked(command)
    for command in plan.set_controls_commands:
        run_checked(command)
    if config.capture.settle_seconds > 0:
        time.sleep(config.capture.settle_seconds)
    write_dual_session(plan, config, devices=devices, preview=preview, parallel_capture=parallel_capture)
    if preview:
        status = run_preview_dual(plan)
    elif parallel_capture:
        status = run_parallel_dual(plan)
    else:
        status = run_foreground(plan.single_process_command)
    write_packet_timing_logs(plan.out_dir, (("cam1", plan.outputs[0]), ("cam2", plan.outputs[1])))
    print_saved_videos(plan.outputs)
    return status


def print_saved_videos(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.is_file():
            print(f"Saved video: {path}")


def print_single_plan(plan: SingleRecordingPlan) -> None:
    print(f"Output: {plan.output}")
    print(f"Metadata: {plan.metadata}")
    print(f"Controls: {plan.controls_string}")
    print(display_command(plan.set_format_command))
    print(display_command(plan.set_controls_command))
    print(display_command(plan.record_command))


def print_dual_plan(plan: DualRecordingPlan, *, preview: bool, parallel_capture: bool) -> None:
    print("Saving full-resolution recordings:")
    print(f"  {plan.outputs[0]}")
    print(f"  {plan.outputs[1]}")
    print(f"Controls: {plan.controls_string}")
    if plan.soft_sync_base_time_utc:
        print(f"Soft sync base: {plan.soft_sync_base_time_utc} ({plan.soft_sync_base_epoch})")
    else:
        print("Soft sync disabled.")
    for command in plan.set_format_commands:
        print(display_command(command))
    for command in plan.set_controls_commands:
        print(display_command(command))
    if preview:
        print(display_command(plan.preview_command))
        print(display_command(plan.ffplay_command))
    elif parallel_capture:
        print(display_command(plan.record_commands[0]))
        print(display_command(plan.record_commands[1]))
    else:
        print(display_command(plan.single_process_command))


def write_single_metadata(plan: SingleRecordingPlan, config: RecordingConfig) -> None:
    camera_id = canonical_camera_id(plan.set_format_command[2])
    lines = [
        f"timestamp={plan.timestamp}",
        f"config={config.path}",
        f"device={plan.set_format_command[2]}",
        f"output={plan.output}",
        f"container={plan.container}",
        f"video_size={config.capture.video_size}",
        f"framerate={format_number(config.capture.fps)}",
        f"input_format={config.capture.input_format}",
        f"sample_fps={'' if plan.sample_fps is None else format_number(plan.sample_fps)}",
        f"duration={'' if plan.duration is None else format_number(plan.duration)}",
        f"v4l2_ctrls={plan.controls_string}",
        "",
        "[set_format_command]",
        display_command(plan.set_format_command),
        "",
        "[set_controls_command]",
        display_command(plan.set_controls_command),
        "",
        "[record_command]",
        display_command(plan.record_command),
        "",
        "[current_format]",
        run_text(["v4l2-ctl", "-d", plan.set_format_command[2], "--get-fmt-video", "--get-parm"]),
        "",
        "[current_controls]",
        run_text(["v4l2-ctl", "-d", plan.set_format_command[2], f"--get-ctrl={','.join(CONTROL_NAMES)}"]),
        "",
        "[all_controls]",
        run_text(["v4l2-ctl", "-d", plan.set_format_command[2], "--list-ctrls-menus"]),
    ]
    plan.metadata.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {
        "schema_version": "tennisbot.recording.session.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mono",
        "camera_ids": [camera_id],
        "devices": [plan.set_format_command[2]],
        "streams": {camera_id: str(plan.output)},
        "capture": {
            "width": config.capture.width,
            "height": config.capture.height,
            "fps": config.capture.fps,
            "input_format": config.capture.input_format,
        },
        "controls": {name: format_control_value(value) for name, value in config.v4l2_controls()},
    }
    (plan.out_dir / "session.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_dual_session(
    plan: DualRecordingPlan,
    config: RecordingConfig,
    *,
    devices: tuple[str, str],
    preview: bool,
    parallel_capture: bool,
) -> None:
    payload = {
        "schema_version": "tennisbot.recording.session.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "stereo",
        "camera_ids": ["cam1", "cam2"],
        "timestamp": plan.timestamp,
        "config": str(config.path),
        "devices": list(devices),
        "outputs": [str(path) for path in plan.outputs],
        "streams": {"cam1": str(plan.outputs[0]), "cam2": str(plan.outputs[1])},
        "logs": [str(path) for path in plan.log_files],
        "capture": {
            "width": config.capture.width,
            "height": config.capture.height,
            "fps": config.capture.fps,
            "input_format": config.capture.input_format,
            "pixel_format": config.capture.pixel_format,
        },
        "recording": {
            "preview": preview,
            "parallel_capture": parallel_capture,
            "soft_sync_base_epoch": plan.soft_sync_base_epoch,
            "soft_sync_base_time_utc": plan.soft_sync_base_time_utc,
        },
        "controls": {name: format_control_value(value) for name, value in config.v4l2_controls()},
        "commands": {
            "set_format": [display_command(command) for command in plan.set_format_commands],
            "set_controls": [display_command(command) for command in plan.set_controls_commands],
            "record_parallel": [display_command(command) for command in plan.record_commands],
            "record_single_process": display_command(plan.single_process_command),
            "record_preview": display_command(plan.preview_command),
        },
        "current_controls": {
            device: run_text(["v4l2-ctl", "-d", device, f"--get-ctrl={','.join(CONTROL_NAMES)}"])
            for device in devices
        },
    }
    (plan.out_dir / "session.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def probe_video_timestamps(path: Path) -> list[float]:
    if not path.is_file():
        return []
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path),
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    try:
        frames = json.loads(result.stdout).get("frames", [])
        return [float(item["best_effort_timestamp_time"]) for item in frames if "best_effort_timestamp_time" in item]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def canonical_camera_id(device: str) -> str:
    config = load_camera_config()
    for camera_id, camera in config.cameras.items():
        if camera.device == device:
            return camera_id
    return Path(device).name


def write_timing_records(out_dir: Path, streams: Sequence[tuple[str, Path, Sequence[float]]]) -> None:
    with (out_dir / "frames.ndjson").open("w", encoding="utf-8") as frames_file:
        for camera_id, path, timestamps in streams:
            for sequence, timestamp_s in enumerate(timestamps):
                frames_file.write(json.dumps({
                    "camera_id": camera_id,
                    "sequence": sequence,
                    "timestamp_s": timestamp_s,
                    "video": str(path),
                }, sort_keys=True) + "\n")
    if len(streams) != 2:
        return
    left, right = streams
    with (out_dir / "pairs.ndjson").open("w", encoding="utf-8") as pairs_file:
        for pair_id, (left_s, right_s) in enumerate(zip(left[2], right[2], strict=False)):
            pairs_file.write(json.dumps({
                "pair_id": pair_id,
                "left_sequence": pair_id,
                "right_sequence": pair_id,
                "delta_ms": (right_s - left_s) * 1000.0,
                "within_threshold": abs(right_s - left_s) <= 0.010,
            }, sort_keys=True) + "\n")


def write_packet_timing_logs(out_dir: Path, streams: Sequence[tuple[str, Path]]) -> None:
    records = [(camera_id, path, probe_video_timestamps(path)) for camera_id, path in streams]
    write_timing_records(out_dir, records)


def run_parallel_dual(plan: DualRecordingPlan) -> int:
    with tempfile.TemporaryDirectory(prefix="tennisbot-recording-") as tmp:
        fifo_a = Path(tmp) / "start-a"
        fifo_b = Path(tmp) / "start-b"
        os.mkfifo(fifo_a)
        os.mkfifo(fifo_b)
        processes: list[subprocess.Popen[bytes]] = []
        logs: list[TextIO] = []
        try:
            for command, fifo, log_file in zip(plan.record_commands, (fifo_a, fifo_b), plan.log_files, strict=True):
                log_file.parent.mkdir(parents=True, exist_ok=True)
                log = log_file.open("wb")
                logs.append(log)
                processes.append(start_after_fifo(command, fifo, log))
            release_fifo(fifo_a)
            release_fifo(fifo_b)
            print("Preview disabled. Press q then Enter or Ctrl+C to stop.")
            return monitor_processes(processes)
        finally:
            terminate_processes(processes)
            for log in logs:
                log.close()


def run_preview_dual(plan: DualRecordingPlan) -> int:
    ffmpeg_process = subprocess.Popen(plan.preview_command)
    time.sleep(1)
    if ffmpeg_process.poll() is not None:
        return int(ffmpeg_process.returncode or 1)
    try:
        ffplay_status = run_foreground(plan.ffplay_command)
    finally:
        terminate_process(ffmpeg_process)
    return ffplay_status


def start_after_fifo(command: list[str], fifo: Path, log: TextIO) -> subprocess.Popen[bytes]:
    shell_command = ["bash", "-c", 'read -r _ < "$1"; shift; exec "$@"', "tennisbot-recording-start", str(fifo), *command]
    return subprocess.Popen(shell_command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)


def release_fifo(fifo: Path) -> None:
    with fifo.open("w", encoding="utf-8") as stream:
        stream.write("go\n")


def monitor_processes(processes: Sequence[subprocess.Popen[bytes]]) -> int:
    try:
        while any(process.poll() is None for process in processes):
            readable, _, _ = select.select([sys.stdin], [], [], 0.5)
            if readable:
                line = sys.stdin.readline()
                if line.strip().lower() == "q":
                    terminate_processes(processes)
                    break
            for process in processes:
                if process.poll() not in (None, 0):
                    terminate_processes(processes)
                    break
    except KeyboardInterrupt:
        terminate_processes(processes)
    statuses = [process.wait() for process in processes]
    nonzero = [status for status in statuses if status not in (0, -signal.SIGINT)]
    return int(nonzero[0]) if nonzero else 0


def run_foreground(command: Sequence[str]) -> int:
    process = subprocess.Popen(list(command))
    try:
        return int(process.wait())
    except KeyboardInterrupt:
        terminate_process(process)
        return int(process.returncode or 130)


def terminate_processes(processes: Sequence[subprocess.Popen[bytes]]) -> None:
    active = [process for process in processes if process.poll() is None]
    if not active:
        return
    for process in active:
        process.send_signal(signal.SIGINT)
    remaining = wait_for_processes(active, timeout=5)
    for process in remaining:
        process.terminate()
    remaining = wait_for_processes(remaining, timeout=2)
    for process in remaining:
        process.kill()
    wait_for_processes(remaining, timeout=2)


def wait_for_processes(
    processes: Sequence[subprocess.Popen[bytes]],
    *,
    timeout: float,
) -> list[subprocess.Popen[bytes]]:
    deadline = time.monotonic() + timeout
    for process in processes:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass
    return [process for process in processes if process.poll() is None]


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_checked(command: Sequence[str]) -> None:
    subprocess.run(list(command), check=True)


def run_text(command: Sequence[str]) -> str:
    result = subprocess.run(list(command), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return result.stdout.rstrip()


def require_command(name: str) -> None:
    if subprocess.run(["sh", "-c", f"command -v {shlex.quote(name)} >/dev/null 2>&1"]).returncode != 0:
        raise FileNotFoundError(f"Missing command: {name}")


def soft_sync_global_args(base_epoch: str | None) -> list[str]:
    return ["-copyts"] if base_epoch is not None else []


def soft_sync_input_args(base_epoch: str | None) -> list[str]:
    return ["-timestamps", "abs"] if base_epoch is not None else []


def soft_sync_output_args(base_epoch: str | None, base_time_utc: str | None) -> list[str]:
    if base_epoch is None:
        return []
    args = [
        "-output_ts_offset",
        f"-{base_epoch}",
        "-metadata",
        f"soft_sync_base_epoch={base_epoch}",
    ]
    if base_time_utc is not None:
        args.extend(["-metadata", f"soft_sync_base_time_utc={base_time_utc}"])
    return args


def display_command(command: Sequence[str]) -> str:
    return shlex.join(str(part) for part in command)


def format_number(value: float | int) -> str:
    parsed = float(value)
    if parsed.is_integer():
        return str(int(parsed))
    return str(value)


def local_timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def unique_plan_dir(base: Path) -> Path:
    if not base.exists():
        return base
    suffix = 1
    while True:
        candidate = Path(f"{base}_{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def device_label(device: str) -> str:
    return safe_label(Path(device).name or device)
