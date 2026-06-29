"""Task API routes."""

from __future__ import annotations

from abc import ABC, abstractmethod

from dataclasses import asdict
import json
import os
from typing import Any

from flask import Blueprint, jsonify, request

from app.api.auth import current_business_line
from app.api.models import Source, Task
from app.api.repository import SourceRepo, TaskRepo


def _error(message: str, status: int = 422):
    return jsonify({"error": message}), status


def _preview_url(task_id: str) -> str:
    base_url = os.environ.get("MEDIAMTX_HLS_BASE_URL", "/hls")
    return f"{base_url.rstrip('/')}/{task_id}/index.m3u8"


def _task_json(task: Task) -> dict[str, Any]:
    data = asdict(task)
    if task.status == "running":
        data["preview_url"] = _preview_url(task.id)
    return data


def _task_from_payload(data: dict[str, Any]) -> tuple[Task | None, str | None]:
    source_id = data.get("source_id")
    algorithm_id = data.get("algorithm_id")
    if not isinstance(source_id, str) or not source_id.strip():
        return None, "source_id is required"
    if not isinstance(algorithm_id, str) or not algorithm_id.strip():
        return None, "algorithm_id is required"
    if algorithm_id != "small_crop":
        return None, "algorithm_id must be small_crop"
    confidence = data.get("confidence", 0.5)
    if not isinstance(confidence, int | float) or confidence < 0 or confidence > 1:
        return None, "confidence must be between 0 and 1"
    roi = data.get("roi", "")
    prompt = data.get("prompt", "")
    if roi is None:
        roi = ""
    if prompt is None:
        prompt = ""
    if isinstance(roi, list | dict):
        roi = json.dumps(roi)
    if not isinstance(roi, str):
        return None, "roi must be string or structured JSON"
    if not isinstance(prompt, str):
        return None, "prompt must be string"
    return Task(
        source_id=source_id.strip(),
        algorithm_id=algorithm_id.strip(),
        roi=roi,
        prompt=prompt,
        confidence=float(confidence),
    ), None


class ConfigPublisher(ABC):
    """Publishes task runtime config so Producer/Consumer/Saver can read it."""

    @abstractmethod
    def publish_started(self, task: Task, source: Source) -> None: ...

    @abstractmethod
    def publish_stopped(self, task: Task) -> None: ...


class RedisConfigPublisher(ConfigPublisher):
    """Writes task config to Redis on start, removes on stop."""

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    def publish_started(self, task: Task, source: Source) -> None:
        with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(f"task:{task.id}", _config_value(task, source))
            pipe.sadd("tasks:active", task.id)
            pipe.execute()

    def publish_stopped(self, task: Task) -> None:
        with self._redis.pipeline(transaction=True) as pipe:
            pipe.delete(f"task:{task.id}")
            pipe.srem("tasks:active", task.id)
            pipe.execute()


def _config_value(task: Task, source: Source) -> str:
    return json.dumps({
        "task_id": task.id,
        "source_id": source.id,
        "source_name": source.name,
        "source_address": source.address,
        "source_protocol": source.protocol,
        "algorithm_id": task.algorithm_id,
        "roi": task.roi,
        "prompt": task.prompt,
        "confidence": task.confidence,
        "business_line": task.business_line,
    })


def make_tasks_blueprint(
    task_repo: TaskRepo,
    source_repo: SourceRepo,
    config_publisher: ConfigPublisher | None = None,
) -> Blueprint:
    bp = Blueprint("tasks", __name__)

    @bp.post("/tasks")
    def create_task():
        task, err = _task_from_payload(request.get_json(silent=True) or {})
        if err:
            return _error(err)
        assert task is not None
        bl = current_business_line()
        if source_repo.get(task.source_id, business_line=bl) is None:
            return _error("source_id does not exist")
        task.business_line = bl
        return jsonify(_task_json(task_repo.create(task))), 201

    @bp.get("/tasks")
    def list_tasks():
        return jsonify([_task_json(t) for t in task_repo.list(business_line=current_business_line())])

    @bp.get("/tasks/<task_id>")
    def get_task(task_id: str):
        task = task_repo.get(task_id, business_line=current_business_line())
        if task is None:
            return _error("task not found", 404)
        return jsonify(_task_json(task))

    @bp.post("/tasks/<task_id>/start")
    def start_task(task_id: str):
        bl = current_business_line()
        task = task_repo.get(task_id, business_line=bl)
        if task is None:
            return _error("task not found", 404)
        source = source_repo.get(task.source_id, business_line=bl)
        if source is None:
            task.status = "error"
            task.error_message = "task source does not exist"
            task_repo.update(task, business_line=bl)
            return _error("task source does not exist", 409)
        if not source.enabled:
            task.status = "error"
            task.error_message = "task source is disabled"
            task_repo.update(task, business_line=bl)
            return _error("task source is disabled", 409)
        try:
            if config_publisher is not None:
                config_publisher.publish_started(task, source)
        except Exception as exc:
            task.status = "error"
            task.error_message = str(exc)
            task_repo.update(task, business_line=bl)
            return _error("failed to publish runtime config", 500)
        task.status = "running"
        task.error_message = ""
        task_repo.update(task, business_line=bl)
        return jsonify(_task_json(task))

    @bp.post("/tasks/<task_id>/stop")
    def stop_task(task_id: str):
        bl = current_business_line()
        task = task_repo.get(task_id, business_line=bl)
        if task is None:
            return _error("task not found", 404)
        task.status = "stopped"
        task_repo.update(task, business_line=bl)
        if config_publisher is not None:
            config_publisher.publish_stopped(task)
        return jsonify(_task_json(task))

    @bp.get("/tasks/<task_id>/status")
    def task_status(task_id: str):
        task = task_repo.get(task_id, business_line=current_business_line())
        if task is None:
            return _error("task not found", 404)
        return jsonify(
            {
                "id": task.id,
                "status": task.status,
                "error_message": task.error_message,
                **({"preview_url": _preview_url(task.id)} if task.status == "running" else {}),
            }
        )

    return bp
