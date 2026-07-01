from __future__ import annotations

import os
import sys


def main() -> int:
    os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    import pytest

    return pytest.main(sys.argv[1:])
