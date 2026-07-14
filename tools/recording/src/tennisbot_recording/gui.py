from __future__ import annotations

import signal
import subprocess
import threading
import time
from pathlib import Path
from tkinter import BOTH, BOTTOM, DISABLED, LEFT, NORMAL, X, Button, Frame, Label, PhotoImage, StringVar, Tk
from typing import BinaryIO, TextIO

from .config import RecordingConfig
from .recording import (
    build_dual_plan,
    build_set_controls_command,
    build_set_format_command,
    build_single_ffmpeg_command,
    DualRecordingPlan,
    format_number,
    run_checked,
    terminate_processes,
    write_dual_session,
    write_single_metadata,
    SingleRecordingPlan,
)


class TennisRecorderGui:
    def __init__(
        self,
        *,
        config: RecordingConfig,
        device: str,
        out_root: Path,
        preview_width: int,
        preview_fps: float,
        sample_fps: float | None,
    ) -> None:
        self.config = config
        self.device = device
        self.out_root = out_root
        self.preview_width = preview_width
        self.preview_fps = preview_fps
        self.sample_fps = sample_fps

        self.root = Tk()
        self.root.title("Tennis Camera Recorder")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = StringVar(value="Starting preview...")
        self.video_label = Label(self.root, bg="black")
        self.video_label.pack(fill=BOTH, expand=True)

        controls = Frame(self.root)
        controls.pack(side=BOTTOM, fill=X)
        self.record_button = Button(controls, text="Start Recording", command=self.start_recording)
        self.record_button.pack(side=LEFT, padx=8, pady=8)
        self.stop_button = Button(controls, text="Stop Recording", state=DISABLED, command=self.stop_recording)
        self.stop_button.pack(side=LEFT, padx=8, pady=8)
        Label(controls, textvariable=self.status).pack(side=LEFT, padx=8)

        self.preview_process: subprocess.Popen[bytes] | None = None
        self.record_process: subprocess.Popen[bytes] | None = None
        self.preview_thread: threading.Thread | None = None
        self.last_image: PhotoImage | None = None
        self.closing = False
        self.recording_started_at: float | None = None
        self.current_output: Path | None = None

        self.configure_camera()
        self.start_preview()
        self.tick()

    def run(self) -> None:
        self.root.mainloop()

    def configure_camera(self) -> None:
        run_checked(build_set_format_command(self.config, self.device))
        run_checked(build_set_controls_command(self.config, self.device))

    def start_preview(self) -> None:
        if self.preview_process is not None:
            return
        command = build_preview_command(self.config, self.device, self.preview_width, self.preview_fps)
        self.preview_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.preview_thread = threading.Thread(target=self.read_preview_frames, daemon=True)
        self.preview_thread.start()
        self.status.set("Previewing")

    def stop_preview(self) -> None:
        process = self.preview_process
        self.preview_process = None
        if process is not None:
            terminate_process(process)

    def read_preview_frames(self) -> None:
        process = self.preview_process
        if process is None or process.stdout is None:
            return
        while not self.closing and self.preview_process is process:
            frame = read_ppm(process.stdout)
            if frame is None:
                break
            self.root.after(0, self.show_frame, frame)
        if not self.closing and self.preview_process is process:
            self.root.after(0, self.preview_failed)

    def show_frame(self, frame: bytes) -> None:
        if self.closing:
            return
        image = PhotoImage(data=frame, format="PPM")
        self.last_image = image
        self.video_label.configure(image=image)

    def preview_failed(self) -> None:
        if self.record_process is None:
            self.status.set("Preview stopped. Is another app using the camera?")

    def start_recording(self) -> None:
        if self.record_process is not None:
            return
        self.record_button.configure(state=DISABLED)
        self.status.set("Freezing preview and starting recording...")
        self.stop_preview()
        self.configure_camera()

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        out_dir = self.out_root / timestamp
        out_dir.mkdir(parents=True, exist_ok=True)
        output = out_dir / f"{timestamp}_{self.config.single.output_label}.mkv"
        metadata = output.with_suffix(".controls.txt")
        command = build_single_ffmpeg_command(
            self.config,
            self.device,
            output,
            duration=None,
            sample_fps=self.sample_fps,
        )
        plan = SingleRecordingPlan(
            timestamp=timestamp,
            out_dir=out_dir,
            output=output,
            metadata=metadata,
            set_format_command=build_set_format_command(self.config, self.device),
            set_controls_command=build_set_controls_command(self.config, self.device),
            record_command=command,
            controls_string=self.config.v4l2_controls_string(),
            container="mkv",
            duration=None,
            sample_fps=self.sample_fps,
        )
        write_single_metadata(plan, self.config)
        self.record_process = subprocess.Popen(command)
        self.recording_started_at = time.monotonic()
        self.current_output = output
        self.stop_button.configure(state=NORMAL)
        if self.sample_fps is None:
            self.status.set(f"Recording: {output}")
        else:
            self.status.set(f"Recording {format_number(self.sample_fps)} fps: {output}")

    def stop_recording(self) -> None:
        process = self.record_process
        if process is not None:
            terminate_process(process)
        self.record_process = None
        self.recording_started_at = None
        self.stop_button.configure(state=DISABLED)
        self.record_button.configure(state=NORMAL)
        if self.current_output is not None:
            self.status.set(f"Saved: {self.current_output}")
        self.current_output = None
        self.configure_camera()
        self.start_preview()

    def tick(self) -> None:
        if self.record_process is not None and self.recording_started_at is not None and self.current_output is not None:
            elapsed = int(time.monotonic() - self.recording_started_at)
            if self.sample_fps is None:
                self.status.set(f"Recording {elapsed}s: {self.current_output}")
            else:
                self.status.set(f"Recording {elapsed}s at {format_number(self.sample_fps)} fps: {self.current_output}")
            if self.record_process.poll() is not None:
                self.stop_recording()
        self.root.after(1000, self.tick)

    def close(self) -> None:
        self.closing = True
        self.stop_preview()
        if self.record_process is not None:
            terminate_process(self.record_process)
        self.root.destroy()


class TennisDualRecorderGui:
    def __init__(
        self,
        *,
        config: RecordingConfig,
        devices: tuple[str, str],
        out_root: Path,
        preview_width: int,
        preview_fps: float,
        soft_sync: bool,
    ) -> None:
        self.config = config
        self.devices = devices
        self.out_root = out_root
        self.preview_width = preview_width
        self.preview_fps = preview_fps
        self.soft_sync = soft_sync

        self.root = Tk()
        self.root.title("Tennis Dual Camera Recorder")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status = StringVar(value="Starting stereo preview...")
        video_frame = Frame(self.root, bg="black")
        video_frame.pack(fill=BOTH, expand=True)
        self.video_labels = [Label(video_frame, bg="black"), Label(video_frame, bg="black")]
        self.video_labels[0].pack(side=LEFT, fill=BOTH, expand=True)
        self.video_labels[1].pack(side=LEFT, fill=BOTH, expand=True)

        controls = Frame(self.root)
        controls.pack(side=BOTTOM, fill=X)
        self.record_button = Button(controls, text="Start Recording", command=self.start_recording)
        self.record_button.pack(side=LEFT, padx=8, pady=8)
        self.stop_button = Button(controls, text="Stop Recording", state=DISABLED, command=self.stop_recording)
        self.stop_button.pack(side=LEFT, padx=8, pady=8)
        Label(controls, textvariable=self.status).pack(side=LEFT, padx=8)

        self.preview_processes: list[subprocess.Popen[bytes] | None] = [None, None]
        self.preview_threads: list[threading.Thread | None] = [None, None]
        self.last_images: list[PhotoImage | None] = [None, None]
        self.record_processes: list[subprocess.Popen[bytes]] = []
        self.record_logs: list[TextIO] = []
        self.current_plan: DualRecordingPlan | None = None
        self.recording_started_at: float | None = None
        self.closing = False

        self.configure_cameras()
        self.start_preview()
        self.tick()

    def run(self) -> None:
        self.root.mainloop()

    def configure_cameras(self) -> None:
        for device in self.devices:
            run_checked(build_set_format_command(self.config, device))
            run_checked(build_set_controls_command(self.config, device))

    def start_preview(self) -> None:
        if any(process is not None for process in self.preview_processes):
            return
        for index, device in enumerate(self.devices):
            command = build_preview_command(self.config, device, self.preview_width, self.preview_fps)
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.preview_processes[index] = process
            thread = threading.Thread(target=self.read_preview_frames, args=(index, process), daemon=True)
            self.preview_threads[index] = thread
            thread.start()
        self.status.set("Previewing stereo")

    def stop_preview(self) -> None:
        processes = [process for process in self.preview_processes if process is not None]
        self.preview_processes = [None, None]
        for process in processes:
            terminate_process(process)

    def read_preview_frames(self, index: int, process: subprocess.Popen[bytes]) -> None:
        if process.stdout is None:
            return
        while not self.closing and self.preview_processes[index] is process:
            frame = read_ppm(process.stdout)
            if frame is None:
                break
            self.root.after(0, self.show_frame, index, frame)
        if not self.closing and self.preview_processes[index] is process:
            self.root.after(0, self.preview_failed, index)

    def show_frame(self, index: int, frame: bytes) -> None:
        if self.closing:
            return
        image = PhotoImage(data=frame, format="PPM")
        self.last_images[index] = image
        self.video_labels[index].configure(image=image)

    def preview_failed(self, index: int) -> None:
        if not self.record_processes:
            self.status.set(f"Preview stopped for camera {index + 1}. Is another app using it?")

    def start_recording(self) -> None:
        if self.record_processes:
            return
        self.record_button.configure(state=DISABLED)
        self.status.set("Freezing preview and starting stereo recording...")
        self.stop_preview()
        self.configure_cameras()

        plan = build_dual_plan(
            self.config,
            devices=self.devices,
            out_root=self.out_root,
            preview=False,
            soft_sync=self.soft_sync,
            duration=None,
        )
        plan.out_dir.mkdir(parents=True, exist_ok=True)
        write_dual_session(plan, self.config, devices=self.devices, preview=False, parallel_capture=True)
        self.record_logs = []
        self.record_processes = []
        for command, log_file in zip(plan.record_commands, plan.log_files, strict=True):
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log = log_file.open("w", encoding="utf-8")
            self.record_logs.append(log)
            self.record_processes.append(
                subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            )
        self.current_plan = plan
        self.recording_started_at = time.monotonic()
        self.stop_button.configure(state=NORMAL)
        self.status.set(f"Recording stereo: {plan.out_dir}")

    def stop_recording(self) -> None:
        if self.record_processes:
            terminate_processes(self.record_processes)
        self.close_record_logs()
        self.record_processes = []
        self.recording_started_at = None
        self.stop_button.configure(state=DISABLED)
        self.record_button.configure(state=NORMAL)
        if self.current_plan is not None:
            self.status.set(f"Saved stereo recording: {self.current_plan.out_dir}")
        self.current_plan = None
        self.configure_cameras()
        self.start_preview()

    def tick(self) -> None:
        if self.record_processes and self.recording_started_at is not None and self.current_plan is not None:
            elapsed = int(time.monotonic() - self.recording_started_at)
            self.status.set(f"Recording stereo {elapsed}s: {self.current_plan.out_dir}")
            if any(process.poll() is not None for process in self.record_processes):
                self.stop_recording()
        self.root.after(1000, self.tick)

    def close(self) -> None:
        self.closing = True
        self.stop_preview()
        if self.record_processes:
            terminate_processes(self.record_processes)
        self.close_record_logs()
        self.root.destroy()

    def close_record_logs(self) -> None:
        for log in self.record_logs:
            log.close()
        self.record_logs = []


def run_gui(
    *,
    config: RecordingConfig,
    device: str,
    out_root: Path,
    preview_width: int,
    preview_fps: float,
    sample_fps: float | None,
) -> None:
    TennisRecorderGui(
        config=config,
        device=device,
        out_root=out_root,
        preview_width=preview_width,
        preview_fps=preview_fps,
        sample_fps=sample_fps,
    ).run()


def run_dual_gui(
    *,
    config: RecordingConfig,
    devices: tuple[str, str],
    out_root: Path,
    preview_width: int,
    preview_fps: float,
    soft_sync: bool,
) -> None:
    TennisDualRecorderGui(
        config=config,
        devices=devices,
        out_root=out_root,
        preview_width=preview_width,
        preview_fps=preview_fps,
        soft_sync=soft_sync,
    ).run()


def build_preview_command(config: RecordingConfig, device: str, preview_width: int, preview_fps: float) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
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
        "-vf",
        f"fps={format_number(preview_fps)},scale={preview_width}:-1",
        "-f",
        "image2pipe",
        "-vcodec",
        "ppm",
        "-",
    ]


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


def read_ppm(stream: BinaryIO) -> bytes | None:
    magic = stream.readline()
    if not magic:
        return None
    if magic != b"P6\n":
        return None
    header = bytearray(magic)
    tokens: list[bytes] = []
    while len(tokens) < 3:
        line = stream.readline()
        if not line:
            return None
        header.extend(line)
        if line.startswith(b"#"):
            continue
        tokens.extend(line.split())
    width = int(tokens[0])
    height = int(tokens[1])
    max_value = int(tokens[2])
    if max_value != 255:
        return None
    payload_size = width * height * 3
    payload = stream.read(payload_size)
    if len(payload) != payload_size:
        return None
    return bytes(header) + payload
