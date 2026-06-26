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

from app.common.config import fetch_vlm_endpoints
from app.common.dedup import event_id as make_event_id
from app.common.imaging import crop_jpeg_b64
from app.common.streams import ack, ensure_group, make_client, pending_count, read_group
from app.common.vlm import VLMClient, VLMRequestError, VLMRuntimeState, interpret_judgment
from app.workers.base import WorkerBase

logger = logging.getLogger(__name__)


def _bbox_overlaps_roi(bbox: list[float], roi: list[int]) -> bool:
    """True if ``bbox`` [x1,y1,x2,y2] intersects ``roi``. Missing bbox passes."""
    if len(bbox) != 4 or len(roi) != 4:
        return True
    bx1, by1, bx2, by2 = bbox
    rx1, ry1, rx2, ry2 = roi
    return not (bx2 < rx1 or bx1 > rx2 or by2 < ry1 or by1 > ry2)


def _resolve_ts_ms(fields: dict[str, str], entry_id: str) -> int:
    """Resolve the frame timestamp used for the dedup window.

    ``event_id`` is derived from this value, so the fallback must be stable
    across re-delivery — a wall-clock fallback would shift a replayed frame
    into a different window and duplicate the alarm. The Redis stream entry-id
    millisecond prefix (e.g. ``1700000000000-3``) is redelivered unchanged, so
    it is the deterministic fallback when the producer didn't stamp ``ts_ms``.
    """
    try:
        ts = int(fields.get("ts_ms") or 0)
    except (TypeError, ValueError):
        ts = 0
    if ts > 0:
        return ts
    try:
        return int(str(entry_id).split("-", 1)[0])
    except (TypeError, ValueError):
        return 0


class _StubDetector:
    def detect(self, frame_b64: str) -> list[dict[str, Any]]:  # noqa: ARG002
        return [{"class": "person", "score": 0.9, "bbox": [0, 0, 10, 10]}]


class _YoloDetector:
    """Wraps an ultralytics model so it exposes the same ``detect`` contract.

    Decodes the base64 JPEG once, runs inference, and returns normalised
    detection dicts (``class`` / ``score`` / ``bbox`` = [x1,y1,x2,y2]).
    """

    def __init__(self, model, device: str) -> None:
        self._model = model
        self._device = device

    def detect(self, frame_b64: str) -> list[dict[str, Any]]:
        from app.common.imaging import decode_jpeg_b64

        img = decode_jpeg_b64(frame_b64)
        if img is None:
            return []
        results = self._model.predict(img, device=self._device, verbose=False)
        out: list[dict[str, Any]] = []
        names = getattr(self._model, "names", {})
        for res in results:
            boxes = getattr(res, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                cls_idx = int(box.cls[0])
                out.append(
                    {
                        "class": names.get(cls_idx, str(cls_idx)) if isinstance(names, dict) else str(cls_idx),
                        "score": float(box.conf[0]),
                        "bbox": [float(v) for v in box.xyxy[0].tolist()],
                    }
                )
        return out



def _load_detector(model_path: str, device: str):
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        logger.warning("ultralytics not installed; using stub detector")
        return _StubDetector()
    try:
        model = YOLO(model_path)
        logger.info("loaded YOLO model=%s device=%s", model_path, device)
        return _YoloDetector(model, device)
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
        self.vlm_state = VLMRuntimeState()
        self.vlm_client: VLMClient | None = None

    def setup(self) -> None:
        self.client = make_client(self.cfg)
        self.detector = _load_detector(self.cfg.yolo.model, self.cfg.yolo.device)
        self._build_vlm()

    def on_reload(self) -> None:
        new_model = self.cfg.yolo.model
        self.detector = _load_detector(new_model, self.cfg.yolo.device)
        self._build_vlm()

    def _build_vlm(self) -> None:
        ep_list = fetch_vlm_endpoints(self.cfg)
        if not ep_list and self.cfg.task.vlm_enabled:
            logger.info("VLM enabled but no endpoints; disabling VLM")
        self.vlm_state = VLMRuntimeState()
        self.vlm_client = VLMClient(
            endpoints=ep_list,
            state=self.vlm_state,
            max_retries=self.cfg.vlm.max_retries,
            backoff_base_s=self.cfg.vlm.backoff_base_s,
            disable_thinking=self.cfg.vlm.disable_thinking,
        )

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

    def _filter_detections(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply confidence threshold, target-class filter, and ROI gate."""
        conf = self.cfg.task.confidence
        classes = self.cfg.task.classes
        roi = self.cfg.task.roi
        out: list[dict[str, Any]] = []
        for det in detections:
            if float(det.get("score", 0.0)) < conf:
                continue
            cls = det.get("class", "unknown")
            if classes and cls not in classes:
                continue
            bbox = [float(v) for v in det.get("bbox", [])]
            if roi and not _bbox_overlaps_roi(bbox, roi):
                continue
            out.append(det)
        return out

    def _build_alarm(
        self,
        task_id: str,
        det: dict[str, Any],
        *,
        mode: str,
        crop_b64: str,
        ts_ms: int,
        vlm_status: str,
        judgment: dict[str, Any] | None = None,
        vlm_error: str | None = None,
    ) -> dict[str, str]:
        roi_str = ",".join(str(v) for v in self.cfg.task.roi) if self.cfg.task.roi else ""
        cls = str(det.get("class", "unknown"))
        eid = make_event_id(
            task_id, roi_str, cls, ts_ms=ts_ms, window_s=self.cfg.vlm.dedup_window_s
        )
        alarm: dict[str, str] = {
            "task_id": task_id,
            "rule_id": "demo",
            "class": cls,
            "score": str(float(det.get("score", 0.0))),
            "bbox": ",".join(str(v) for v in det.get("bbox", [])),
            "roi": roi_str,
            "ts_ms": str(ts_ms),
            "mode": mode,
            "event_id": eid,
            "crop_jpeg_b64": crop_b64 or "",
            "vlm_status": vlm_status,
            "vlm_reason": str((judgment or {}).get("reason", "")),
            "vlm_confidence": str((judgment or {}).get("confidence", "")),
            "vlm_summary": str((judgment or {}).get("summary", "")),
        }
        if vlm_error:
            alarm["vlm_error"] = vlm_error
        return alarm

    def _process_frame(
        self, frame_stream: str, task_id: str, fields: dict[str, str], entry_id: str
    ) -> list[dict[str, str]]:
        frame_b64 = fields.get("frame_jpeg_b64", "")
        ts_ms = _resolve_ts_ms(fields, entry_id)

        hits = self._filter_detections(self._infer(frame_b64))
        if not hits:
            return []

        mode, vlm_error = self._vlm_guard(frame_stream)
        alarms: list[dict[str, str]] = []
        for det in hits:
            bbox = [float(v) for v in det.get("bbox", [])]
            crop_b64 = (crop_jpeg_b64(frame_b64, bbox) if bbox else None) or ""

            if mode == "vlm" and self.vlm_client is not None:
                try:
                    raw = self.vlm_client.analyze(
                        crop_b64 or frame_b64, prompt=self.cfg.task.prompt, crop={"bbox": bbox}
                    )
                except VLMRequestError as exc:
                    alarms.append(
                        self._build_alarm(
                            task_id, det, mode="small_only", crop_b64=crop_b64,
                            ts_ms=ts_ms, vlm_status="failed", vlm_error=str(exc),
                        )
                    )
                    continue
                judgment = interpret_judgment(raw)
                if not judgment["is_alarm"]:
                    continue
                alarms.append(
                    self._build_alarm(
                        task_id, det, mode="vlm", crop_b64=crop_b64,
                        ts_ms=ts_ms, vlm_status="ok", judgment=judgment,
                    )
                )
            elif mode == "small_only":
                alarms.append(
                    self._build_alarm(
                        task_id, det, mode="small_only", crop_b64=crop_b64,
                        ts_ms=ts_ms, vlm_status="skipped", vlm_error=vlm_error,
                    )
                )
            else:
                alarms.append(
                    self._build_alarm(
                        task_id, det, mode="default", crop_b64=crop_b64,
                        ts_ms=ts_ms, vlm_status="disabled",
                    )
                )
        return alarms

    def _vlm_guard(self, frame_stream: str) -> tuple[str, str | None]:
        if not self.cfg.task.vlm_enabled:
            return "default", None
        queue_lag = pending_count(self.client, frame_stream, self.cfg.streams.group_consumer)  # type: ignore[arg-type]
        if queue_lag >= self.cfg.vlm.queue_high_watermark:
            self.vlm_state.degraded_mode = "small_only"
            self.vlm_state.last_failure_reason = "queue_high_watermark"
            return "small_only", "queue_high_watermark"
        if self.vlm_client is None:
            return "small_only", "vlm_client_missing"
        return "vlm", None

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
                    alarms = self._process_frame(frame_stream, task_id, fields, entry_id)
                    for alarm in alarms:
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
