"""Saver worker — consume alarm:raw, dedup, persist to MySQL + MinIO + broadcast.

Pipeline per entry:

  1. dedup — the consumer stamps each alarm with ``event_id`` (the 3s-window
     hash). A Redis key short-circuits obvious replays; the repository's UNIQUE
     constraint (MySQL) / seen-set (in-memory) is the durable dedup.
  2. screenshot — the crop JPEG produced by the consumer is uploaded to MinIO
     under a traceable, event-derived object key. The full frame never reaches
     this worker, satisfying the "no full frame lingering" requirement.
  3. persist — one row in ``alarms`` via :class:`AlarmRepo`.
  4. push — an enriched payload is published on Redis Pub/Sub ``ws:alarm`` so the
     Flask main process fans it out to WebSocket/SSE clients.

XACK happens only after the durable write + push succeed. If anything fails the
entry stays pending and a future tick (or restart) replays it; the dedup gate
plus the repo's UNIQUE constraint keep replays idempotent.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import socket
import sys
import time
from typing import Any

import redis

from app.api.models import Alarm
from app.api.repository import AlarmRepo, InMemoryAlarmRepo, MySQLAlarmRepo
from app.common.streams import ack, ensure_group, make_client, pending_count, read_group
from app.workers.base import WorkerBase

logger = logging.getLogger(__name__)

_WS_CHANNEL = "ws:alarm"
_DEDUP_KEY_PREFIX = "dedup:event:"
_DEDUP_TTL_S = 3600


class _MinioWriter:
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self._client = None

    def client(self):
        if self._client is not None:
            return self._client
        try:
            from minio import Minio  # type: ignore
        except ImportError:
            logger.warning("minio sdk not installed; screenshot upload will be a no-op")
            return None
        self._client = Minio(
            self.cfg.minio.endpoint,
            access_key=self.cfg.minio.access_key,
            secret_key=self.cfg.minio.secret_key,
            secure=self.cfg.minio.secure,
        )
        return self._client

    def put_screenshot(self, object_key: str, jpeg_bytes: bytes) -> str | None:
        client = self.client()
        if client is None:
            return None
        try:
            client.put_object(
                bucket_name=self.cfg.minio.bucket_alarms,
                object_name=object_key,
                data=io.BytesIO(jpeg_bytes),
                length=len(jpeg_bytes),
                content_type="image/jpeg",
            )
        except Exception:
            logger.exception("minio put failed for %s", object_key)
            raise
        return object_key


class SaverWorker(WorkerBase):
    name = "saver"
    metrics_port_attr = "saver"

    def __init__(self) -> None:
        super().__init__()
        self.client: redis.Redis | None = None
        self.minio: _MinioWriter | None = None
        self.alarm_repo: AlarmRepo | None = None
        self._consumer_name = f"{self.name}-{socket.gethostname()}"

    def setup(self) -> None:
        self.client = make_client(self.cfg)
        ensure_group(self.client, self.cfg.streams.alarm_raw, self.cfg.streams.group_saver)
        self.minio = _MinioWriter(self.cfg)
        if os.environ.get("API_REPO", "memory") == "mysql":
            self.alarm_repo = MySQLAlarmRepo(
                {
                    "host": self.cfg.mysql.host,
                    "port": self.cfg.mysql.port,
                    "user": self.cfg.mysql.user,
                    "password": self.cfg.mysql.password,
                    "database": self.cfg.mysql.db,
                }
            )
        else:
            self.alarm_repo = InMemoryAlarmRepo()

    def _screenshot_key(self, event_id: str, ts_ms: int) -> str:
        day = time.strftime("%Y/%m/%d", time.gmtime(ts_ms / 1000.0 if ts_ms else time.time()))
        return f"{day}/{event_id}.jpg"

    def _resolve_business_line(self, task_id: str) -> str:
        """Look up the owning task's business_line from Redis task config. Falls
        back to the phase1 default when the config is absent (demo task or
        pre-Stage1 producer that never published business_line)."""
        from app.api.models import DEFAULT_BUSINESS_LINE

        assert self.client is not None
        if not task_id:
            return DEFAULT_BUSINESS_LINE
        raw = self.client.get(f"task:{task_id}")
        if not raw:
            return DEFAULT_BUSINESS_LINE
        try:
            cfg = json.loads(raw)
        except (ValueError, TypeError):
            return DEFAULT_BUSINESS_LINE
        bl = cfg.get("business_line")
        return bl or DEFAULT_BUSINESS_LINE

    def _persist_entry(self, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Dedup + upload + persist a single alarm.

        Returns the WS payload to push, or ``None`` when the Redis gate proves
        this entry was already fully processed (persisted *and* pushed). The
        gate key is set by the caller only after the push succeeds, so a crash
        between persist and push leaves the gate unset; the replay then finds
        the row already present (repo returns ``None``) but STILL builds a
        payload, giving at-least-once push delivery (clients dedup on
        ``event_id``)."""
        assert self.client is not None and self.minio is not None and self.alarm_repo is not None
        event_id = fields.get("event_id", "")
        dedup_key = f"{_DEDUP_KEY_PREFIX}{event_id}" if event_id else ""

        if dedup_key and self.client.get(dedup_key) is not None:
            return None

        try:
            ts_ms = int(fields.get("ts_ms") or 0)
        except ValueError:
            ts_ms = 0

        crop_b64 = fields.get("crop_jpeg_b64") or fields.get("frame_jpeg_b64") or ""
        try:
            jpeg_bytes = base64.b64decode(crop_b64) if crop_b64 else b""
        except (ValueError, binascii.Error):
            logger.warning("saver: malformed crop for event_id=%s; skipping screenshot", event_id)
            jpeg_bytes = b""
        object_key = (
            self.minio.put_screenshot(self._screenshot_key(event_id, ts_ms), jpeg_bytes)
            if jpeg_bytes
            else None
        )

        try:
            score = float(fields.get("score", 0.0) or 0.0)
        except ValueError:
            score = 0.0
        try:
            vlm_conf = float(fields.get("vlm_confidence", 0.0) or 0.0)
        except ValueError:
            vlm_conf = 0.0

        alarm = Alarm(
            event_id=event_id,
            task_id=fields.get("task_id", ""),
            rule_id=fields.get("rule_id", "demo"),
            class_name=fields.get("class", ""),
            score=score,
            bbox=fields.get("bbox", ""),
            roi=fields.get("roi", ""),
            mode=fields.get("mode", "default"),
            vlm_status=fields.get("vlm_status", ""),
            vlm_reason=fields.get("vlm_reason", ""),
            vlm_confidence=vlm_conf,
            screenshot_object=object_key or "",
            ts_ms=ts_ms,
            business_line=self._resolve_business_line(fields.get("task_id", "")),
        )
        # create() returns None on a durable-dedup hit (row already exists). We
        # still push in that case — the prior attempt may have crashed before
        # pushing, and a duplicate push is harmless (clients dedup on event_id).
        created = self.alarm_repo.create(alarm) or alarm
        return {
            "alarm_id": created.id,
            "event_id": created.event_id,
            "task_id": created.task_id,
            "rule_id": created.rule_id,
            "class": created.class_name,
            "score": created.score,
            "mode": created.mode,
            "vlm_status": created.vlm_status,
            "vlm_reason": created.vlm_reason,
            "vlm_confidence": created.vlm_confidence,
            "screenshot_object": created.screenshot_object,
            "ts_ms": created.ts_ms,
        }

    def step(self) -> None:
        assert self.client is not None and self.minio is not None and self.alarm_repo is not None
        stream = self.cfg.streams.alarm_raw
        group = self.cfg.streams.group_saver

        entries = read_group(
            self.client,
            stream=stream,
            group=group,
            consumer=self._consumer_name,
            count=16,
            block_ms=500,
        )
        if not entries:
            return

        self.metrics.stream_lag.labels(stream=stream).set(
            pending_count(self.client, stream, group)
        )

        ack_ids: list[str] = []
        for entry_id, fields in entries:
            try:
                payload = self._persist_entry(fields)
                if payload is not None:
                    self.client.publish(_WS_CHANNEL, json.dumps(payload))
                    self.client.xadd(
                        self.cfg.streams.alarm_pushed,
                        {"alarm_id": payload["alarm_id"], "ts_ms": str(int(time.time() * 1000))},
                    )
                    self.metrics.alarm_emit_total.labels(
                        rule_id=fields.get("rule_id", "unknown")
                    ).inc()
                    # Set the dedup gate only after the push lands, so a crash
                    # before this point lets the replay re-push (at-least-once).
                    event_id = fields.get("event_id", "")
                    if event_id:
                        self.client.set(
                            f"{_DEDUP_KEY_PREFIX}{event_id}", "1", ex=_DEDUP_TTL_S
                        )
            except Exception:
                logger.exception("saver: failed entry %s; left pending", entry_id)
                continue
            ack_ids.append(entry_id)

        if ack_ids:
            ack(self.client, stream, group, ack_ids)

    def teardown(self) -> None:
        try:
            if self.client is not None:
                self.client.close()
        except Exception:
            pass


def main() -> int:
    return SaverWorker().run()


if __name__ == "__main__":
    sys.exit(main())
