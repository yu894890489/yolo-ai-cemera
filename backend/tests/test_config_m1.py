"""Tests for new M1 config overlay keys (BE-M1-B)."""

from __future__ import annotations

import pytest

from app.common import config as config_mod


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    monkeypatch.setattr(config_mod, "_version", 0)
    yield
    monkeypatch.setattr(config_mod, "_cached", None)
    monkeypatch.setattr(config_mod, "_version", 0)


def test_overlay_parses_task_classes_csv(monkeypatch):
    monkeypatch.setattr(config_mod, "fetch_mysql_overlay", lambda cfg: {"task.classes": "person,car"})
    monkeypatch.setattr(config_mod, "fetch_vlm_endpoints", lambda cfg: [])
    cfg = config_mod.reload_config()
    assert cfg.task.classes == ["person", "car"]


def test_overlay_parses_task_classes_list(monkeypatch):
    monkeypatch.setattr(config_mod, "fetch_mysql_overlay", lambda cfg: {"task.classes": ["dog"]})
    monkeypatch.setattr(config_mod, "fetch_vlm_endpoints", lambda cfg: [])
    cfg = config_mod.reload_config()
    assert cfg.task.classes == ["dog"]


def test_overlay_parses_vlm_dedup_window(monkeypatch):
    monkeypatch.setattr(config_mod, "fetch_mysql_overlay", lambda cfg: {"vlm.dedup_window_s": "5"})
    monkeypatch.setattr(config_mod, "fetch_vlm_endpoints", lambda cfg: [])
    cfg = config_mod.reload_config()
    assert cfg.vlm.dedup_window_s == 5


def test_default_classes_is_none_and_dedup_window_is_three():
    cfg = config_mod.load_from_env()
    assert cfg.task.classes is None
    assert cfg.vlm.dedup_window_s == 3
