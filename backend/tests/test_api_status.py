from __future__ import annotations

from app.api import create_app
from app.common import config as config_mod
from app.common.vlm import VLMRuntimeState


def test_runtime_status_exposes_config_version_and_vlm_summary(monkeypatch):
    cfg = config_mod.load_from_env()
    cfg.version = 7
    cfg.task.vlm_enabled = True
    cfg.task.prompt = "watch gate"
    cfg.task.roi = [1, 2, 3, 4]
    cfg.task.confidence = 0.66
    state = VLMRuntimeState(
        enabled=True,
        active_provider="glm-4v",
        last_error="qwen-vl-max: timeout",
        last_failure_reason="timeout",
        degraded_mode="small_only",
    )

    monkeypatch.setattr("app.api.get_config", lambda: cfg)
    monkeypatch.setattr("app.api.get_vlm_runtime_state", lambda: state)
    monkeypatch.setattr("app.api.make_client", lambda cfg: None)
    monkeypatch.setattr("threading.Thread.start", lambda self: None)

    app = create_app()
    resp = app.test_client().get("/api/runtime/status")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["config_version"] == 7
    assert body["task"]["vlm_enabled"] is True
    assert body["task"]["prompt"] == "watch gate"
    assert body["task"]["roi"] == [1, 2, 3, 4]
    assert body["task"]["confidence"] == 0.66
    assert body["vlm"]["active_provider"] == "glm-4v"
    assert body["vlm"]["last_error"] == "qwen-vl-max: timeout"
    assert body["vlm"]["degraded_mode"] == "small_only"
