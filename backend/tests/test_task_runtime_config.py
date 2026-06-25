"""Tests for task runtime configuration publishing."""

from __future__ import annotations

import json

import pytest

from app.api.repository import InMemorySourceRepo, InMemoryTaskRepo
from app.api.sources import make_sources_blueprint
from app.api.tasks import make_tasks_blueprint


class RecordingPublisher:
    def __init__(self) -> None:
        self.started = []
        self.started_statuses = []
        self.stopped = []

    def publish_started(self, task, source):
        self.started.append((task, source))
        self.started_statuses.append(task.status)

    def publish_stopped(self, task):
        self.stopped.append(task)


@pytest.fixture
def source_repo():
    return InMemorySourceRepo()


@pytest.fixture
def task_repo():
    return InMemoryTaskRepo()


@pytest.fixture
def publisher():
    return RecordingPublisher()


@pytest.fixture
def client(source_repo, task_repo, publisher):
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    app.register_blueprint(
        make_tasks_blueprint(task_repo, source_repo, config_publisher=publisher),
        url_prefix="/api",
    )
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def created_source(client):
    return client.post(
        "/api/sources",
        data=json.dumps({"name": "Cam 1", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream"}),
        content_type="application/json",
    ).get_json()


def test_start_publishes_runtime_config(client, publisher, created_source):
    task = client.post(
        "/api/tasks",
        data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
        content_type="application/json",
    ).get_json()

    client.post(f"/api/tasks/{task['id']}/start")

    assert len(publisher.started) == 1
    started_task, source = publisher.started[0]
    assert started_task.id == task["id"]
    assert started_task.status == "running"
    assert publisher.started_statuses == ["created"]
    assert source.id == created_source["id"]


def test_stop_publishes_runtime_stop(client, publisher, created_source):
    task = client.post(
        "/api/tasks",
        data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
        content_type="application/json",
    ).get_json()

    client.post(f"/api/tasks/{task['id']}/start")
    client.post(f"/api/tasks/{task['id']}/stop")

    assert len(publisher.stopped) == 1
    assert publisher.stopped[0].id == task["id"]
    assert publisher.stopped[0].status == "stopped"


def test_start_returns_500_when_publish_fails(source_repo, task_repo):
    class FailingPublisher:
        def __init__(self):
            self.started = []
            self.stopped = []

        def publish_started(self, task, source):
            raise RuntimeError("redis connection refused")

        def publish_stopped(self, task):
            self.stopped.append(task)

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    app.register_blueprint(
        make_tasks_blueprint(task_repo, source_repo, config_publisher=FailingPublisher()),
        url_prefix="/api",
    )
    app.config["TESTING"] = True
    with app.test_client() as c:
        source = c.post(
            "/api/sources",
            data=json.dumps({"name": "Cam", "protocol": "rtsp", "address": "rtsp://x/stream"}),
            content_type="application/json",
        ).get_json()
        task = c.post(
            "/api/tasks",
            data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()

        resp = c.post(f"/api/tasks/{task['id']}/start")

        assert resp.status_code == 500
        assert resp.get_json() == {"error": "failed to publish runtime config"}

        status = c.get(f"/api/tasks/{task['id']}/status").get_json()
        assert status["status"] == "error"
        assert status["error_message"] == "failed to publish runtime config"


def test_start_removes_runtime_config_when_mark_running_fails(source_repo):
    class FailingUpdateTaskRepo(InMemoryTaskRepo):
        def update(self, task):
            if task.status == "running":
                task.status = "error"
                task.error_message = "failed to update task status"
                raise RuntimeError("database unavailable")
            return super().update(task)

    publisher = RecordingPublisher()

    from flask import Flask

    app = Flask(__name__)
    task_repo = FailingUpdateTaskRepo()
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    app.register_blueprint(
        make_tasks_blueprint(task_repo, source_repo, config_publisher=publisher),
        url_prefix="/api",
    )
    app.config["TESTING"] = True
    with app.test_client() as c:
        source = c.post(
            "/api/sources",
            data=json.dumps({"name": "Cam", "protocol": "rtsp", "address": "rtsp://x/stream"}),
            content_type="application/json",
        ).get_json()
        task = c.post(
            "/api/tasks",
            data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()

        resp = c.post(f"/api/tasks/{task['id']}/start")

        assert resp.status_code == 500
        assert len(publisher.started) == 1
        assert len(publisher.stopped) == 1

