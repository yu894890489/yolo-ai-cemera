"""Prometheus metrics — shared registry definitions used by all workers.

Each worker imports the metrics it owns and serves them on its own port via
``prometheus_client.start_http_server``. Keeping the names central avoids
typo-divergence across workers, which is the most common breakage of
dashboard queries.
"""

from __future__ import annotations

import logging
from typing import Iterable

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    start_http_server,
)

logger = logging.getLogger(__name__)


def new_registry() -> CollectorRegistry:
    return CollectorRegistry()


def build_metrics(registry: CollectorRegistry, worker: str) -> "Metrics":
    return Metrics(registry, worker)


class Metrics:
    """Metric handles for one worker process.

    ``worker`` is exposed as the ``worker`` label on ``process_up`` and is also
    set on the histogram-buckets gauge to make multi-worker dashboards readable.
    """

    # YOLO target is sub-50ms on RTX 2060, buckets stretch wide enough to surface
    # the slow tail (cold start, large frames).
    _YOLO_LATENCY_BUCKETS_MS: Iterable[float] = (
        5, 10, 20, 35, 50, 75, 100, 150, 250, 500, 1000, 2500,
    )

    def __init__(self, registry: CollectorRegistry, worker: str) -> None:
        self.worker = worker
        self.registry = registry

        self.frame_in_total = Counter(
            "frame_in_total",
            "Frames produced or consumed",
            labelnames=("task_id",),
            registry=registry,
        )
        self.frame_drop_total = Counter(
            "frame_drop_total",
            "Frames dropped (backpressure, decode failure, etc.)",
            labelnames=("reason",),
            registry=registry,
        )
        self.yolo_latency_ms = Histogram(
            "yolo_latency_ms",
            "End-to-end YOLO inference latency in milliseconds",
            buckets=tuple(self._YOLO_LATENCY_BUCKETS_MS),
            registry=registry,
        )
        self.alarm_emit_total = Counter(
            "alarm_emit_total",
            "Alarms emitted",
            labelnames=("rule_id",),
            registry=registry,
        )
        self.stream_lag = Gauge(
            "stream_lag",
            "Pending entries on a Redis Stream for this worker's consumer group",
            labelnames=("stream",),
            registry=registry,
        )
        self.process_up = Gauge(
            "process_up",
            "1 if the worker has finished startup",
            labelnames=("worker",),
            registry=registry,
        )
        self.process_up.labels(worker=worker).set(0)


def serve(port: int, registry: CollectorRegistry) -> None:
    """Bind the metrics HTTP server. Non-blocking."""
    start_http_server(port, registry=registry)
    logger.info("metrics server listening on :%d", port)
