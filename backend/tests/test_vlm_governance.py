from __future__ import annotations

import logging

import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.common import config as config_mod  # noqa: E402
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


def test_reload_config_applies_runtime_task_settings_and_versions(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    overlays = [
        {
            "task.confidence": "0.42",
            "task.roi": "10,20,30,40",
            "task.prompt": "count people",
            "task.vlm_enabled": "true",
            "vlm.queue_high_watermark": "17",
            "vlm.queue_timeout_ms": "60000",
            "vlm.disable_thinking": "true",
            "vlm.max_retries": "2",
        },
        {"task.confidence": "0.7", "task.prompt": "new prompt"},
    ]

    monkeypatch.setattr(config_mod, "fetch_mysql_overlay", lambda cfg: overlays.pop(0))
    monkeypatch.setattr(config_mod, "fetch_vlm_endpoints", lambda cfg: [])

    first = config_mod.reload_config()
    second = config_mod.reload_config()

    assert first.version == 1
    assert first.task.confidence == 0.42
    assert first.task.roi == [10, 20, 30, 40]
    assert first.task.prompt == "count people"
    assert first.task.vlm_enabled is True
    assert first.vlm.queue_high_watermark == 17
    assert first.vlm.queue_timeout_ms == 60000
    assert first.vlm.disable_thinking is True
    assert first.vlm.max_retries == 2
    assert second.version == 2
    assert second.task.confidence == 0.7
    assert "config reloaded: version=2" in caplog.text
    assert "task.prompt" in caplog.text


def test_reload_config_keeps_active_config_when_runtime_overlay_is_invalid(monkeypatch):
    overlays = [{"task.confidence": "0.55"}, {"task.confidence": "not-a-float"}]
    monkeypatch.setattr(config_mod, "fetch_mysql_overlay", lambda cfg: overlays.pop(0))
    monkeypatch.setattr(config_mod, "fetch_vlm_endpoints", lambda cfg: [])

    active = config_mod.reload_config()
    after_failure = config_mod.reload_config()

    assert after_failure is active
    assert config_mod.get_config().task.confidence == 0.55
    assert config_mod.get_config().version == 1


def test_vlm_client_retries_primary_then_fails_over_to_backup_without_thinking():
    calls: list[tuple[str, dict]] = []

    def transport(endpoint: VLMEndpoint, payload: dict, timeout_s: float) -> dict:  # noqa: ARG001
        calls.append((endpoint.provider, payload))
        if endpoint.provider == "qwen-vl-max":
            raise VLMRequestError("rate_limited")
        return {"summary": "person near gate"}

    state = VLMRuntimeState()
    client = VLMClient(
        endpoints=[
            VLMEndpoint("qwen-vl-max", "https://qwen.example/vl", True, 10, 1.0, 512),
            VLMEndpoint("glm-4v", "https://glm.example/vl", True, 20, 1.0, 256),
        ],
        transport=transport,
        state=state,
        max_retries=1,
        backoff_base_s=0,
        disable_thinking=True,
    )

    result = client.analyze("frame", prompt="describe", crop={"bbox": [0, 0, 1, 1]})

    assert result == {"summary": "person near gate"}
    assert [provider for provider, _ in calls] == ["qwen-vl-max", "qwen-vl-max", "glm-4v"]
    assert calls[-1][1]["thinking"] is False
    assert state.active_provider == "glm-4v"
    assert state.last_error == "qwen-vl-max: rate_limited"


def test_consumer_degrades_to_small_only_when_vlm_queue_waterline_is_high(fake_client, monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.task.vlm_enabled = True
    cfg.vlm.queue_high_watermark = 0
    monkeypatch.setattr(config_mod, "get_config", lambda: cfg)

    frame_stream = f"{cfg.streams.frame_prefix}demo"
    worker = consumer_mod.ConsumerWorker()
    worker.client = fake_client
    worker.detector = consumer_mod._StubDetector()
    worker.cfg = cfg
    worker._known_streams = {frame_stream}
    worker._last_scan = 1e9

    fake_client.xgroup_create(name=frame_stream, groupname=cfg.streams.group_consumer, id="0", mkstream=True)
    fake_client.xadd(frame_stream, {"task_id": "demo", "seq": "1", "ts_ms": "0", "frame_jpeg_b64": "frame"})

    worker.step()

    _, alarm = fake_client.xrange(cfg.streams.alarm_raw)[0]
    assert alarm["mode"] == "small_only"
    assert alarm["vlm_status"] == "skipped"
    assert alarm["vlm_error"] == "queue_high_watermark"
