#!/usr/bin/env python3

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from camera_controls import apply_default_camera_controls, build_camera_control_commands
from process_utils import REPO_ROOT, display_command, parse_devices, process_env, require_value, shell_quote


@dataclass
class Options:
    command: str
    dry_run: bool = False
    with_manager: bool = True
    record: bool = False
    task_id: str | None = None
    single_task: bool = False
    log_root: str = "runs/vision-runtime"
    session: str | None = None
    video: bool = True
    chassis_log: bool = True
    yolo_log: bool = True
    target_log: bool = True
    event_log: bool = True
    auto_source: bool = True
    setup_files: list[str] = field(default_factory=list)
    tile: bool | None = None
    devices: str | None = None
    left_device: str | None = None
    right_device: str | None = None
    width: str | None = None
    height: str | None = None
    fps: str | None = None
    model: str | None = None
    calibration_package: str | None = None
    yolo_device: str | None = None
    allow_missing_yaw: bool = False
    fallback_yaw: str | None = None
    extra_params: list[str] = field(default_factory=list)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h"}:
        print_usage()
        return 0

    try:
        options = parse_options(argv)
        return run(options)
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_usage()
        return 2


def run(options: Options) -> int:
    vision_runtime = wrap_ros_command(build_vision_runtime_command(options), options)
    manager_command = build_manager_command(options)
    manager = None if manager_command is None else wrap_ros_command(manager_command, options)
    devices = camera_devices(options)

    if options.dry_run:
        for command in build_camera_control_commands(devices):
            print(display_command(command))
        if manager is not None:
            print(display_command(manager))
        print(display_command(vision_runtime))
        return 0

    apply_default_camera_controls(devices, REPO_ROOT)

    procs: list[subprocess.Popen[bytes]] = []
    if manager is not None:
        procs.append(spawn(manager))
    procs.append(spawn(vision_runtime))

    previous_handlers = forward_signals(procs)
    try:
        first_index, first_code = wait_for_first_exit(procs)
        for index, proc in enumerate(procs):
            if index != first_index:
                terminate(proc)
        for proc in procs:
            try:
                proc.wait()
            except KeyboardInterrupt:
                terminate(proc, signal.SIGINT)
                proc.wait()
        return first_code
    finally:
        restore_signals(previous_handlers)


def build_vision_runtime_command(options: Options) -> list[str]:
    params: list[str] = []
    add_param(params, "runtime_log_enabled", bool_value(options.record))
    add_param(params, "runtime_log_root", options.log_root)
    add_param(params, "runtime_log_video", bool_value(options.video))
    add_param(params, "runtime_log_chassis", bool_value(options.chassis_log))
    add_param(params, "runtime_log_yolo", bool_value(options.yolo_log))
    add_param(params, "runtime_log_targets", bool_value(options.target_log))
    add_param(params, "runtime_log_events", bool_value(options.event_log))
    add_param(params, "single_task_mode", bool_value(options.single_task))
    add_param(params, "single_task_shutdown_on_complete", bool_value(options.single_task))
    if options.session is not None:
        add_param(params, "runtime_log_session", options.session)
    if options.task_id is not None:
        add_param(params, "initial_task_id", options.task_id)
    if options.tile is not None:
        add_param(params, "tile", bool_value(options.tile))
    if options.left_device is not None:
        add_param(params, "left_device", options.left_device)
    if options.right_device is not None:
        add_param(params, "right_device", options.right_device)
    if options.devices is not None:
        left, right = parse_devices(options.devices)
        add_param(params, "left_device", left)
        add_param(params, "right_device", right)
    if options.width is not None:
        add_param(params, "width", options.width)
    if options.height is not None:
        add_param(params, "height", options.height)
    if options.fps is not None:
        add_param(params, "fps", options.fps)
    if options.model is not None:
        add_param(params, "model_path", options.model)
    if options.calibration_package is not None:
        add_param(params, "calibration_package", options.calibration_package)
    if options.yolo_device is not None:
        add_param(params, "yolo_device", options.yolo_device)
    add_param(params, "allow_missing_yaw", bool_value(options.allow_missing_yaw))
    if options.fallback_yaw is not None:
        add_param(params, "fallback_yaw_rad", options.fallback_yaw)
    for item in options.extra_params:
        params.extend(["-p", item])

    return [
        "ros2",
        "run",
        "tennisbot_vision_runtime",
        "vision_runtime_node",
        "--ros-args",
        *params,
    ]


def build_manager_command(options: Options) -> list[str] | None:
    if not options.with_manager:
        return None
    return ["ros2", "launch", "target_manager", "target_manager.launch.py"]


def camera_devices(options: Options) -> tuple[str, str]:
    if options.devices is not None:
        return parse_devices(options.devices)
    return options.left_device or "/dev/video0", options.right_device or "/dev/video2"


def parse_options(args: list[str]) -> Options:
    command = args[0]
    if command not in {"run", "task"}:
        raise ValueError(f"Unknown command: {command}")

    options = Options(
        command=command,
        record=command == "task",
        single_task=command == "task",
        setup_files=default_setup_files(),
    )

    index = 1
    while index < len(args):
        arg = args[index]
        if arg in {"--help", "-h"}:
            print_usage()
            raise SystemExit(0)
        if arg == "--dry-run":
            options.dry_run = True
        elif arg == "--with-manager":
            options.with_manager = True
        elif arg == "--no-manager":
            options.with_manager = False
        elif arg == "--record":
            options.record = True
        elif arg == "--no-record":
            options.record = False
        elif arg == "--single-task":
            options.single_task = True
        elif arg == "--continuous":
            options.single_task = False
        elif arg == "--tile":
            options.tile = True
        elif arg == "--no-tile":
            options.tile = False
        elif arg == "--no-video":
            options.video = False
        elif arg == "--no-chassis-log":
            options.chassis_log = False
        elif arg == "--no-yolo-log":
            options.yolo_log = False
        elif arg == "--no-target-log":
            options.target_log = False
        elif arg == "--no-event-log":
            options.event_log = False
        elif arg == "--auto-source":
            options.auto_source = True
        elif arg == "--no-auto-source":
            options.auto_source = False
        elif arg == "--clear-setup-files":
            options.setup_files = []
        elif arg == "--setup-file":
            index += 1
            options.setup_files.append(require_value(args, index, arg))
        elif arg == "--task-id":
            index += 1
            options.task_id = require_value(args, index, arg)
        elif arg == "--log-root":
            index += 1
            options.log_root = require_value(args, index, arg)
        elif arg == "--session":
            index += 1
            options.session = require_value(args, index, arg)
        elif arg == "--devices":
            index += 1
            options.devices = require_value(args, index, arg)
        elif arg == "--left-device":
            index += 1
            options.left_device = require_value(args, index, arg)
        elif arg == "--right-device":
            index += 1
            options.right_device = require_value(args, index, arg)
        elif arg == "--width":
            index += 1
            options.width = require_value(args, index, arg)
        elif arg == "--height":
            index += 1
            options.height = require_value(args, index, arg)
        elif arg == "--fps":
            index += 1
            options.fps = require_value(args, index, arg)
        elif arg == "--model":
            index += 1
            options.model = require_value(args, index, arg)
        elif arg == "--calibration-package":
            index += 1
            options.calibration_package = require_value(args, index, arg)
        elif arg == "--yolo-device":
            index += 1
            options.yolo_device = require_value(args, index, arg)
        elif arg == "--allow-missing-yaw":
            options.allow_missing_yaw = True
        elif arg == "--no-allow-missing-yaw":
            options.allow_missing_yaw = False
        elif arg == "--fallback-yaw":
            index += 1
            options.fallback_yaw = require_value(args, index, arg)
        elif arg == "--param":
            index += 1
            options.extra_params.append(require_value(args, index, arg))
        else:
            raise ValueError(f"Unknown option: {arg}")
        index += 1

    if options.command == "task" and options.task_id is None:
        raise ValueError("task command requires --task-id")
    return options


def default_setup_files() -> list[str]:
    return [
        os.environ.get("ROS_SETUP", "/opt/ros/humble/setup.bash"),
        os.environ.get(
            "TENNISBOT_CONTROL_SETUP",
            str(Path.home() / "tennis_robot_ws/install/setup.bash"),
        ),
        os.environ.get("TENNISBOT_LOCAL_SETUP", str(REPO_ROOT / "install/setup.bash")),
    ]


def wrap_ros_command(command: list[str], options: Options) -> list[str]:
    if not options.auto_source:
        return command
    source_prefix = "".join(
        f"source {shell_quote(item)} && "
        for item in options.setup_files
        if item.strip()
    )
    return ["bash", "-lc", f"{source_prefix}exec {' '.join(shell_quote(item) for item in command)}"]


def add_param(params: list[str], name: str, value: str) -> None:
    params.extend(["-p", f"{name}:={value}"])


def bool_value(value: bool) -> str:
    return "true" if value else "false"


def spawn(command: list[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen(command, cwd=REPO_ROOT, env=process_env())


def forward_signals(procs: list[subprocess.Popen[bytes]]) -> dict[int, object]:
    previous_handlers: dict[int, object] = {}

    def handler(signum: int, _frame: object) -> None:
        for proc in procs:
            terminate(proc, signal.Signals(signum))

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, handler)
    return previous_handlers


def restore_signals(previous_handlers: dict[int, object]) -> None:
    for signum, handler in previous_handlers.items():
        signal.signal(signum, handler)


def wait_for_first_exit(procs: list[subprocess.Popen[bytes]]) -> tuple[int, int]:
    while True:
        for index, proc in enumerate(procs):
            code = proc.poll()
            if code is not None:
                return index, code
        time.sleep(0.1)


def terminate(proc: subprocess.Popen[bytes], signum: signal.Signals = signal.SIGTERM) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signum)
    except ProcessLookupError:
        return
    timer = threading.Timer(2.0, _kill_process, args=(proc,))
    timer.daemon = True
    timer.start()


def _kill_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/vision-runtime.py run [options]
  uv run scripts/vision-runtime.py task --task-id <id> [options]

主链路入口:
  run   启动 vision runtime，可选启动外部 target_manager，可选记录运行日志
  task  用指定 task_id 启动单次任务，默认开启日志，任务结束后 vision runtime 节点退出

常用命令:
  uv run scripts/vision-runtime.py run
  uv run scripts/vision-runtime.py run --record --session test01 --tile
  uv run scripts/vision-runtime.py task --task-id 42 --session catch42 --tile
  uv run scripts/vision-runtime.py task --task-id 42 --no-video
  uv run scripts/vision-runtime.py run --dry-run --record --devices /dev/video0,/dev/video2
  uv run scripts/vision-runtime.py run --allow-missing-yaw --fallback-yaw 0.0

选项:
  --record / --no-record              开关 runs/vision-runtime 日志
  --log-root <path>                   日志根目录，默认 runs/vision-runtime
  --session <name>                    日志会话名，默认自动时间戳
  --no-video                          不写 left.mp4/right.mp4
  --no-chassis-log                    不写 chassis.ndjson
  --no-yolo-log                       不写 frames/detections/observations
  --no-target-log                     不写 targets.ndjson
  --task-id <id>                      初始或单次任务 task_id
  --single-task / --continuous        单任务或连续任务模式
  --with-manager / --no-manager       是否同时启动外部 target_manager，默认启动
  --auto-source / --no-auto-source    是否自动 source ROS/control/local setup，默认开启
  --setup-file <path>                 追加一个 setup.bash，可重复
  --clear-setup-files                 清空默认 setup 列表，配合 --setup-file 使用
  --tile / --no-tile                  覆盖 YOLO tiled 推理
  --devices <left,right>              覆盖双目设备
  --allow-missing-yaw / --no-allow-missing-yaw  容忍缺失底盘 yaw，用 fallback_yaw_rad 替代
  --fallback-yaw <rad>                 缺失 yaw 时的回退弧度，默认 0.0
  --param <name:=value>               透传 ROS 参数，可重复

说明:
  启动相机前会对左右设备应用固定 V4L2 控制：手动曝光、白平衡、增益、锐度等。
  运行阶段默认自动 source ROS、控制工作区和本仓库 install；构建阶段仍需 source 后 colcon build。
  默认 setup 可用 ROS_SETUP、TENNISBOT_CONTROL_SETUP、TENNISBOT_LOCAL_SETUP 环境变量覆盖。
  日志目录包含 session.json、left.mp4、right.mp4、frames.ndjson、chassis.ndjson、
  detections.ndjson、observations.ndjson、targets.ndjson 和 events.ndjson。
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
