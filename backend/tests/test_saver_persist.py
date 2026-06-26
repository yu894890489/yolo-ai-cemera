"""Saver persistence path: dedup, MinIO upload, alarm row, enriched WS (BE-M1-B)."""

from __future__ import annotations

import base64
import json

import numpy as np
import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.api.models import Alarm  # noqa: E402
from app.api.repository import InMemoryAlarmRepo  # noqa: E402
from app.common import config as config_mod  # noqa: E402
from app.common import imaging  # noqa: E402
from app.workers import saver as saver_mod  # noqa: E402


@pytest.fixture
def fake_client():
    server = fakeredis.FakeServer()
    return fakeredis.FakeStrictRedis(server=server, decode_responses=True)


class _RecordingMinio:
    def __init__(self):
        self.puts = []

    def put_screenshot(self, object_key, jpeg_bytes):
        self.puts.append((object_key, jpeg_bytes))
        return object_key


def _crop_b64():
    return imaging.encode_jpeg_b64(np.full((30, 30, 3), 120, dtype=np.uint8))


def _alarm_fields(event_id="e1", **kw):
    base = {
        "task_id": "demo",
        "rule_id": "demo",
        "class": "person",
        "score": "0.9",
        "bbox": "10,10,40,40",
        "roi": "",
        "ts_ms": "1000",
        "mode": "vlm",
        "event_id": event_id,
        "crop_jpeg_b64": _crop_b64(),
        "vlm_status": "ok",
        "vlm_reason": "person climbing",
        "vlm_confidence": "0.88",
        "vlm_summary": "intruder",
    }
    base.update(kw)
    return base


def _make_worker(fake_client, cfg, repo, minio):
    worker = saver_mod.SaverWorker()
    worker.client = fake_client
    worker.cfg = cfg
    worker.alarm_repo = repo
    worker.minio = minio
    fake_client.xgroup_create(
        name=cfg.streams.alarm_raw, groupname=cfg.streams.group_saver, id="0", mkstream=True
    )
    return worker


def test_alarm_is_persisted_uploaded_and_pushed(fake_client):
    cfg = config_mod.load_from_env()
    repo = InMemoryAlarmRepo()
    minio = _RecordingMinio()
    worker = _make_worker(fake_client, cfg, repo, minio)

    fake_client.xadd(cfg.streams.alarm_raw, _alarm_fields())
    pubsub = fake_client.pubsub()
    pubsub.subscribe("ws:alarm")
    pubsub.get_message()  # drop subscribe confirmation

    worker.step()

    stored = repo.list()
    assert len(stored) == 1
    assert stored[0].event_id == "e1"
    assert stored[0].vlm_reason == "person climbing"
    assert stored[0].screenshot_object  # MinIO key recorded on the row

    assert len(minio.puts) == 1
    key, jpeg = minio.puts[0]
    assert key.endswith(".jpg")
    assert jpeg == base64.b64decode(_crop_b64())

    msg = pubsub.get_message(timeout=1)
    assert msg is not None and msg["type"] == "message"
    payload = json.loads(msg["data"])
    assert payload["event_id"] == "e1"
    assert payload["class"] == "person"
    assert payload["vlm_reason"] == "person climbing"
    assert payload["screenshot_object"] == key

    # entry must be ACK'd (zero pending)
    pend = fake_client.xpending(cfg.streams.alarm_raw, cfg.streams.group_saver)
    assert pend["pending"] == 0


def test_duplicate_event_id_is_deduped_and_acked(fake_client):
    cfg = config_mod.load_from_env()
    repo = InMemoryAlarmRepo()
    minio = _RecordingMinio()
    worker = _make_worker(fake_client, cfg, repo, minio)

    fake_client.xadd(cfg.streams.alarm_raw, _alarm_fields(event_id="dup"))
    fake_client.xadd(cfg.streams.alarm_raw, _alarm_fields(event_id="dup"))

    worker.step()

    assert len(repo.list()) == 1  # second was deduped
    assert len(minio.puts) == 1
    pend = fake_client.xpending(cfg.streams.alarm_raw, cfg.streams.group_saver)
    assert pend["pending"] == 0


def test_durable_dedup_replay_still_pushes_when_redis_gate_absent(fake_client):
    """Crash-after-persist-before-push replay: the row already exists (repo
    returns None) and the Redis gate was never set. The push MUST still fire so
    the realtime alarm is not lost (at-least-once; FE dedups on event_id)."""
    cfg = config_mod.load_from_env()
    repo = InMemoryAlarmRepo()
    minio = _RecordingMinio()
    # simulate a prior attempt that persisted the row but never set the gate/pushed
    repo.create(Alarm(event_id="e1"))
    worker = _make_worker(fake_client, cfg, repo, minio)

    fake_client.xadd(cfg.streams.alarm_raw, _alarm_fields(event_id="e1"))
    pubsub = fake_client.pubsub()
    pubsub.subscribe("ws:alarm")
    pubsub.get_message()

    worker.step()

    assert len(repo.list()) == 1  # no duplicate row
    msg = pubsub.get_message(timeout=1)
    assert msg is not None and msg["type"] == "message"  # push still delivered
    assert json.loads(msg["data"])["event_id"] == "e1"
    pend = fake_client.xpending(cfg.streams.alarm_raw, cfg.streams.group_saver)
    assert pend["pending"] == 0


def test_redis_gate_hit_skips_push_and_acks(fake_client):
    """When the Redis gate key already exists the entry is a confirmed-complete
    duplicate: no push, no new row, but still ACK'd."""
    cfg = config_mod.load_from_env()
    repo = InMemoryAlarmRepo()
    minio = _RecordingMinio()
    worker = _make_worker(fake_client, cfg, repo, minio)

    fake_client.set("dedup:event:gated", "1")
    fake_client.xadd(cfg.streams.alarm_raw, _alarm_fields(event_id="gated"))
    pubsub = fake_client.pubsub()
    pubsub.subscribe("ws:alarm")
    pubsub.get_message()

    worker.step()

    assert repo.list() == []
    assert minio.puts == []
    assert pubsub.get_message(timeout=0.2) is None
    pend = fake_client.xpending(cfg.streams.alarm_raw, cfg.streams.group_saver)
    assert pend["pending"] == 0


def test_malformed_crop_does_not_wedge_entry(fake_client):
    """A non-base64 crop must not raise and strand the entry pending forever."""
    cfg = config_mod.load_from_env()
    repo = InMemoryAlarmRepo()
    minio = _RecordingMinio()
    worker = _make_worker(fake_client, cfg, repo, minio)

    fake_client.xadd(
        cfg.streams.alarm_raw, _alarm_fields(event_id="bad", crop_jpeg_b64="!!!not-base64!!!")
    )
    worker.step()

    stored = repo.list()
    assert len(stored) == 1
    assert stored[0].screenshot_object == ""  # upload skipped
    assert minio.puts == []
    pend = fake_client.xpending(cfg.streams.alarm_raw, cfg.streams.group_saver)
    assert pend["pending"] == 0

