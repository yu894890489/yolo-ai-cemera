"""Shared worker scaffolding.

A worker is a small loop:

  1. Construct an :class:`AppConfig`.
  2. Bind a metrics HTTP server on its own port.
  3. Install the SIGHUP reload handler.
  4. Enter the main loop (subclass responsibility).
  5. On SIGTERM/SIGINT, flip ``process_up`` to 0 and exit cleanly.

The skeleton intentionally does not import ultralytics / opencv / minio
top-level — that way the Producer / Saver containers do not need GPU wheels.
"""

from __future__ import annotations

import logging
import signal
import time
from abc import ABC, abstractmethod

from app.common import metrics as metrics_mod
from app.common.config import AppConfig, get_config, reload_config
from app.common.signals import install_sighup, register_reload

logger = logging.getLogger(__name__)


class WorkerBase(ABC):
    """Lifecycle skeleton; subclasses implement :meth:`step`."""

    name: str = "worker"
    metrics_port_attr: str = ""

    def __init__(self) -> None:
        self.cfg: AppConfig = get_config()
        self.registry = metrics_mod.new_registry()
        self.metrics = metrics_mod.build_metrics(self.registry, self.name)
        self._running = True

    def metrics_port(self) -> int:
        return int(getattr(self.cfg.ports, self.metrics_port_attr))

    def _on_term(self, signum, frame):  # noqa: ARG002 - signal API
        logger.info("%s: signal %d received, shutting down", self.name, signum)
        self._running = False

    def _on_reload(self) -> None:
        self.cfg = reload_config()
        self.on_reload()

    def on_reload(self) -> None:
        """Hook for subclasses to refresh derived state after SIGHUP."""

    @abstractmethod
    def setup(self) -> None:
        """One-shot setup before the main loop (open clients, create groups)."""

    @abstractmethod
    def step(self) -> None:
        """Run one tick of work. May block briefly waiting on Redis."""

    def teardown(self) -> None:
        """Best-effort cleanup. Default is a no-op."""

    def run(self) -> int:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )

        metrics_mod.serve(self.metrics_port(), self.registry)

        install_sighup()
        register_reload(self._on_reload)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._on_term)

        try:
            self.setup()
        except Exception:
            logger.exception("%s: setup failed", self.name)
            return 2

        self.metrics.process_up.labels(worker=self.name).set(1)
        logger.info("%s: up, entering main loop", self.name)
        try:
            while self._running:
                try:
                    self.step()
                except Exception:
                    logger.exception("%s: step failed, backing off 1s", self.name)
                    time.sleep(1.0)
        finally:
            self.metrics.process_up.labels(worker=self.name).set(0)
            try:
                self.teardown()
            except Exception:
                logger.exception("%s: teardown failed", self.name)
            logger.info("%s: exit", self.name)
        return 0
