"""Pytest config — make ``app`` importable without an install step."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_BACKEND = Path(__file__).resolve().parents[1]
if str(_REPO_BACKEND) not in sys.path:
    sys.path.insert(0, str(_REPO_BACKEND))


def pytest_configure(config):  # noqa: ARG001
    os.environ.setdefault("FLASK_SECRET_KEY", "test")
