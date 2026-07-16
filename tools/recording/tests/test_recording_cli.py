from __future__ import annotations

import signal
import subprocess
from pathlib import Path

from tennisbot_recording.cli import main
from tennisbot_recording.config import DEFAULT_CONFIG_PATH, load_config
from tennisbot_recording.gui import start_noninteractive_process
from tennisbot_recording.recording import (
    build_dual_plan,
    build_single_plan,
    display_command,
    print_saved_videos,
    terminate_processes,
)


def test_default_config_loads_record_script_camera_controls() -> None:
    config = load_config(DEFAULT_CONFIG_PATH)

    assert config.capture.video_size == "3840x2160"
    assert config.capture.fps == 30
    assert config.single.device == "/dev/video0"
    assert config.dual.devices == ("/dev/video2", "/dev/video0")
    assert "exposure_time_absolute=10" in config.v4l2_controls_string()
    assert "white_balance_temperature=4600" in config.v4l2_controls_string()
    assert "brightness=-5" in config.v4l2_controls_string()


def test_single_plan_uses_config_controls_and_sample_fps(tmp_path: Path) -> None:
    config = load_config(DEFAULT_CONFIG_PATH)
    plan = build_single_plan(
        config,
        device="/dev/video8",
        out_root=tmp_path,
        container="mkv",
        duration=60,
        sample_fps=3,
        timestamp="20260714_120000",
    )

    command = display_command(plan.record_command)
    assert plan.output == tmp_path / "20260714_120000" / "20260714_120000_video0.mkv"
    assert "--set-ctrl=auto_exposure=1,exposure_time_absolute=10" in display_command(plan.set_controls_command)
    assert "-vf fps=3" in command
    assert "-t 60" in command
    assert "/dev/video8" in command


def test_dual_plan_builds_soft_sync_parallel_commands(tmp_path: Path) -> None:
    config = load_config(DEFAULT_CONFIG_PATH)
    plan = build_dual_plan(
        config,
        devices=("/dev/video2", "/dev/video0"),
        out_root=tmp_path,
        preview=False,
        soft_sync=True,
        duration=10,
        timestamp="20260714_120001",
    )

    first = display_command(plan.record_commands[0])
    second = display_command(plan.record_commands[1])
    assert plan.outputs[0].name == "20260714_120001_video2.mkv"
    assert plan.outputs[1].name == "20260714_120001_video0.mkv"
    assert "-copyts" in first
    assert "-timestamps abs" in first
    assert "soft_sync_base_epoch=" in first
    assert "/dev/video2" in first
    assert "/dev/video0" in second


def test_print_saved_videos_reports_only_existing_outputs(tmp_path: Path, capsys) -> None:
    saved = tmp_path / "camera-a.mkv"
    missing = tmp_path / "camera-b.mkv"
    saved.write_bytes(b"video")

    print_saved_videos((saved, missing))

    output = capsys.readouterr().out
    assert f"Saved video: {saved}" in output
    assert str(missing) not in output


def test_terminate_processes_signals_all_captures_before_waiting() -> None:
    events: list[str] = []

    class FakeProcess:
        def __init__(self, name: str) -> None:
            self.name = name
            self.done = False

        def poll(self):
            return 0 if self.done else None

        def send_signal(self, sent_signal):
            events.append(f"signal:{self.name}:{sent_signal}")

        def wait(self, timeout=None):
            events.append(f"wait:{self.name}")
            self.done = True
            return 0

    terminate_processes([FakeProcess("left"), FakeProcess("right")])

    assert events[:2] == [f"signal:left:{signal.SIGINT}", f"signal:right:{signal.SIGINT}"]
    assert events[2:] == ["wait:left", "wait:right"]


def test_record_single_dry_run_accepts_negative_brightness_override(capsys) -> None:
    code = main(["record", "single", "--dry-run", "--duration", "1", "--brightness", "-5", "--exposure", "123"])

    output = capsys.readouterr().out
    assert code == 0
    assert "Controls:" in output
    assert "brightness=-5" in output
    assert "exposure_time_absolute=123" in output
    assert "ffmpeg" in output


def test_gui_single_dry_run_uses_config(capsys) -> None:
    code = main(["gui", "single", "--dry-run", "--sample-fps", "3"])

    output = capsys.readouterr().out
    assert code == 0
    assert "recording_gui=dry-run" in output
    assert "device=/dev/video0" in output
    assert "sample_fps=3" in output


def test_gui_dual_dry_run_uses_config_and_overrides(capsys) -> None:
    code = main(["gui", "dual", "--dry-run", "--devices", "/dev/video4,/dev/video6", "--no-soft-sync"])

    output = capsys.readouterr().out
    assert code == 0
    assert "recording_dual_gui=dry-run" in output
    assert "devices=/dev/video4,/dev/video6" in output
    assert "preview=960px@10fps per_camera" in output
    assert "soft_sync=False" in output
    assert "exposure_time_absolute=10" in output


def test_gui_process_does_not_inherit_terminal_stdin(monkeypatch) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr("tennisbot_recording.gui.subprocess.Popen", fake_popen)

    process = start_noninteractive_process(["ffmpeg", "-version"], stdout=-1)

    assert process is sentinel
    assert captured["command"] == ["ffmpeg", "-version"]
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["stdout"] == -1


def test_extract_yolo_frames_dry_run_maps_video_labels(tmp_path: Path, capsys) -> None:
    session = tmp_path / "20260701_205507"
    session.mkdir()
    (session / "20260701_205507_video0.mkv").write_bytes(b"")
    (session / "20260701_205507_video2.mkv").write_bytes(b"")

    code = main(["extract-yolo-frames", "--dry-run", "--dataset-root", str(tmp_path / "dataset"), str(session)])

    output = capsys.readouterr().out
    assert code == 0
    assert "20260701_205507_cam1_frame_%06d.jpg" in output
    assert "20260701_205507_cam2_frame_%06d.jpg" in output
    assert "-vf fps=2" in output


def test_normalize_timestamps_dry_run_uses_base_epoch(tmp_path: Path, capsys) -> None:
    video = tmp_path / "input.mkv"
    video.write_bytes(b"")

    code = main(["normalize-timestamps", "--dry-run", "--base-epoch", "1782893181.5", str(video)])

    output = capsys.readouterr().out
    assert code == 0
    assert "-output_ts_offset -1782893181.5" in output
    assert "input_normalized.mkv" in output
