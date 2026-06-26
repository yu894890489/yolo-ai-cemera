"""Flask HTTP + WebSocket entry point.

Responsibilities:
  * GET /healthz  — liveness, used by Compose health checks.
  * GET /metrics  — Flask's own minimal metrics (just process_up; the heavy
                    lifting lives in the worker processes).
  * GET /ws       — WebSocket; subscribes to Redis ws:alarm and fans out every
                    published alarm to connected clients.

Kept tiny on purpose. Business API surface lands in M1+.
"""

from __future__ import annotations

import logging
import os
import threading

from flask import Flask, Response, jsonify
from flask_sock import Sock
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from app.common.config import get_config
from app.common.signals import install_sighup
from app.common.streams import make_client

from app.api.sources import make_sources_blueprint
from app.api.tasks import RedisConfigPublisher, make_tasks_blueprint
from app.api.repository import (
    InMemorySourceRepo, InMemoryTaskRepo,
    MySQLSourceRepo, MySQLTaskRepo,
)

from app.common.vlm import VLMRuntimeState


logger = logging.getLogger(__name__)
_vlm_runtime_state = VLMRuntimeState()


def get_vlm_runtime_state() -> VLMRuntimeState:
    return _vlm_runtime_state


def create_app() -> Flask:
    cfg = get_config()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = cfg.flask_secret_key
    sock = Sock(app)

    # Flask's own metrics: just confirm the main process is up.
    registry = CollectorRegistry()
    process_up = Gauge(
        "process_up", "1 if Flask main process is up", labelnames=("worker",), registry=registry
    )
    process_up.labels(worker="flask").set(1)

    redis_client = make_client(cfg)
    if os.environ.get("API_REPO", "memory") == "mysql":
        conn_params = {
            "host": cfg.mysql.host,
            "port": cfg.mysql.port,
            "user": cfg.mysql.user,
            "password": cfg.mysql.password,
            "database": cfg.mysql.db,
        }
        source_repo = MySQLSourceRepo(conn_params)
        task_repo = MySQLTaskRepo(conn_params)
    else:
        source_repo = InMemorySourceRepo()
        task_repo = InMemoryTaskRepo()
    config_publisher = RedisConfigPublisher(redis_client)
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    app.register_blueprint(
        make_tasks_blueprint(task_repo, source_repo, config_publisher=config_publisher),
        url_prefix="/api",
    )
    _clients: set = set()
    _clients_lock = threading.Lock()

    def _broadcast_loop():
        pubsub = redis_client.pubsub()
        pubsub.subscribe("ws:alarm")
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if not data:
                continue
            with _clients_lock:
                dead = []
                for ws in list(_clients):
                    try:
                        ws.send(data if isinstance(data, str) else data.decode("utf-8"))
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    _clients.discard(ws)

    threading.Thread(target=_broadcast_loop, name="ws-broadcast", daemon=True).start()
    install_sighup()

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/runtime/status")
    def runtime_status():
        active_cfg = get_config()
        vlm_state = get_vlm_runtime_state()
        return jsonify(
            {
                "config_version": active_cfg.version,
                "task": {
                    "confidence": active_cfg.task.confidence,
                    "roi": active_cfg.task.roi,
                    "prompt": active_cfg.task.prompt,
                    "vlm_enabled": active_cfg.task.vlm_enabled,
                },
                "vlm": {
                    "enabled": active_cfg.task.vlm_enabled,
                    "active_provider": vlm_state.active_provider,
                    "last_error": vlm_state.last_error,
                    "last_failure_reason": vlm_state.last_failure_reason,
                    "degraded_mode": vlm_state.degraded_mode,
                    "queue_high_watermark": active_cfg.vlm.queue_high_watermark,
                    "queue_timeout_ms": active_cfg.vlm.queue_timeout_ms,
                    "disable_thinking": active_cfg.vlm.disable_thinking,
                    "max_retries": active_cfg.vlm.max_retries,
                },
            }
        )

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), mimetype="text/plain; version=0.0.4")

    @sock.route("/ws")
    def ws_route(ws):  # pragma: no cover - exercised in integration only
        with _clients_lock:
            _clients.add(ws)
        try:
            while True:
                msg = ws.receive(timeout=30)
                if msg is None:
                    continue
        finally:
            with _clients_lock:
                _clients.discard(ws)

    return app


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cfg = get_config()
    app = create_app()
    app.run(host="0.0.0.0", port=cfg.ports.flask)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
