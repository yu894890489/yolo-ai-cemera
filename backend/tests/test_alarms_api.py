"""Tests for the alarm list + SSE endpoints (BE-M1-B)."""

from __future__ import annotations

import json

import pytest

from app.api.alarms import _sse_event, make_alarms_blueprint
from app.api.models import Alarm
from app.api.repository import InMemoryAlarmRepo


@pytest.fixture
def repo():
    return InMemoryAlarmRepo()


@pytest.fixture
def client(repo):
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(make_alarms_blueprint(repo), url_prefix="/api")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _alarm(event_id, ts_ms):
    return Alarm(
        event_id=event_id, task_id="t1", class_name="person", score=0.9,
        mode="vlm", vlm_status="ok", vlm_reason="climbing", vlm_confidence=0.8,
        screenshot_object=f"2026/06/26/{event_id}.jpg", ts_ms=ts_ms,
    )


def test_list_alarms_returns_most_recent_first(client, repo):
    for i in range(3):
        repo.create(_alarm(f"e{i}", ts_ms=1000 + i))
    resp = client.get("/api/alarms")
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert [a["event_id"] for a in body] == ["e2", "e1", "e0"]
    assert body[0]["screenshot_object"] == "2026/06/26/e2.jpg"
    assert body[0]["vlm_reason"] == "climbing"


def test_list_alarms_respects_limit(client, repo):
    for i in range(5):
        repo.create(_alarm(f"e{i}", ts_ms=1000 + i))
    resp = client.get("/api/alarms?limit=2")
    assert resp.status_code == 200
    assert len(json.loads(resp.data)) == 2


def test_sse_event_formats_payload_as_event_stream():
    out = _sse_event({"event_id": "e1", "class": "person"})
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    assert json.loads(out[len("data: "):].strip()) == {"event_id": "e1", "class": "person"}
