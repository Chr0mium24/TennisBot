# RK3576 Buildroot Debug Image Plan

Date: 2026-07-15

## Goal

Build a development-stage RK3576 image for the active runtime chain:

```text
stereo cameras
  -> capture frames
  -> NPU model inference
  -> left/right point extraction
  -> stereo triangulation
  -> field-frame trajectory prediction
  -> ROS target communication
```

The image is not yet a final production image. It should keep enough debug
interfaces to verify camera, NPU, geometry, prediction, and ROS communication
on real hardware.

## Buildroot Structure

Use a Buildroot external tree instead of modifying upstream Buildroot directly:

```text
br2-external-tennisbot/
  configs/rk3576_tennisbot_dev_defconfig
  board/rk3576-tennisbot/
    rootfs-overlay/
    post-build.sh
    post-image.sh
  package/
    tennisbot-runtime/
    rknn-runtime/
```

The Buildroot manual recommends root filesystem overlays and post-build scripts
for target filesystem customization, which fits this project better than
patching Buildroot core files.

References:

- https://buildroot.org/downloads/manual/manual.html

## Development Image Contents

### Keep In The Development Image

Base system:

- Linux kernel with RK3576 board support.
- Device tree configured for USB/MIPI cameras and RKNPU.
- RKNPU kernel driver.
- BusyBox shell tools.
- SSH server for remote development.
- Persistent writable partition or mount point, for example `/data`.

Camera:

- V4L2 support.
- UVC or sensor-specific camera drivers.
- `v4l-utils` for `v4l2-ctl`.
- Optional `ffmpeg` for capture verification and short debug clips.
- Optional `media-ctl` if the camera path uses Media Controller pipelines.

NPU:

- `librknnrt.so`.
- RKNN runtime support files required by the selected board vendor image.
- `rknn_server` if the selected RKNN runtime version requires it.
- A small RKNN smoke-test command or example binary.
- Project model artifact as `.rknn`, not only `.pt`.

Python and math:

- Python runtime matching the chosen ROS 2 build.
- `numpy`.
- OpenCV Python binding or project C++/Python binding using vendor OpenCV.
- `pyyaml` only if runtime config parsing or debug scripts require it.

ROS:

- ROS 2 runtime libraries needed by:
  - `rclpy`
  - `builtin_interfaces`
  - `launch`
  - `launch_ros`
  - `ament_index_python`
  - external `target_msgs`
  - external `target_manager`
- ROS CLI tools in the development image, especially `ros2 topic`,
  `ros2 node`, `ros2 param`, and `ros2 service`.

Project files:

- `tennisbot_vision_runtime`.
- Required geometry, matching, calibration loading, and prediction code from
  `tools/stereo` and `src/tennisbot_vision_runtime`.
- Stereo calibration package.
- RKNN model package.
- Launch/config files.

Debug tools:

- `strace`.
- `gdbserver` if native crashes are expected.
- `tcpdump` or a smaller packet capture option if network/ROS discovery needs
  debugging.
- `i2c-tools` only if the cameras or sensors need I2C-level bring-up.
- `usbutils` only if USB camera enumeration needs debugging.

### Do Not Put In The Minimum NPU Runtime

These are useful on the host or in a large debug image, but should not be in the
small NPU runtime image:

- `ultralytics`.
- `torch`.
- `torchvision`.
- `onnxruntime`.
- `fastapi`.
- `uvicorn`.
- YOLO annotation frontend.
- calibration GUI frontend.
- Bun/TypeScript tooling.

`onnxruntime` is not the RK3576 NPU runtime. ONNX should be an intermediate
conversion format:

```text
model.pt -> model.onnx -> model.rknn
```

The board should run `model.rknn` through RKNN runtime.

## Runtime Code Gap

Current code path:

```text
YoloBallDetector -> ultralytics.YOLO(model.pt)
```

Required RK3576 path:

```text
RknnBallDetector -> RKNN runtime(model.rknn)
```

The adapter should preserve the existing detector contract:

```python
detect_pair(left_frame, right_frame) -> (left_detections, right_detections)
```

Where each detection still has:

- `x1`
- `y1`
- `x2`
- `y2`
- center `x/y`
- `confidence`
- `class_id`

That keeps stereo matching, triangulation, trajectory prediction, and ROS
publishing unchanged while swapping only the inference backend.

## Debug Interfaces

### ROS Topics

Keep the existing production topics:

- `/robot/chassis_position`
- `/target/raw`
- `/target/managed`

Add or keep development-only debug topics:

- `/vision/debug/frame_meta`
  - frame id
  - capture timestamp
  - frame size
  - camera device names
  - dropped-frame reason
- `/vision/debug/detections`
  - left/right bounding boxes
  - confidence
  - NPU inference time
  - preprocessing and postprocessing time
- `/vision/debug/stereo_match`
  - selected left/right boxes
  - disparity
  - epipolar error
  - reprojection error
  - camera-frame 3D point
- `/vision/debug/observation`
  - field-frame point after chassis pose and camera extrinsics
- `/vision/debug/runtime_status`
  - camera opened
  - model loaded
  - recent pose available
  - publish rate
  - last error

Use normal ROS tools first. Do not add a web server unless ROS topic debugging
is not enough.

### ROS Services

Useful development services:

- `/vision/debug/capture_once`
  - saves one left/right frame pair and metadata under `/data/tennisbot/debug`.
- `/vision/debug/dump_ring_buffer`
  - saves the last N frame pairs, detections, stereo matches, and targets.
- `/vision/debug/set_recording`
  - enables or disables NDJSON and optional image dumps at runtime.
- `/vision/debug/reload_config`
  - reloads non-dangerous thresholds and debug settings.

Avoid runtime model hot-swap until the RKNN adapter is stable. Model reloads can
hide startup and memory bugs.

### Filesystem Logs

Use a bounded log root:

```text
/data/tennisbot/logs/
/data/tennisbot/debug/
/data/tennisbot/config/
```

Recommended log files:

- `session.json`
- `frames.ndjson`
- `detections.ndjson`
- `matches.ndjson`
- `observations.ndjson`
- `targets.ndjson`
- `events.ndjson`

Add log rotation or a session count limit early. Development logs can fill
small embedded storage quickly.

### Snapshot Artifacts

For debugging without GUI, save small artifacts on demand:

- raw left/right frame as JPEG or PNG;
- detection overlay image;
- stereo match overlay image;
- JSON metadata with timings and selected match;
- optional short MJPEG/H.264 clip if `ffmpeg` is present.

This is more useful on Buildroot than OpenCV GUI windows.

## Bring-up Sequence

1. Boot minimal RK3576 Buildroot image with SSH and persistent `/data`.
2. Verify cameras:
   - enumerate `/dev/video*`;
   - run `v4l2-ctl --list-devices`;
   - set exposure and format;
   - capture one frame pair.
3. Verify RKNPU:
   - load `librknnrt.so`;
   - run a vendor RKNN sample;
   - run project `model.rknn` on one saved image.
4. Verify Python/OpenCV:
   - import `cv2` and `numpy`;
   - open both cameras with the target resolution and FOURCC;
   - save frame metadata.
5. Verify ROS:
   - start `target_manager`;
   - echo `/robot/chassis_position`;
   - publish a synthetic `RawTarget` only as an interface smoke test.
6. Verify vision runtime in stages:
   - camera open only;
   - camera plus RKNN detections;
   - detections plus stereo match;
   - stereo point plus field transform;
   - prediction plus `/target/raw`.
7. Verify target manager:
   - inspect `/target/raw`;
   - inspect `/target/managed`;
   - compare timestamps and remaining time.

## Production Slimming Later

After board validation, split the configuration:

- `rk3576_tennisbot_dev_defconfig`
  - SSH
  - ROS CLI
  - `v4l-utils`
  - debug dump services
  - optional `ffmpeg`, `strace`, `gdbserver`
- `rk3576_tennisbot_runtime_defconfig`
  - runtime app
  - RKNN runtime
  - ROS runtime libraries
  - camera drivers
  - no GUI, no Torch, no Ultralytics, no ONNX Runtime, no web tools

Do not remove `v4l-utils` until camera format and controls are set by another
reliable mechanism.

## Current Recommendation

For the current development phase, build the first image as a debug image, not
as the smallest possible image. The minimum useful development set is:

```text
kernel + dtb + camera drivers + RKNPU driver
Buildroot rootfs + SSH + /data
ROS 2 runtime + ROS CLI
Python + numpy + OpenCV binding
v4l-utils
RKNN runtime + model.rknn
tennisbot runtime package + target_msgs + target_manager
NDJSON logs + ROS debug topics + capture_once service
```

The important code task before this image is fully useful is the RKNN detector
adapter. Without that adapter, the image either needs the heavy
Ultralytics/Torch path or cannot run the real model inference chain.
