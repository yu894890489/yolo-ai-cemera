"""Integration-ish test for the Consumer worker against fakeredis.

Contract under test:
  1. Producer XADDs a frame.
  2. Consumer reads the frame, runs the stub detector, emits alarm:raw.
  3. The frame entry is ACK'd.
  4. If we re-run the step without new frames, no duplicate alarm appears.
"""

from __future__ import annotations

import pytest

from app.common import config as config_mod
from app.workers import consumer as consumer_mod

fakeredis = pytest.importorskip("fakeredis")


@pytest.fixture(autouse=True)
def _fresh_config(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    yield
    monkeypatch.setattr(config_mod, "_cached", None)


@pytest.fixture
def fake_client(monkeypatch):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)

    monkeypatch.setattr(
        "app.workers.consumer.make_client",
        lambda cfg: client,
    )
    return client


def test_consumer_processes_frame_emits_alarm_and_acks(fake_client):
    cfg = config_mod.get_config()
    frame_stream = f"{cfg.streams.frame_prefix}demo"

    worker = consumer_mod.ConsumerWorker()
    worker.client = fake_client
    worker.detector = consumer_mod._StubDetector()

    fake_client.xgroup_create(name=frame_stream, groupname=cfg.streams.group_consumer, id="0", mkstream=True)
    worker._known_streams = {frame_stream}
    worker._last_scan = 1e9  # skip scan in this step

    fake_client.xadd(
        frame_stream,
        {"task_id": "demo", "seq": "1", "ts_ms": "0", "frame_jpeg_b64": ""},
    )

    worker.step()

    alarms = fake_client.xrange(cfg.streams.alarm_raw)
    assert len(alarms) == 1
    _, fields = alarms[0]
    assert fields["task_id"] == "demo"
    assert fields["rule_id"] == "demo"

    pending = fake_client.xpending(frame_stream, cfg.streams.group_consumer)
    pending_count = pending["pending"] if isinstance(pending, dict) else (pending[0] if pending else 0)
    assert int(pending_count) == 0

    worker.step()
    alarms_again = fake_client.xrange(cfg.streams.alarm_raw)
    assert len(alarms_again) == 1
