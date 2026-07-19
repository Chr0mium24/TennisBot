#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


if __name__ == "__main__":
    raise SystemExit(
        run_streaming(
            ["uv", "run", "--project", str(REPO_ROOT / "packages/vision-python"), "tennisbot-camera", *sys.argv[1:]]
        )
    )
