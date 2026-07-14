from __future__ import annotations

import signal
import subprocess
import threading
import time
from pathlib import Path
from tkinter import BOTH, BOTTOM, DISABLED, LEFT, NORMAL, X, Button, Frame, Label, PhotoImage, StringVar, Tk

from .config import RecordingConfig
from .recording import (
    build_set_controls_command,
    build_set_format_command,
    build_single_ffmpeg_command,
    format_number,
    run_checked,
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
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-input_format",
            self.config.capture.input_format,
            "-video_size",
            self.config.capture.video_size,
            "-framerate",
            format_number(self.config.capture.fps),
            "-i",
            self.device,
            "-vf",
            f"fps={format_number(self.preview_fps)},scale={self.preview_width}:-1",
            "-f",
            "image2pipe",
            "-vcodec",
            "ppm",
            "-",
        ]
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


def read_ppm(stream) -> bytes | None:
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
