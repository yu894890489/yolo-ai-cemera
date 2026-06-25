"""Tests for producer runtime task config consumption."""

from __future__ import annotations

import json

import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.common import config as config_mod  # noqa: E402
from app.workers import producer as producer_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_config(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    yield
    monkeypatch.setattr(config_mod, "_cached", None)


@pytest.fixture
def fake_client(monkeypatch):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    monkeypatch.setattr("app.workers.producer.make_client", lambda cfg: client)
    return client


def test_producer_loads_started_task_config_from_redis(fake_client):
    task_config = {
        "task_id": "task1",
        "source_id": "src1",
        "source_name": "Cam 1",
        "source_address": "rtsp://10.0.0.1/stream",
        "source_protocol": "rtsp",
        "algorithm_id": "small_crop",
        "roi": "",
        "prompt": "",
        "confidence": 0.5,
    }
    fake_client.sadd("tasks:active", "task1")
    fake_client.set("task:task1", json.dumps(task_config))
    worker = producer_mod.ProducerWorker()
    worker.client = fake_client

    worker.step()

    entries = fake_client.xrange("frame:task1")
    assert len(entries) == 1
    _, fields = entries[0]
    assert fields["task_id"] == "task1"


def test_producer_stops_writing_task_frames_when_runtime_config_is_removed(fake_client):
    task_config = {
        "task_id": "task1",
        "source_id": "src1",
        "source_name": "Cam 1",
        "source_address": "rtsp://10.0.0.1/stream",
        "source_protocol": "rtsp",
        "algorithm_id": "small_crop",
        "roi": "",
        "prompt": "",
        "confidence": 0.5,
    }
    fake_client.sadd("tasks:active", "task1")
    fake_client.set("task:task1", json.dumps(task_config))
    worker = producer_mod.ProducerWorker()
    worker.client = fake_client
    worker.step()
    fake_client.srem("tasks:active", "task1")
    fake_client.delete("task:task1")

    worker.step()

    assert len(fake_client.xrange("frame:task1")) == 1


def test_producer_reuses_runtime_source_sequence(fake_client):
    task_config = {
        "task_id": "task1",
        "source_id": "src1",
        "source_name": "Cam 1",
        "source_address": "rtsp://10.0.0.1/stream",
        "source_protocol": "rtsp",
        "algorithm_id": "small_crop",
        "roi": "",
        "prompt": "",
        "confidence": 0.5,
    }
    fake_client.sadd("tasks:active", "task1")
    fake_client.set("task:task1", json.dumps(task_config))
    worker = producer_mod.ProducerWorker()
    worker.client = fake_client

    worker.step()
    worker.step()

    entries = fake_client.xrange("frame:task1")
    assert [fields["seq"] for _, fields in entries] == ["1", "2"]
