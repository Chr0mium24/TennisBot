from __future__ import annotations

import os


def main() -> int:
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    from pytest import console_main

    return int(console_main())
