#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


if __name__ == "__main__":
    extras = [] if any(item in {"-h", "--help", "--dry-run"} for item in sys.argv[1:]) or "communication" in sys.argv[1:] else ["--extra", "detect"]
    raise SystemExit(run_streaming([
        "uv", "run", "--project", str(REPO_ROOT / "packages/vision-python"), *extras, "tennisbot-test", *sys.argv[1:]
    ]))
