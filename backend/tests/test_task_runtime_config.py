"""Tests for task runtime configuration publishing."""

from __future__ import annotations

import json

import pytest

from app.api.repository import InMemorySourceRepo, InMemoryTaskRepo
from app.api.sources import make_sources_blueprint
from app.api.tasks import RedisConfigPublisher, make_tasks_blueprint


class RecordingPublisher:
    def __init__(self) -> None:
        self.started = []
        self.stopped = []

    def publish_started(self, task, source):
        self.started.append((task, source))

    def publish_stopped(self, task):
        self.stopped.append(task)


class FakeRedis:
    def __init__(self) -> None:
        self.values = {}
        self.sets = {}
        self.executed_pipelines = []
        self.pipeline_transactions = []

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    def srem(self, key, value):
        self.sets.setdefault(key, set()).discard(value)

    def pipeline(self, transaction=True):
        self.pipeline_transactions.append(transaction)
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis) -> None:
        self.redis = redis
        self.commands = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    def sadd(self, key, value):
        self.commands.append(("sadd", key, value))
        return self

    def srem(self, key, value):
        self.commands.append(("srem", key, value))
        return self

    def execute(self):
        for command in self.commands:
            if command[0] == "set":
                self.redis.set(command[1], command[2])
            elif command[0] == "delete":
                self.redis.delete(command[1])
            elif command[0] == "sadd":
                self.redis.sadd(command[1], command[2])
            elif command[0] == "srem":
                self.redis.srem(command[1], command[2])
        self.redis.executed_pipelines.append(list(self.commands))


class FailingPublisher:
    def publish_started(self, task, source):
        raise RuntimeError("redis unavailable")

    def publish_stopped(self, task):
        pass


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


def test_redis_publisher_tracks_active_task_set():
    redis = FakeRedis()
    publisher = RedisConfigPublisher(redis)
    task = type("Task", (), {"id": "task1", "algorithm_id": "small_crop", "roi": "", "prompt": "", "confidence": 0.5, "business_line": "phase1"})()
    source = type("Source", (), {"id": "src1", "name": "Cam 1", "address": "rtsp://x", "protocol": "rtsp"})()

    publisher.publish_started(task, source)

    assert "task1" in redis.sets["tasks:active"]
    assert "task:task1" in redis.values
    assert redis.pipeline_transactions == [True]
    assert redis.executed_pipelines[0][0][0] == "set"
    assert redis.executed_pipelines[0][1] == ("sadd", "tasks:active", "task1")

    publisher.publish_stopped(task)

    assert "task1" not in redis.sets["tasks:active"]
    assert "task:task1" not in redis.values
    assert redis.pipeline_transactions == [True, True]
    assert redis.executed_pipelines[1] == [("delete", "task:task1"), ("srem", "tasks:active", "task1")]


def test_start_returns_error_when_task_source_was_deleted(client, created_source):
    task = client.post(
        "/api/tasks",
        data=json.dumps({"source_id": created_source["id"], "algorithm_id": "small_crop"}),
        content_type="application/json",
    ).get_json()
    client.delete(f"/api/sources/{created_source['id']}")

    resp = client.post(f"/api/tasks/{task['id']}/start")

    assert resp.status_code == 409
    assert resp.get_json()["error"] == "task source does not exist"
    status = client.get(f"/api/tasks/{task['id']}/status").get_json()
    assert status["status"] == "error"
    assert status["error_message"] == "task source does not exist"


def test_start_marks_task_error_when_runtime_config_publish_fails(source_repo, task_repo):
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
            data=json.dumps({"name": "Cam 1", "protocol": "rtsp", "address": "rtsp://10.0.0.1/stream"}),
            content_type="application/json",
        ).get_json()
        task = c.post(
            "/api/tasks",
            data=json.dumps({"source_id": source["id"], "algorithm_id": "small_crop"}),
            content_type="application/json",
        ).get_json()

        resp = c.post(f"/api/tasks/{task['id']}/start")

        assert resp.status_code == 500
        assert resp.get_json()["error"] == "failed to publish runtime config"
        status = c.get(f"/api/tasks/{task['id']}/status").get_json()
        assert status["status"] == "error"
        assert status["error_message"] == "redis unavailable"
