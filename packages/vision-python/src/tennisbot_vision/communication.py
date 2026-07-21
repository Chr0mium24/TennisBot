#!/usr/bin/env python3

from __future__ import annotations

import math
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .command_utils import REPO_ROOT, process_env, require_value, shell_quote


@dataclass
class Options:
    topic: str = "/robot/chassis_position"
    expected_type: str = "target_msgs/msg/ChassisPosition"
    timeout_ms: int = 5000
    hz_seconds: float = 4.0
    auto_source: bool = True
    setup_files: list[str] = field(default_factory=list)


@dataclass
class CommandResult:
    code: int | None
    stdout: str
    stderr: str
    timed_out: bool


@dataclass
class ParsedMessage:
    publish_stamp_sec: float | None = None
    publish_stamp_nanosec: float | None = None
    sequence_id: float | None = None
    x: float | None = None
    y: float | None = None
    yaw: float | None = None


@dataclass
class RawTargetPublishOptions:
    topic: str = "/target/raw"
    task_id: int = 1
    sequence_id: int = 0
    target_x: float = 0.0
    target_y: float = 0.0
    predicted_t_remain: float = 1.0
    sigma_x: float = 0.05
    sigma_y: float = 0.05
    capture_stamp_sec: int | None = None
    capture_stamp_nanosec: int | None = None
    dry_run: bool = False
    auto_source: bool = True
    setup_files: list[str] = field(default_factory=list)


def main(argv: list[str]) -> int:
    try:
        options = parse_options(argv)
        return run(options)
    except ValueError as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_usage()
        return 2


def run(options: Options) -> int:
    print(f"检查: {options.topic}")

    topic_list = run_ros_command(["topic", "list", "-t"], options.timeout_ms, options)
    if topic_list.timed_out:
        print(f"topic列表: 超时 {format_seconds(options.timeout_ms)}")
        print("结果: FAIL")
        return 1
    if topic_list.code != 0:
        print("topic列表: 失败")
        print_command_error(topic_list)
        print("结果: FAIL")
        return 1

    topic_type = parse_topic_type(topic_list.stdout, options.topic)
    if topic_type is None:
        print("topic: 不存在")
        print(f"期望类型: {options.expected_type}")
        print("结果: FAIL")
        return 1

    print("topic: 存在")
    print(f"type: {topic_type}")
    if topic_type != options.expected_type:
        print(f"期望类型: {options.expected_type}")
        print("结果: FAIL")
        return 1

    echo = run_ros_command(["topic", "echo", "--once", options.topic], options.timeout_ms, options)
    if echo.timed_out:
        print(f"消息: {format_seconds(options.timeout_ms)} 内未收到")
        print("结果: FAIL")
        return 1
    if echo.code != 0:
        print("消息: 读取失败")
        print_command_error(echo)
        print("结果: FAIL")
        return 1

    message = parse_chassis_position(echo.stdout)
    print("消息: 收到")
    print_parsed_message(message)

    errors = validate_message(message)
    if options.hz_seconds > 0:
        print_topic_hz(options)

    if errors:
        print(f"字段检查: {', '.join(errors)}")
        print("结果: FAIL")
        return 1

    print("字段检查: OK")
    print("结果: OK")
    return 0


def publish_raw_target_main(argv: list[str]) -> int:
    try:
        options = parse_raw_target_publish_options(argv)
        return publish_raw_target(options)
    except ValueError as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_raw_target_publish_usage()
        return 2


def publish_raw_target(options: RawTargetPublishOptions) -> int:
    stamp_ns = time.time_ns()
    stamp_sec = (
        options.capture_stamp_sec
        if options.capture_stamp_sec is not None
        else stamp_ns // 1_000_000_000
    )
    stamp_nanosec = (
        options.capture_stamp_nanosec
        if options.capture_stamp_nanosec is not None
        else stamp_ns % 1_000_000_000
    )
    remain_ns = round(options.predicted_t_remain * 1_000_000_000)
    remain_sec, remain_nanosec = divmod(remain_ns, 1_000_000_000)
    payload = (
        "{capture_stamp: {sec: "
        f"{stamp_sec}, nanosec: {stamp_nanosec}"
        "}, task_id: "
        f"{options.task_id}, sequence_id: {options.sequence_id}, "
        f"target_x: {options.target_x}, target_y: {options.target_y}, "
        "predicted_t_remain: {sec: "
        f"{remain_sec}, nanosec: {remain_nanosec}"
        f"}}, sigma_x: {options.sigma_x}, sigma_y: {options.sigma_y}"
        "}"
    )
    command = ["topic", "pub", "--once", options.topic, "target_msgs/msg/RawTarget", payload]

    print("模式: 发布人工 RawTarget（不属于真实 ROS/Gazebo 闭环验证）")
    print(f"topic: {options.topic}")
    print(f"id: task={options.task_id}, sequence={options.sequence_id}")
    print(f"target: x={options.target_x}, y={options.target_y}")
    print(f"capture_stamp: {stamp_sec}.{stamp_nanosec:09d}")
    print(f"predicted_t_remain: {options.predicted_t_remain}s")
    if options.dry_run:
        wrapped = wrap_ros_command(["ros2", *command], options)
        print("command: " + " ".join(shell_quote(item) for item in wrapped))
        return 0

    result = run_ros_command(command, 10000, options)
    if result.timed_out:
        print("发布: 10s 内未完成")
        print("结果: FAIL")
        return 1
    if result.code != 0:
        print("发布: 失败")
        print_command_error(result)
        print("结果: FAIL")
        return 1
    print("发布: 完成")
    print("结果: OK")
    return 0


def print_topic_hz(options: Options) -> None:
    timeout_ms = max(1000, round(options.hz_seconds * 1000))
    hz = run_ros_command(["topic", "hz", options.topic], timeout_ms, options, signal.SIGINT)
    average = parse_last_number(hz.stdout, r"average rate:\s*([0-9.]+)")
    window = parse_last_number(hz.stdout, r"window:\s*([0-9]+)")
    if average is None:
        print(f"频率: 未测到 ({format_seconds(timeout_ms)} 采样)")
        return
    suffix = "" if window is None else f", window {round(window)}"
    print(f"频率: {average:.3f} Hz ({format_seconds(timeout_ms)} 采样{suffix})")


def parse_options(args: list[str]) -> Options:
    options = Options(setup_files=default_setup_files())
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--help", "-h"}:
            print_usage()
            raise SystemExit(0)
        if arg == "--topic":
            index += 1
            options.topic = require_value(args, index, arg)
        elif arg == "--expected-type":
            index += 1
            options.expected_type = require_value(args, index, arg)
        elif arg == "--timeout":
            index += 1
            options.timeout_ms = seconds_to_ms(require_value(args, index, arg), arg)
        elif arg == "--hz-seconds":
            index += 1
            options.hz_seconds = nonnegative_seconds(require_value(args, index, arg), arg)
        elif arg == "--no-hz":
            options.hz_seconds = 0
        elif arg == "--auto-source":
            options.auto_source = True
        elif arg == "--no-auto-source":
            options.auto_source = False
        elif arg == "--clear-setup-files":
            options.setup_files = []
        elif arg == "--setup-file":
            index += 1
            options.setup_files.append(require_value(args, index, arg))
        else:
            raise ValueError(f"Unknown option: {arg}")
        index += 1

    if not options.topic.startswith("/"):
        raise ValueError("--topic must be an absolute ROS topic name")
    return options


def parse_raw_target_publish_options(args: list[str]) -> RawTargetPublishOptions:
    options = RawTargetPublishOptions(setup_files=default_setup_files())
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--help", "-h"}:
            print_raw_target_publish_usage()
            raise SystemExit(0)
        if arg == "--topic":
            index += 1
            options.topic = require_value(args, index, arg)
        elif arg == "--task-id":
            index += 1
            options.task_id = nonnegative_integer(require_value(args, index, arg), arg)
        elif arg == "--sequence-id":
            index += 1
            options.sequence_id = nonnegative_integer(require_value(args, index, arg), arg)
        elif arg in {"--target-x", "--target-y", "--sigma-x", "--sigma-y"}:
            index += 1
            setattr(options, arg[2:].replace("-", "_"), finite_number(require_value(args, index, arg), arg))
        elif arg == "--predicted-t-remain":
            index += 1
            options.predicted_t_remain = finite_number(require_value(args, index, arg), arg)
        elif arg == "--capture-stamp-sec":
            index += 1
            options.capture_stamp_sec = nonnegative_integer(require_value(args, index, arg), arg)
        elif arg == "--capture-stamp-nanosec":
            index += 1
            options.capture_stamp_nanosec = nonnegative_integer(require_value(args, index, arg), arg)
        elif arg == "--dry-run":
            options.dry_run = True
        elif arg == "--auto-source":
            options.auto_source = True
        elif arg == "--no-auto-source":
            options.auto_source = False
        elif arg == "--clear-setup-files":
            options.setup_files = []
        elif arg == "--setup-file":
            index += 1
            options.setup_files.append(require_value(args, index, arg))
        else:
            raise ValueError(f"Unknown option: {arg}")
        index += 1

    if not options.topic.startswith("/"):
        raise ValueError("--topic must be an absolute ROS topic name")
    if options.task_id > 0xFFFFFFFFFFFFFFFF:
        raise ValueError("--task-id must fit uint64")
    if options.sequence_id > 0xFFFFFFFF:
        raise ValueError("--sequence-id must fit uint32")
    if options.capture_stamp_nanosec is not None and options.capture_stamp_nanosec >= 1_000_000_000:
        raise ValueError("--capture-stamp-nanosec must be less than 1000000000")
    if options.predicted_t_remain <= 0.0 or options.predicted_t_remain > 5.0:
        raise ValueError("--predicted-t-remain must be within (0, 5]")
    if options.sigma_x < 0.0 or options.sigma_y < 0.0:
        raise ValueError("--sigma-x and --sigma-y must be nonnegative")
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


def run_ros_command(
    args: list[str],
    timeout_ms: int,
    options: Options,
    timeout_signal: signal.Signals = signal.SIGTERM,
) -> CommandResult:
    command = wrap_ros_command(["ros2", *args], options)
    try:
        proc = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=process_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as error:
        return CommandResult(code=127, stdout="", stderr=str(error), timed_out=False)

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_ms / 1000)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.send_signal(timeout_signal)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
    return CommandResult(code=proc.returncode, stdout=stdout, stderr=stderr, timed_out=timed_out)


def wrap_ros_command(command: list[str], options: Options) -> list[str]:
    if not options.auto_source:
        return command
    source_prefix = "".join(
        f"source {shell_quote(item)} && "
        for item in options.setup_files
        if item.strip()
    )
    return ["bash", "-lc", f"{source_prefix}exec {' '.join(shell_quote(item) for item in command)}"]


def parse_topic_type(output: str, topic: str) -> str | None:
    for line in output.splitlines():
        match = re.match(r"^(.+?)\s+\[(.+)]$", line.strip())
        if match is not None and match.group(1) == topic:
            return match.group(2)
    return None


def parse_chassis_position(output: str) -> ParsedMessage:
    result = ParsedMessage()
    section = ""
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        root_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if root_match is not None:
            section = root_match.group(1)
            value = root_match.group(2).strip()
            parsed = parse_finite_number(value)
            if section == "sequence_id":
                result.sequence_id = parsed
            elif section == "x":
                result.x = parsed
            elif section == "y":
                result.y = parsed
            elif section == "yaw":
                result.yaw = parsed
            continue

        if section == "publish_stamp":
            child_match = re.match(r"^\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
            if child_match is None:
                continue
            value = parse_finite_number(child_match.group(2).strip())
            if child_match.group(1) == "sec":
                result.publish_stamp_sec = value
            elif child_match.group(1) == "nanosec":
                result.publish_stamp_nanosec = value
    return result


def print_parsed_message(message: ParsedMessage) -> None:
    print(f"publish_stamp.sec: {format_value(message.publish_stamp_sec)}")
    print(f"publish_stamp.nanosec: {format_value(message.publish_stamp_nanosec)}")
    print(f"sequence_id: {format_value(message.sequence_id)}")
    print(f"x: {format_value(message.x)}")
    print(f"y: {format_value(message.y)}")
    print(f"yaw: {format_value(message.yaw)}")


def validate_message(message: ParsedMessage) -> list[str]:
    errors: list[str] = []
    if not is_finite(message.publish_stamp_sec):
        errors.append("publish_stamp.sec 缺失或非法")
    if not is_finite(message.publish_stamp_nanosec):
        errors.append("publish_stamp.nanosec 缺失或非法")
    if not is_finite(message.sequence_id):
        errors.append("sequence_id 缺失或非法")
    if not is_finite(message.x):
        errors.append("x 缺失或非法")
    if not is_finite(message.y):
        errors.append("y 缺失或非法")
    if not is_finite(message.yaw):
        errors.append("yaw 缺失或非法")
    return errors


def parse_last_number(output: str, pattern: str) -> float | None:
    value: float | None = None
    for match in re.finditer(pattern, output):
        parsed = parse_finite_number(match.group(1))
        if parsed is not None:
            value = parsed
    return value


def parse_finite_number(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def print_command_error(result: CommandResult) -> None:
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    if stderr:
        print(f"stderr: {stderr}")
    elif stdout:
        print(f"stdout: {stdout}")


def seconds_to_ms(value: str, option: str) -> int:
    seconds = nonnegative_seconds(value, option)
    if seconds <= 0:
        raise ValueError(f"{option} must be greater than 0")
    return round(seconds * 1000)


def nonnegative_seconds(value: str, option: str) -> float:
    try:
        seconds = float(value)
    except ValueError as error:
        raise ValueError(f"{option} must be a nonnegative number of seconds") from error
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"{option} must be a nonnegative number of seconds")
    return seconds


def finite_number(value: str, option: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{option} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{option} must be a finite number")
    return number


def nonnegative_integer(value: str, option: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{option} must be a nonnegative integer") from error
    if number < 0:
        raise ValueError(f"{option} must be a nonnegative integer")
    return number


def format_seconds(timeout_ms: int) -> str:
    digits = 0 if timeout_ms % 1000 == 0 else 1
    return f"{timeout_ms / 1000:.{digits}f}s"


def format_value(value: float | None) -> str:
    return "缺失" if value is None else str(int(value) if value.is_integer() else value)


def is_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/test.py communication chassis-position [options]

说明:
  检查 /robot/chassis_position 是否存在、类型是否正确、是否能收到一条消息，并输出关键字段。
  输出是普通文本，不生成 Markdown 文件。

常用:
  uv run scripts/test.py communication chassis-position
  uv run scripts/test.py communication chassis-position --timeout 8 --hz-seconds 5
  uv run scripts/test.py communication chassis-position --no-hz

选项:
  --topic <name>             默认 /robot/chassis_position
  --expected-type <type>     默认 target_msgs/msg/ChassisPosition
  --timeout <seconds>        topic list 和 echo 的超时时间，默认 5
  --hz-seconds <seconds>     频率采样时间，默认 4
  --no-hz                    不采样频率
  --auto-source              自动 source ROS/control/local setup，默认开启
  --no-auto-source           不自动 source
  --setup-file <path>        追加 setup.bash，可重复
  --clear-setup-files        清空默认 setup 列表，配合 --setup-file 使用
"""
    )


def print_raw_target_publish_usage() -> None:
    print(
        """用法:
  uv run scripts/test.py communication publish-raw-target [options]

说明:
  向 /target/raw 单次发布 target_msgs/msg/RawTarget。
  target-x/target-y 必须使用球场/接口坐标系。本命令不属于真实 ROS/Gazebo 闭环验证。

常用:
  uv run scripts/test.py communication publish-raw-target --task-id 1 --sequence-id 0 --target-x 1.0 --target-y -0.5
  uv run scripts/test.py communication publish-raw-target --dry-run

选项:
  --topic <name>                    默认 /target/raw
  --task-id <integer>               默认 1
  --sequence-id <integer>           默认 0
  --target-x <meters>               球场坐标 x，默认 0
  --target-y <meters>               球场坐标 y，默认 0
  --predicted-t-remain <seconds>    默认 1.0，范围 (0, 5]
  --sigma-x <meters>                默认 0.05
  --sigma-y <meters>                默认 0.05
  --capture-stamp-sec <integer>     默认使用当前系统时间
  --capture-stamp-nanosec <integer> 默认使用当前系统时间
  --dry-run                         只打印发布命令
  --auto-source                     自动 source ROS/control/local setup，默认开启
  --no-auto-source                  不自动 source
  --setup-file <path>               追加 setup.bash，可重复
  --clear-setup-files               清空默认 setup 列表，配合 --setup-file 使用
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
