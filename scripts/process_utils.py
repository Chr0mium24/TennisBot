#!/usr/bin/env python3

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]


def display_command(command: Sequence[str]) -> str:
    return shlex.join(command)


def shell_quote(value: str) -> str:
    return shlex.quote(value)


def process_env() -> dict[str, str]:
    return dict(os.environ)


def run_streaming(
    command: Sequence[str],
    *,
    cwd: Path | str = REPO_ROOT,
    stdin: int | None = None,
) -> int:
    try:
        proc = subprocess.Popen(
            list(command),
            cwd=Path(cwd),
            env=process_env(),
            stdin=stdin,
        )
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 127

    previous_handlers: dict[int, object] = {}
    terminating = False
    hard_kill_timer: threading.Timer | None = None

    def forward(signum: int, _frame: object) -> None:
        nonlocal terminating, hard_kill_timer
        try:
            proc.send_signal(signum)
        except ProcessLookupError:
            return
        if terminating:
            return
        terminating = True
        hard_kill_timer = threading.Timer(2.0, _kill_process, args=(proc,))
        hard_kill_timer.daemon = True
        hard_kill_timer.start()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, forward)

    try:
        return proc.wait()
    finally:
        if hard_kill_timer is not None:
            hard_kill_timer.cancel()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def _kill_process(proc: subprocess.Popen[bytes]) -> None:
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def require_value(args: Sequence[str], index: int, option: str) -> str:
    try:
        value = args[index]
    except IndexError as error:
        raise ValueError(f"{option} requires a value") from error
    if value.startswith("--"):
        raise ValueError(f"{option} requires a value")
    return value


def option_value(args: Sequence[str], name: str) -> str | None:
    for index, arg in enumerate(args):
        if arg == name:
            return require_value(args, index + 1, name)
        if arg.startswith(f"{name}="):
            return arg[len(name) + 1 :]
    return None


def parse_devices(value: str) -> tuple[str, str]:
    devices = [item.strip() for item in value.split(",") if item.strip()]
    if len(devices) != 2:
        raise ValueError("--devices requires exactly two comma-separated devices")
    return devices[0], devices[1]


def has_any_option(args: Iterable[str], names: Sequence[str]) -> bool:
    return any(
        arg == name or arg.startswith(f"{name}=")
        for arg in args
        for name in names
    )
