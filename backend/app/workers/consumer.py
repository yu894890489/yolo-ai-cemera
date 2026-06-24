"""Consumer worker — read frame:* Streams, run YOLO, emit alarm:raw.

Two responsibilities, kept separate so M1 can plug a real rule engine in:

  * _infer — runs the detector. If ultralytics + torch are unavailable
    (the container slot reserved for it), it falls back to a stub that
    matches the I/O shape so the full chain stays unblocked.

  * _evaluate_rules — turns detections into alarms. For M0 the rule is
    intentionally trivial ("any detection emits one alarm of rule_id=demo").
    Real rules land in M1.

Zero-loss contract: an entry is XACK'd only after the alarm has been XADD'd
to alarm:raw (or the inference judged it had no alarm to emit). If the
process dies between XADD and XACK, the same frame is replayed; consumer logic
must therefore be idempotent at the alarm level (M1 dedupes by content hash).
"""

from __future__ import annotations

import logging
import socket
import sys
import time
from typing import Any

import redis

from app.common.streams import ack, ensure_group, make_client, pending_count, read_group
from app.workers.base import WorkerBase

logger = logging.getLogger(__name__)


class _StubDetector:
    def detect(self, frame_b64: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return [{"class": "person", "score": 0.9, "bbox": [0, 0, 10, 10]}]


def _load_detector(model_path: str, device: str):
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        logger.warning("ultralytics not installed; using stub detector")
        return _StubDetector()
    try:
        model = YOLO(model_path)
        logger.info("loaded YOLO model=%s device=%s", model_path, device)
        return model
    except Exception:
        logger.exception("YOLO load failed; falling back to stub")
        return _StubDetector()


class ConsumerWorker(WorkerBase):
    name = "consumer"
    metrics_port_attr = "consumer"

    _SCAN_INTERVAL_SEC = 5.0

    def __init__(self) -> None:
        super().__init__()
        self.client: redis.Redis | None = None
        self.detector = None
        self._consumer_name = f"{self.name}-{socket.gethostname()}"
        self._known_streams: set[str] = set()
        self._last_scan: float = 0.0

    def setup(self) -> None:
        self.client = make_client(self.cfg)
        self.detector = _load_detector(self.cfg.yolo.model, self.cfg.yolo.device)

    def on_reload(self) -> None:
        new_model = self.cfg.yolo.model
        self.detector = _load_detector(new_model, self.cfg.yolo.device)

    def _refresh_streams(self) -> None:
        assert self.client is not None
        now = time.monotonic()
        if now - self._last_scan < self._SCAN_INTERVAL_SEC:
            return
        self._last_scan = now
        prefix = self.cfg.streams.frame_prefix
        cursor = 0
        found: set[str] = set()
        while True:
            cursor, keys = self.client.scan(cursor=cursor, match=f"{prefix}*", count=200)
            for key in keys:
                found.add(key)
            if cursor == 0:
                break
        new_streams = found - self._known_streams
        for stream in new_streams:
            ensure_group(self.client, stream, self.cfg.streams.group_consumer)
        self._known_streams = found

    def _infer(self, frame_b64: str) -> list[dict[str, Any]]:
        t0 = time.perf_counter()
        try:
            return self.detector.detect(frame_b64)  # type: ignore[union-attr]
        finally:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            self.metrics.yolo_latency_ms.observe(dt_ms)

    def _evaluate_rules(self, task_id: str, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alarms = []
        for det in detections:
            alarms.append(
                {
                    "task_id": task_id,
                    "rule_id": "demo",
                    "class": det.get("class", "unknown"),
                    "score": float(det.get("score", 0.0)),
                    "bbox": ",".join(str(v) for v in det.get("bbox", [])),
                    "ts_ms": str(int(time.time() * 1000)),
                }
            )
        return alarms

    def step(self) -> None:
        assert self.client is not None
        self._refresh_streams()
        if not self._known_streams:
            time.sleep(0.5)
            return

        group = self.cfg.streams.group_consumer
        alarm_stream = self.cfg.streams.alarm_raw

        for frame_stream in list(self._known_streams):
            entries = read_group(
                self.client,
                stream=frame_stream,
                group=group,
                consumer=self._consumer_name,
                count=8,
                block_ms=200,
            )
            if not entries:
                continue
            self.metrics.stream_lag.labels(stream=frame_stream).set(
                pending_count(self.client, frame_stream, group)
            )

            ack_ids: list[str] = []
            for entry_id, fields in entries:
                task_id = fields.get("task_id", "unknown")
                self.metrics.frame_in_total.labels(task_id=task_id).inc()
                try:
                    detections = self._infer(fields.get("frame_jpeg_b64", ""))
                    alarms = self._evaluate_rules(task_id, detections)
                    for alarm in alarms:
                        alarm["frame_jpeg_b64"] = fields.get("frame_jpeg_b64", "")
                        self.client.xadd(alarm_stream, alarm)
                        self.metrics.alarm_emit_total.labels(rule_id=alarm["rule_id"]).inc()
                except Exception:
                    logger.exception(
                        "consumer: failed processing %s on %s; left pending",
                        entry_id,
                        frame_stream,
                    )
                    continue
                ack_ids.append(entry_id)
            if ack_ids:
                ack(self.client, frame_stream, group, ack_ids)

    def teardown(self) -> None:
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass


def main() -> int:
    return ConsumerWorker().run()


if __name__ == "__main__":
    sys.exit(main())
