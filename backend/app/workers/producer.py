"""Producer worker — pull stream, decode frames, push to ``frame:{task_id}``.

For M0-S3 the producer ships with a deterministic ``DummySource`` so the full
chain can be exercised without a real RTSP feed. Real RTSP pull + frame
sampling is M1 work; the contract this worker commits to is:

  * one Redis Stream per task: ``frame:{task_id}``
  * fields: ``task_id``, ``seq``, ``ts_ms``, ``frame_jpeg_b64``
  * backpressure: if the stream's MAXLEN approximation is exceeded, drop and
    increment ``frame_drop_total{reason="backpressure"}``.

Run with ``python -m app.workers.producer`` inside the container.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time

from app.common.streams import make_client
from app.workers.base import WorkerBase

logger = logging.getLogger(__name__)

# Cap each task's stream so a stalled consumer cannot blow up Redis memory.
# Approximate MAXLEN (~) is O(log n) compared to exact O(n); plenty for M0.
_FRAME_STREAM_MAXLEN_APPROX = 2000


class DummySource:
    """Emit a single 32x32 black JPEG once per second, forever.

    Lets the M0 chain validate without an RTSP feed. The Consumer treats every
    frame as a candidate so this is enough to exercise the alarm path too.
    """

    _BLACK_32x32_JPEG_B64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
        "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAAgACADASIA"
        "AhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAr/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEB"
        "AAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AB//Z"
    )

    def __init__(self, task_id: str, source_address: str = "dummy") -> None:
        self.task_id = task_id
        self.source_address = source_address
        self._seq = 0

    def next_frame(self) -> tuple[int, bytes] | None:
        self._seq += 1
        time.sleep(1.0)
        return self._seq, self._BLACK_32x32_JPEG_B64.encode("ascii")


class ProducerWorker(WorkerBase):
    name = "producer"
    metrics_port_attr = "producer"

    def __init__(self) -> None:
        super().__init__()
        self.client = None
        self.source: DummySource | None = None
        self._source_mode = "demo"

    def setup(self) -> None:
        self.client = make_client(self.cfg)
        # Demo task id is overridable via env so an operator can validate per
        # acceptance criteria without code changes.
        task_id = os.environ.get("DEMO_TASK_ID", "demo")
        self.source = DummySource(task_id=task_id)
        logger.info("producer: source task_id=%s", task_id)

    def _load_runtime_source(self) -> DummySource | None:
        assert self.client is not None
        task_ids = sorted(self.client.smembers("tasks:active"))
        for task_id in task_ids:
            raw = self.client.get(f"task:{task_id}")
            if raw is None:
                continue
            config = json.loads(raw)
            if self._source_mode == "runtime" and self.source is not None and self.source.task_id == config["task_id"]:
                return self.source
            return DummySource(task_id=config["task_id"], source_address=config["source_address"])
        return None

    def _fallback_source(self) -> DummySource:
        task_id = os.environ.get("DEMO_TASK_ID", "demo")
        if self._source_mode == "demo" and self.source is not None and self.source.task_id == task_id:
            return self.source
        return DummySource(task_id=task_id)

    def step(self) -> None:
        assert self.client is not None
        source = self._load_runtime_source()
        if source is not None:
            self._source_mode = "runtime"
            self.source = source
        elif self._source_mode == "runtime":
            self.source = None
            return
        else:
            source = self._fallback_source()
            self._source_mode = "demo"
            self.source = source
        result = source.next_frame()
        if result is None:
            return
        seq, frame_b64 = result
        stream = f"{self.cfg.streams.frame_prefix}{source.task_id}"
        # ``XADD ... MAXLEN ~`` is the contract; redis-py exposes it as
        # ``maxlen`` + ``approximate=True``.
        try:
            self.client.xadd(
                stream,
                {
                    "task_id": source.task_id,
                    "seq": str(seq),
                    "ts_ms": str(int(time.time() * 1000)),
                    "frame_jpeg_b64": frame_b64.decode("ascii"),
                },
                maxlen=_FRAME_STREAM_MAXLEN_APPROX,
                approximate=True,
            )
            self.metrics.frame_in_total.labels(task_id=source.task_id).inc()
        except Exception:
            self.metrics.frame_drop_total.labels(reason="xadd_error").inc()
            raise

    def teardown(self) -> None:
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass


def main() -> int:
    return ProducerWorker().run()


if __name__ == "__main__":
    sys.exit(main())
