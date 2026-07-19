from tennisbot_camera.config import load_camera_config
from tennisbot_camera.controls import apply_command


def test_camera_mapping_and_profile_are_canonical() -> None:
    config = load_camera_config()
    assert config.camera("cam1").device == "/dev/video0"
    assert config.camera("cam1").role == "left"
    assert config.camera("cam2").device == "/dev/video2"
    assert config.camera("cam2").role == "right"
    assert config.capture.pixel_format == "MJPG"
    command = apply_command("/dev/video0", config.profile("runtime"))
    assert "focus_absolute=0" in command[-1]

