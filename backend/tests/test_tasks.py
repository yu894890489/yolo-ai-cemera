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

    def test_rejects_missing_source_id(self, client):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({"algorithm_id": "small_crop"}),
            content_type="application/json",
        )
        assert resp.status_code == 422

    def test_rejects_nonexistent_source(self, client):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": "nosrc123", "algorithm_id": "small_crop"}),
            content_type="application/json",
        )

        assert resp.status_code == 422

    def test_accepts_structured_roi(self, client, created_source):
        payload = {
            "source_id": created_source["id"],
            "algorithm_id": "small_crop",
            "roi": [[100, 100], [200, 100], [200, 200], [100, 200]],
        }

        resp = client.post("/api/tasks", data=json.dumps(payload), content_type="application/json")

        assert resp.status_code == 201
        assert json.loads(resp.get_json()["roi"]) == payload["roi"]

    def test_rejects_invalid_structured_roi(self, client, created_source):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({
                "source_id": created_source["id"],
                "algorithm_id": "small_crop",
                "roi": [100, 100],
            }),
            content_type="application/json",
        )

        assert resp.status_code == 422

    def test_rejects_empty_structured_roi(self, client, created_source):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({
                "source_id": created_source["id"],
                "algorithm_id": "small_crop",
                "roi": [],
            }),
            content_type="application/json",
        )

        assert resp.status_code == 422

    def test_rejects_boolean_roi_coordinates(self, client, created_source):
        resp = client.post(
            "/api/tasks",
            data=json.dumps({
                "source_id": created_source["id"],
                "algorithm_id": "small_crop",
                "roi": [[True, False], [1, 2], [3, 4]],
            }),
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

    def test_start_returns_configured_preview_url(self, source_repo, task_repo, created_source):
        from flask import Flask

        app = Flask(__name__)
        app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
        app.register_blueprint(
            make_tasks_blueprint(
                task_repo,
                source_repo,
                preview_base_url="http://mediamtx.local:8888",
            ),
            url_prefix="/api",
        )
        app.config["TESTING"] = True
        with app.test_client() as c:
            source = c.post(
                "/api/sources",
                data=json.dumps({
                    "name": "Cam 2",
                    "protocol": "rtsp",
                    "address": "rtsp://10.0.0.2/stream",
                }),
                content_type="application/json",
            ).get_json()
            task = c.post(
                "/api/tasks",
                data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
                content_type="application/json",
            ).get_json()

            resp = c.post(f"/api/tasks/{task['id']}/start")

            assert resp.status_code == 200
            assert resp.get_json()["preview_url"] == (
                f"http://mediamtx.local:8888/hls/{task['id']}/index.m3u8"
            )

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

    def test_start_nonexistent_returns_404(self, client):
        resp = client.post("/api/tasks/nonexistent/start")
        assert resp.status_code == 404

    def test_start_returns_409_when_source_was_deleted(self, client, created_source):
        created = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()
        client.delete(f"/api/sources/{created_source['id']}")

        resp = client.post(f"/api/tasks/{created['id']}/start")

        assert resp.status_code == 409
        status = client.get(f"/api/tasks/{created['id']}/status").get_json()
        assert status["status"] == "error"
        assert status["error_message"] == "source not found"

    def test_start_returns_409_when_source_is_disabled(self, client, created_source):
        created = client.post(
            "/api/tasks",
            data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()
        client.put(
            f"/api/sources/{created_source['id']}",
            data=json.dumps({
                "name": created_source["name"],
                "protocol": created_source["protocol"],
                "address": created_source["address"],
                "enabled": False,
            }),
            content_type="application/json",
        )

        resp = client.post(f"/api/tasks/{created['id']}/start")

        assert resp.status_code == 409
        status = client.get(f"/api/tasks/{created['id']}/status").get_json()
        assert status["status"] == "error"
        assert status["error_message"] == "source disabled"