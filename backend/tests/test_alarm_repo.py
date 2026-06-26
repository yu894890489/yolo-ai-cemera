"""Tests for the Alarm model + repository (BE-M1-B)."""

from __future__ import annotations

from app.api.models import Alarm
from app.api.repository import InMemoryAlarmRepo


def _alarm(event_id="e1", **kw):
    base = dict(
        event_id=event_id,
        task_id="t1",
        rule_id="demo",
        class_name="person",
        score=0.9,
        bbox="0,0,10,10",
        roi="",
        mode="vlm",
        vlm_status="ok",
        vlm_reason="climbing",
        vlm_confidence=0.8,
        screenshot_object="2026/06/26/abc.jpg",
        ts_ms=1000,
    )
    base.update(kw)
    return Alarm(**base)


def test_create_assigns_id_and_persists():
    repo = InMemoryAlarmRepo()
    created = repo.create(_alarm())
    assert created is not None
    assert created.id
    assert repo.get(created.id) is created


def test_create_duplicate_event_id_returns_none():
    repo = InMemoryAlarmRepo()
    assert repo.create(_alarm(event_id="dup")) is not None
    assert repo.create(_alarm(event_id="dup")) is None


def test_list_returns_most_recent_first_and_respects_limit():
    repo = InMemoryAlarmRepo()
    for i in range(5):
        repo.create(_alarm(event_id=f"e{i}", ts_ms=1000 + i))
    recent = repo.list(limit=3)
    assert len(recent) == 3
    assert recent[0].ts_ms == 1004
