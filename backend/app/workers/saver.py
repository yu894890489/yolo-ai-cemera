"""Saver worker — consume alarm:raw, persist to MySQL + MinIO + broadcast.

For M0 the MySQL insert is a stub (schema lands in S2 on 06-26) and the
WebSocket broadcast goes through Redis Pub/Sub so the Flask main process can
fan out without sharing in-process state. MinIO upload is real — the bucket is
created by BE-M0-S5 and we PUT a .jpg per alarm.

XACK is performed only after BOTH the MySQL write and the MinIO put succeed.
If either fails, the entry stays pending and a future tick (or restart) replays
it.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import socket
import sys
import time
import uuid
from typing import Any

import redis

from app.common.streams import ack, ensure_group, make_client, pending_count, read_group
from app.workers.base import WorkerBase

logger = logging.getLogger(__name__)

_WS_CHANNEL = "ws:alarm"


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

    def put_screenshot(self, alarm_id: str, jpeg_bytes: bytes) -> str | None:
        client = self.client()
        if client is None:
            return None
        object_name = f"{time.strftime('%Y/%m/%d')}/{alarm_id}.jpg"
        try:
            client.put_object(
                bucket_name=self.cfg.minio.bucket_alarms,
                object_name=object_name,
                data=io.BytesIO(jpeg_bytes),
                length=len(jpeg_bytes),
                content_type="image/jpeg",
            )
        except Exception:
            logger.exception("minio put failed for %s", object_name)
            raise
        return object_name


class _MysqlWriter:
    def __init__(self, cfg) -> None:
        self.cfg = cfg

    def insert_alarm(self, alarm: dict[str, Any], object_name: str | None) -> None:
        # Log-only stub. Returns when the row would have been written.
        # Once S2 ships the schema, swap this body for the real SQL —
        # the worker contract stays the same.
        logger.info(
            "mysql(stub): alarm task_id=%s rule_id=%s class=%s score=%.3f object=%s",
            alarm.get("task_id"),
            alarm.get("rule_id"),
            alarm.get("class"),
            float(alarm.get("score", 0.0) or 0.0),
            object_name,
        )


class SaverWorker(WorkerBase):
    name = "saver"
    metrics_port_attr = "saver"

    def __init__(self) -> None:
        super().__init__()
        self.client: redis.Redis | None = None
        self.minio: _MinioWriter | None = None
        self.mysql: _MysqlWriter | None = None
        self._consumer_name = f"{self.name}-{socket.gethostname()}"

    def setup(self) -> None:
        self.client = make_client(self.cfg)
        ensure_group(self.client, self.cfg.streams.alarm_raw, self.cfg.streams.group_saver)
        self.minio = _MinioWriter(self.cfg)
        self.mysql = _MysqlWriter(self.cfg)

    def step(self) -> None:
        assert self.client is not None and self.minio is not None and self.mysql is not None
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
            alarm_id = uuid.uuid4().hex
            try:
                jpeg_b64 = fields.get("frame_jpeg_b64", "")
                jpeg_bytes = base64.b64decode(jpeg_b64) if jpeg_b64 else b""
                object_name = (
                    self.minio.put_screenshot(alarm_id, jpeg_bytes) if jpeg_bytes else None
                )
                self.mysql.insert_alarm(fields, object_name)

                payload = {
                    "alarm_id": alarm_id,
                    "task_id": fields.get("task_id"),
                    "rule_id": fields.get("rule_id"),
                    "class": fields.get("class"),
                    "score": fields.get("score"),
                    "ts_ms": fields.get("ts_ms"),
                    "object_name": object_name,
                }
                self.client.publish(_WS_CHANNEL, json.dumps(payload))

                self.client.xadd(
                    self.cfg.streams.alarm_pushed,
                    {"alarm_id": alarm_id, "ts_ms": str(int(time.time() * 1000))},
                )
                self.metrics.alarm_emit_total.labels(rule_id=fields.get("rule_id", "unknown")).inc()
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
