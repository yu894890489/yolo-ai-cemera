"""Tests for video source management API."""

from __future__ import annotations

import json

import pytest

from app.api.models import Source
from app.api.repository import InMemorySourceRepo, MySQLSourceRepo, MySQLTaskRepo
from app.api.sources import make_sources_blueprint


@pytest.fixture
def repo():
    return InMemorySourceRepo()


@pytest.fixture
def client(repo):
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(make_sources_blueprint(repo), url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_payload():
    return {"name": "Cam 1", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream", "enabled": True, "note": "entrance"}


class TestCreateSource:
    def test_creates_source_and_returns_201(self, client, sample_payload):
        resp = client.post(
            "/api/sources", data=json.dumps(sample_payload), content_type="application/json"
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Cam 1"
        assert data["protocol"] == "rtsp"
        assert "id" in data

    def test_rejects_missing_name(self, client):
        resp = client.post(
            "/api/sources",
            data=json.dumps({"protocol": "rtsp", "address": "rtsp://example/stream"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_rejects_empty_name(self, client):
        resp = client.post(
            "/api/sources",
            data=json.dumps({"name": "", "protocol": "rtsp", "address": "rtsp://example/stream"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_rejects_missing_protocol(self, client):
        resp = client.post(
            "/api/sources",
            data=json.dumps({"name": "Cam 1", "address": "rtsp://example/stream"}),
            content_type="application/json",
        )
        assert resp.status_code == 422


class TestListSources:
    def test_list_returns_empty_when_none(self, client):
        resp = client.get("/api/sources")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_returns_all_sources(self, client, sample_payload):
        client.post("/api/sources", data=json.dumps(sample_payload), content_type="application/json")
        client.post(
            "/api/sources",
            data=json.dumps({"name": "Cam 2", "protocol": "rtsp", "address": "rtsp://10.0.0.2/stream"}),
            content_type="application/json",
        )
        resp = client.get("/api/sources")
        assert len(resp.get_json()) == 2


class TestGetSource:
    def test_get_returns_source(self, client, sample_payload):
        created = client.post(
            "/api/sources", data=json.dumps(sample_payload), content_type="application/json"
        ).get_json()
        resp = client.get(f"/api/sources/{created['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Cam 1"

    def test_get_returns_404_for_missing(self, client):
        resp = client.get("/api/sources/nonexistent")
        assert resp.status_code == 404


class TestUpdateSource:
    def test_update_returns_updated(self, client, sample_payload):
        created = client.post(
            "/api/sources", data=json.dumps(sample_payload), content_type="application/json"
        ).get_json()
        resp = client.put(
            f"/api/sources/{created['id']}",
            data=json.dumps({"name": "Cam 1 Updated", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Cam 1 Updated"

    def test_update_returns_404_for_missing(self, client):
        resp = client.put(
            "/api/sources/nonexistent",
            data=json.dumps({"name": "Any", "protocol": "rtsp", "address": "rtsp://x/stream"}),
            content_type="application/json",
        )
        assert resp.status_code == 404


class TestDeleteSource:
    def test_delete_returns_204(self, client, sample_payload):
        created = client.post(
            "/api/sources", data=json.dumps(sample_payload), content_type="application/json"
        ).get_json()
        resp = client.delete(f"/api/sources/{created['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/sources/{created['id']}").status_code == 404

    def test_delete_returns_404_for_missing(self, client):
        resp = client.delete("/api/sources/nonexistent")
        assert resp.status_code == 404


class TestMySQLSourceRepo:
    def test_get_converts_enabled_to_boolean(self):
        repo = MySQLSourceRepo({})
        repo._connect = lambda: _FakeConnection([("src1", "Cam 1", "rtsp", "rtsp://x", 1, "", "created", "updated")])

        source = repo.get("src1")

        assert source == Source("src1", "Cam 1", "rtsp", "rtsp://x", True, "", "created", "updated")
        assert isinstance(source.enabled, bool)

    def test_list_converts_enabled_to_boolean(self):
        repo = MySQLSourceRepo({})
        repo._connect = lambda: _FakeConnection([("src1", "Cam 1", "rtsp", "rtsp://x", 0, "", "created", "updated")])

        sources = repo.list()

        assert sources[0].enabled is False

    def test_connect_reconnects_stale_connection(self):
        repo = MySQLSourceRepo({})
        conn = _FakeConnection([])
        repo._conn = conn

        assert repo._connect() is conn

        assert conn.ping_calls == [(True,)]


class TestMySQLTaskRepo:
    def test_connect_reconnects_stale_connection(self):
        repo = MySQLTaskRepo({})
        conn = _FakeConnection([])
        repo._conn = conn

        assert repo._connect() is conn

        assert conn.ping_calls == [(True,)]


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.ping_calls = []

    def ping(self, reconnect=False):
        self.ping_calls.append((reconnect,))

    def cursor(self):
        return _FakeCursor(self.rows)


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows
