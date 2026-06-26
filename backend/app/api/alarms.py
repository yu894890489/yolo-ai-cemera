"""Alarm query + push-fallback API routes.

  * GET /alarms            — most-recent-first list (``limit`` query param).
  * GET /alarms/stream     — Server-Sent Events fallback for clients that cannot
                             hold a WebSocket. Bridges the same Redis ``ws:alarm``
                             Pub/Sub channel the /ws route fans out.

WebSocket (``/ws`` in :mod:`app.api`) is the primary push; SSE here is the
documented fallback.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from flask import Blueprint, Response, jsonify, request

from app.api.repository import AlarmRepo

_WS_CHANNEL = "ws:alarm"


def _sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def make_alarms_blueprint(repo: AlarmRepo, redis_client=None) -> Blueprint:
    bp = Blueprint("alarms", __name__)

    @bp.get("/alarms")
    def list_alarms():
        try:
            limit = int(request.args.get("limit", 50))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 500))
        return jsonify([asdict(a) for a in repo.list(limit=limit)])

    @bp.get("/alarms/stream")
    def stream_alarms():  # pragma: no cover - exercised in integration only
        if redis_client is None:
            return jsonify({"error": "sse unavailable"}), 503

        def _gen():
            pubsub = redis_client.pubsub()
            pubsub.subscribe(_WS_CHANNEL)
            try:
                yield ": connected\n\n"
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if not data:
                        continue
                    text = data if isinstance(data, str) else data.decode("utf-8")
                    yield f"data: {text}\n\n"
            finally:
                pubsub.close()

        return Response(_gen(), mimetype="text/event-stream")

    return bp
