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
        self.stopped = []

    def publish_started(self, task, source):
        self.started.append((task, source))

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
