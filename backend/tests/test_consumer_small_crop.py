"""Consumer small_crop path: filtering, crop, VLM judgment, dedup key (BE-M1-B)."""

from __future__ import annotations

import numpy as np
import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.common import config as config_mod  # noqa: E402
from app.common import imaging  # noqa: E402
from app.common.vlm import VLMClient, VLMEndpoint, VLMRequestError, VLMRuntimeState  # noqa: E402
from app.workers import consumer as consumer_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    monkeypatch.setattr(config_mod, "_version", 0)
    yield
    monkeypatch.setattr(config_mod, "_cached", None)
    monkeypatch.setattr(config_mod, "_version", 0)


@pytest.fixture
def fake_client():
    server = fakeredis.FakeServer()
    return fakeredis.FakeStrictRedis(server=server, decode_responses=True)


class _FixedDetector:
    def __init__(self, detections):
        self._detections = detections

    def detect(self, frame_b64):  # noqa: ARG002
        return list(self._detections)


def _real_frame_b64(w=100, h=100, color=120):
    return imaging.encode_jpeg_b64(np.full((h, w, 3), color, dtype=np.uint8))


def _make_worker(fake_client, cfg, detections):
    monkey_cfg = cfg
    worker = consumer_mod.ConsumerWorker()
    worker.client = fake_client
    worker.cfg = monkey_cfg
    worker.detector = _FixedDetector(detections)
    frame_stream = f"{cfg.streams.frame_prefix}demo"
    worker._known_streams = {frame_stream}
    worker._last_scan = 1e9
    fake_client.xgroup_create(
        name=frame_stream, groupname=cfg.streams.group_consumer, id="0", mkstream=True
    )
    return worker, frame_stream


def _push_frame(fake_client, frame_stream, frame_b64):
    fake_client.xadd(
        frame_stream, {"task_id": "demo", "seq": "1", "ts_ms": "1000", "frame_jpeg_b64": frame_b64}
    )


def test_detection_below_confidence_threshold_emits_no_alarm(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.confidence = 0.8
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)
    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "person", "score": 0.3, "bbox": [0, 0, 10, 10]}]
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()
    assert fake_client.xrange(cfg.streams.alarm_raw) == []


def test_class_not_in_target_list_emits_no_alarm(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.classes = ["person"]
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)
    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "car", "score": 0.9, "bbox": [0, 0, 10, 10]}]
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()
    assert fake_client.xrange(cfg.streams.alarm_raw) == []


def test_detection_outside_roi_emits_no_alarm(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.roi = [0, 0, 20, 20]
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)
    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "person", "score": 0.9, "bbox": [50, 50, 60, 60]}]
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()
    assert fake_client.xrange(cfg.streams.alarm_raw) == []


def test_vlm_positive_judgment_emits_alarm_with_crop_and_reason(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.vlm_enabled = True
    cfg.task.prompt = "intruder?"
    cfg.vlm.queue_high_watermark = 10_000
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    def transport(endpoint, payload, timeout_s):  # noqa: ARG001
        return {"is_alarm": True, "reason": "person climbing", "confidence": 0.88}

    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "person", "score": 0.9, "bbox": [10, 10, 40, 40]}]
    )
    worker.vlm_state = VLMRuntimeState()
    worker.vlm_client = VLMClient(
        endpoints=[VLMEndpoint("qwen", "http://x", True, 10, 1.0, 256)],
        transport=transport,
        state=worker.vlm_state,
        max_retries=0,
        backoff_base_s=0,
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()

    alarms = fake_client.xrange(cfg.streams.alarm_raw)
    assert len(alarms) == 1
    _, a = alarms[0]
    assert a["mode"] == "vlm"
    assert a["vlm_status"] == "ok"
    assert a["vlm_reason"] == "person climbing"
    assert a["event_id"]
    assert a["crop_jpeg_b64"]
    # crop must decode and be smaller than the source frame
    crop = imaging.decode_jpeg_b64(a["crop_jpeg_b64"])
    assert crop is not None and crop.shape[0] == 30 and crop.shape[1] == 30


def test_vlm_negative_judgment_emits_no_alarm(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.vlm_enabled = True
    cfg.vlm.queue_high_watermark = 10_000
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    def transport(endpoint, payload, timeout_s):  # noqa: ARG001
        return {"is_alarm": False, "reason": "nothing", "confidence": 0.1}

    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "person", "score": 0.9, "bbox": [10, 10, 40, 40]}]
    )
    worker.vlm_state = VLMRuntimeState()
    worker.vlm_client = VLMClient(
        endpoints=[VLMEndpoint("qwen", "http://x", True, 10, 1.0, 256)],
        transport=transport,
        state=worker.vlm_state,
        max_retries=0,
        backoff_base_s=0,
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()
    assert fake_client.xrange(cfg.streams.alarm_raw) == []


def test_vlm_failure_degrades_and_emits_small_only_alarm(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.vlm_enabled = True
    cfg.vlm.queue_high_watermark = 10_000
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    def transport(endpoint, payload, timeout_s):  # noqa: ARG001
        raise VLMRequestError("boom")

    worker, stream = _make_worker(
        fake_client, cfg, [{"class": "person", "score": 0.9, "bbox": [10, 10, 40, 40]}]
    )
    worker.vlm_state = VLMRuntimeState()
    worker.vlm_client = VLMClient(
        endpoints=[VLMEndpoint("qwen", "http://x", True, 10, 1.0, 256)],
        transport=transport,
        state=worker.vlm_state,
        max_retries=0,
        backoff_base_s=0,
    )
    _push_frame(fake_client, stream, _real_frame_b64())
    worker.step()
    alarms = fake_client.xrange(cfg.streams.alarm_raw)
    assert len(alarms) == 1
    _, a = alarms[0]
    assert a["mode"] == "small_only"
    assert a["vlm_status"] == "failed"
