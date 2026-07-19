from __future__ import annotations

import os
from pathlib import Path
import shlex
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[4]


def process_env() -> dict[str, str]:
    return dict(os.environ)


def require_value(args: Sequence[str], index: int, option: str) -> str:
    try:
        value = args[index]
    except IndexError as error:
        raise ValueError(f"{option} requires a value") from error
    if value.startswith("--"):
        raise ValueError(f"{option} requires a value")
    return value


def shell_quote(value: str) -> str:
    return shlex.quote(value)
