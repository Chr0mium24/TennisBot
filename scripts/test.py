#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


if __name__ == "__main__":
    args = sys.argv[1:]
    cuda = "--cuda" in args
    args = [item for item in args if item != "--cuda"]
    skip_detect = any(item in {"-h", "--help", "--dry-run"} for item in args) or "communication" in args
    extras = [] if skip_detect else ["--extra", "detect-cuda" if cuda else "detect"]
    raise SystemExit(
        run_streaming(
            [
                "uv",
                "run",
                "--project",
                str(REPO_ROOT / "packages/vision-python"),
                *extras,
                "tennisbot-test",
                *args,
            ]
        )
    )
