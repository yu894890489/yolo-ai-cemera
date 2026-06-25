"""Tests for app.common.config."""

from __future__ import annotations

import pytest

from app.common import config as config_mod


@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch):
    monkeypatch.setattr(config_mod, "_cached", None)
    yield
    monkeypatch.setattr(config_mod, "_cached", None)


def test_load_from_env_uses_defaults_when_unset(monkeypatch):
    for key in [
        "REDIS_HOST",
        "REDIS_PORT",
        "PRODUCER_METRICS_PORT",
        "CONSUMER_METRICS_PORT",
        "SAVER_METRICS_PORT",
    ]:
        monkeypatch.delenv(key, raising=False)

    cfg = config_mod.load_from_env()
    assert cfg.redis.host == "redis"
    assert cfg.redis.port == 6379
    assert cfg.ports.producer == 9101
    assert cfg.ports.consumer == 9102
    assert cfg.ports.saver == 9103


def test_load_from_env_respects_overrides(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis-prod")
    monkeypatch.setenv("REDIS_PORT", "16379")
    monkeypatch.setenv("PRODUCER_METRICS_PORT", "19101")
    monkeypatch.setenv("MINIO_SECURE", "true")

    cfg = config_mod.load_from_env()
    assert cfg.redis.host == "redis-prod"
    assert cfg.redis.port == 16379
    assert cfg.ports.producer == 19101
    assert cfg.minio.secure is True


def test_load_from_env_int_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("REDIS_PORT", "not-an-int")
    cfg = config_mod.load_from_env()
    assert cfg.redis.port == 6379


def test_overlay_empty_when_pymysql_unavailable(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "pymysql":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    cfg = config_mod.load_from_env()
    overlay = config_mod.fetch_mysql_overlay(cfg)
    assert overlay == {}


def test_reload_config_replaces_cache(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "first")
    first = config_mod.reload_config()
    assert first.redis.host == "first"

    monkeypatch.setenv("REDIS_HOST", "second")
    second = config_mod.reload_config()
    assert second.redis.host == "second"

    assert config_mod.get_config().redis.host == "second"


def test_load_from_env_respects_mediamtx_hls_base_url(monkeypatch):
    monkeypatch.setenv("MEDIAMTX_HLS_BASE_URL", "http://mediamtx.local:8888")

    cfg = config_mod.load_from_env()

    assert cfg.mediamtx.hls_base_url == "http://mediamtx.local:8888"
