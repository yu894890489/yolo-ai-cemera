"""Integration: Flask serves frontend page shells (BE-M1-D / YU-56)."""

from __future__ import annotations

import app.api.web as web_mod
from app.api import create_app


def _make_app(monkeypatch):
    monkeypatch.setattr("app.api.make_client", lambda cfg: None)
    monkeypatch.setattr("threading.Thread.start", lambda self: None)
    return create_app()


def test_pages_503_when_frontend_not_built(monkeypatch):
    monkeypatch.setattr(web_mod, "_load_manifest", lambda root: None)
    app = _make_app(monkeypatch)
    resp = app.test_client().get("/")
    assert resp.status_code == 503


def test_page_renders_when_manifest_present(monkeypatch):
    manifest = {
        "entries/task-create.ts": {"file": "assets/task-create.deadbeef.js", "isEntry": True},
    }
    monkeypatch.setattr(web_mod, "_load_manifest", lambda root: manifest)
    monkeypatch.setenv("FRONTEND_MINIO_BASE", "http://192.168.10.83:19000")
    app = _make_app(monkeypatch)
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    html = resp.get_data(as_text=True)
    assert "assets/task-create.deadbeef.js" in html
    assert '<meta name="minio-base" content="http://192.168.10.83:19000">' in html


def test_alarms_route_uses_alarm_list_entry(monkeypatch):
    manifest = {"entries/alarm-list.ts": {"file": "assets/alarm-list.cafe.js", "isEntry": True}}
    monkeypatch.setattr(web_mod, "_load_manifest", lambda root: manifest)
    app = _make_app(monkeypatch)
    resp = app.test_client().get("/alarms")
    assert resp.status_code == 200
    assert "assets/alarm-list.cafe.js" in resp.get_data(as_text=True)
