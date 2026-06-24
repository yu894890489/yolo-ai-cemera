"""SIGHUP-based config hot reload.

Workers register a callback that re-reads config and any cached connections.
Rule-level reload (parsing rule definitions, swapping the YOLO model, etc.) is
M1 work and lives in those worker modules.
"""

from __future__ import annotations

import logging
import signal
from typing import Callable

logger = logging.getLogger(__name__)

_handlers: list[Callable[[], None]] = []


def register_reload(handler: Callable[[], None]) -> None:
    """Register a callable to invoke when SIGHUP arrives.

    Each worker registers its own handler at startup. Order of invocation is
    registration order; handlers should be idempotent and quick.
    """
    _handlers.append(handler)


def _on_sighup(signum, frame):  # noqa: ARG001 - signal API
    logger.info("SIGHUP received; running %d reload handlers", len(_handlers))
    for handler in _handlers:
        try:
            handler()
        except Exception:  # pragma: no cover - defensive
            logger.exception("reload handler failed")


def install_sighup() -> None:
    """Install the SIGHUP handler. Safe to call multiple times."""
    if not hasattr(signal, "SIGHUP"):
        # Windows has no SIGHUP; reload is a no-op there.
        logger.debug("SIGHUP not available on this platform; skip install")
        return
    signal.signal(signal.SIGHUP, _on_sighup)
    logger.info("SIGHUP handler installed")
