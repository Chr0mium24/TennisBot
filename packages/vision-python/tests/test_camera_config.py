from tennisbot_camera.config import load_camera_config
from tennisbot_camera.controls import apply_command
from tennisbot_camera.cli import preview_frame
import numpy as np


def test_camera_mapping_and_profile_are_canonical() -> None:
    config = load_camera_config()
    assert config.camera("cam1").device == "/dev/video0"
    assert config.camera("cam1").role == "left"
    assert config.camera("cam2").device == "/dev/video2"
    assert config.camera("cam2").role == "right"
    assert config.capture.pixel_format == "MJPG"
    command = apply_command("/dev/video0", config.profile("runtime"))
    assert "focus_absolute=0" in command[-1]
    assert config.profile("calibration")["focus_absolute"] == 600
    assert config.profile("calibration")["exposure_time_absolute"] == 10


def test_preview_resize_does_not_change_capture_frame() -> None:
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    resized = preview_frame(frame, width=100)
    assert resized.shape == (50, 100, 3)
    assert frame.shape == (100, 200, 3)
