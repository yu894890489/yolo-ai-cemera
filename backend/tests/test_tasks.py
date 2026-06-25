"""Tests for small_crop task API."""

from __future__ import annotations

import json

import pytest

from app.api.repository import InMemorySourceRepo, InMemoryTaskRepo
from app.api.sources import make_sources_blueprint
from app.api.tasks import make_tasks_blueprint


@pytest.fixture
def source_repo():
    return InMemorySourceRepo()


@pytest.fixture
def task_repo():
    return InMemoryTaskRepo()


@pytest.fixture
def client(source_repo, task_repo):
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    app.register_blueprint(make_tasks_blueprint(task_repo, source_repo), url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def created_source(client):
    resp = client.post(
        "/api/sources",
        data=json.dumps({"name": "Cam 1", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream"}),
        content_type="application/json",
    )
    return resp.get_json()


class TestCreateTask:
    def test_creates_small_crop_task(self, client, created_source):
        """RED: create a small_crop task linked to an existing source."""
        payload = {
            "source_id": created_source["id"],
            "algorithm_id": "small_crop",
            "roi": "[[100,100],[200,100],[200,200],[100,200]]",
            "prompt": "detect person on the crosswalk",
            "confidence": 0.6,
        }
        resp = client.post("/api/tasks", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["algorithm_id"] == "small_crop"
        assert data["source_id"] == created_source["id"]
        assert data["status"] == "created"
        assert data["confidence"] == 0.6
        assert "id" in data

    def test_accepts_structured_roi(self, client, created_source):
        payload = {
            "source_id": created_source["id"],
            "algorithm_id": "small_crop",
            "roi": [[100, 100], [200, 100], [200, 200], [100, 200]],
        }

        resp = client.post("/api/tasks", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 201
        assert json.loads(resp.get_json()["roi"]) == payload["roi"]

    def test_rejects_missing_source_id(self, client):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({"algorithm_id": "small_crop"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_rejects_nonexistent_source(self, client, task_repo):
        """RED: creating a task for a non-existent source should fail."""
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(
            make_tasks_blueprint(task_repo, InMemorySourceRepo()), url_prefix="/api"
        )
        app.config["TESTING"] = True
        with app.test_client() as c:
            resp = c.post(
                "/api/tasks",
                data=json.dumps({"source_id": "nosrc123", "algorithm_id": "small_crop"}),
                content_type="application/json",
            )
            assert resp.status_code == 422


class TestTaskLifecycle:
    def test_start_changes_status_to_running(self, client, created_source):
        created = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()
        resp = client.post(f"/api/tasks/{created['id']}/start")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "running"
        assert "preview_url" in data

    def test_stop_changes_status_to_stopped(self, client, created_source):
        created = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()
        client.post(f"/api/tasks/{created['id']}/start")
        resp = client.post(f"/api/tasks/{created['id']}/stop")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "stopped"

    def test_status_returns_current(self, client, created_source):
        created = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()
        resp = client.get(f"/api/tasks/{created['id']}/status")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "created"

    def test_start_rejects_disabled_source(self, client):
        source = client.post(
            "/api/sources",
            data=json.dumps({"name": "Disabled Cam", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream", "enabled": False}),
            content_type="application/json",
        ).get_json()
        task = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()

        resp = client.post(f"/api/tasks/{task['id']}/start")

        assert resp.status_code == 409
        assert resp.get_json()["error"] == "task source is disabled"
        status = client.get(f"/api/tasks/{task['id']}/status").get_json()
        assert status["status"] == "error"
        assert status["error_message"] == "task source is disabled"

    def test_status_uses_configured_preview_hls_base_url(self, monkeypatch, source_repo, task_repo):
        from flask import Flask

        monkeypatch.setenv("MEDIAMTX_HLS_BASE_URL", "http://stream.example/hls/")
        app = Flask(__name__)
        app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
        app.register_blueprint(make_tasks_blueprint(task_repo, source_repo), url_prefix="/api")
        app.config["TESTING"] = True
        with app.test_client() as c:
            source = c.post(
                "/api/sources",
                data=json.dumps({"name": "Cam 1", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream"}),
                content_type="application/json",
            ).get_json()
            task = c.post(
                "/api/tasks",
                data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
                content_type="application/json",
            ).get_json()
            c.post(f"/api/tasks/{task['id']}/start")

            resp = c.get(f"/api/tasks/{task['id']}/status")

            assert resp.get_json()["preview_url"] == f"http://stream.example/hls/{task['id']}/index.m3u8"

    def test_start_nonexistent_returns_404(self, client):
        resp = client.post("/api/tasks/nonexistent/start")
        assert resp.status_code == 404