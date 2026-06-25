"""Task API routes."""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod

from dataclasses import asdict
from typing import Any

from flask import Blueprint, jsonify, request

from app.api.models import Source, Task
from app.api.repository import SourceRepo, TaskRepo


def _error(message: str, status: int = 422):
    return jsonify({"error": message}), status


def _preview_url(task: Task, preview_base_url: str = "") -> str:
    path = f"/hls/{task.id}/index.m3u8"
    if not preview_base_url:
        return path
    return f"{preview_base_url.rstrip('/')}{path}"


def _task_json(task: Task, preview_base_url: str = "") -> dict[str, Any]:
    data = asdict(task)
    if task.status == "running":
        data["preview_url"] = _preview_url(task, preview_base_url)
    return data


def _roi_coordinate(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _normalize_roi(roi: Any) -> tuple[str, str | None]:
    if roi is None:
        return "", None
    if isinstance(roi, str):
        return roi, None
    if isinstance(roi, list) and len(roi) >= 3 and all(
        isinstance(point, list | tuple)
        and len(point) == 2
        and all(_roi_coordinate(value) for value in point)
        for point in roi
    ):
        return json.dumps(roi), None
    return "", "roi must be string or polygon list of [x, y] points"


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
    roi, roi_err = _normalize_roi(data.get("roi", ""))
    if roi_err:
        return None, roi_err
    prompt = data.get("prompt", "")
    if prompt is None:
        prompt = ""
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
        self._redis.set(f"task:{task.id}", _config_value(task, source))

    def publish_stopped(self, task: Task) -> None:
        self._redis.delete(f"task:{task.id}")


def _config_value(task: Task, source: Source) -> str:
    import json
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
    })


def make_tasks_blueprint(
    task_repo: TaskRepo,
    source_repo: SourceRepo,
    config_publisher: ConfigPublisher | None = None,
    preview_base_url: str = "",
) -> Blueprint:
    bp = Blueprint("tasks", __name__)

    @bp.post("/tasks")
    def create_task():
        task, err = _task_from_payload(request.get_json(silent=True) or {})
        if err:
            return _error(err)
        assert task is not None
        if source_repo.get(task.source_id) is None:
            return _error("source_id does not exist")
        return jsonify(_task_json(task_repo.create(task), preview_base_url)), 201

    @bp.get("/tasks")
    def list_tasks():
        return jsonify([_task_json(task, preview_base_url) for task in task_repo.list()])

    @bp.get("/tasks/<task_id>")
    def get_task(task_id: str):
        task = task_repo.get(task_id)
        if task is None:
            return _error("task not found", 404)
        return jsonify(_task_json(task, preview_base_url))

    @bp.post("/tasks/<task_id>/start")
    def start_task(task_id: str):
        task = task_repo.get(task_id)
        if task is None:
            return _error("task not found", 404)
        source = source_repo.get(task.source_id)
        if source is None:
            task.status = "error"
            task.error_message = "source not found"
            task_repo.update(task)
            return _error("source not found", 409)
        if not source.enabled:
            task.status = "error"
            task.error_message = "source disabled"
            task_repo.update(task)
            return _error("source disabled", 409)
        if config_publisher is not None:
            try:
                config_publisher.publish_started(task, source)
            except Exception:
                task.status = "error"
                task.error_message = "failed to publish runtime config"
                task_repo.update(task)
                return _error(task.error_message, 500)
        task.status = "running"
        task.error_message = ""
        try:
            task_repo.update(task)
        except Exception:
            task.status = "error"
            task.error_message = "failed to update task status"
            if config_publisher is not None:
                config_publisher.publish_stopped(task)
            task_repo.update(task)
            return _error(task.error_message, 500)
        return jsonify(_task_json(task, preview_base_url))

    @bp.post("/tasks/<task_id>/stop")
    def stop_task(task_id: str):
        task = task_repo.get(task_id)
        if task is None:
            return _error("task not found", 404)
        task.status = "stopped"
        task_repo.update(task)
        if config_publisher is not None:
            config_publisher.publish_stopped(task)
        return jsonify(_task_json(task, preview_base_url))

    @bp.get("/tasks/<task_id>/status")
    def task_status(task_id: str):
        task = task_repo.get(task_id)
        if task is None:
            return _error("task not found", 404)
        return jsonify(
            {
                "id": task.id,
                "status": task.status,
                "error_message": task.error_message,
                **({"preview_url": _preview_url(task, preview_base_url)} if task.status == "running" else {}),
            }
        )

    return bp
