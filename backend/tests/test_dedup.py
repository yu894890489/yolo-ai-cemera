"""Tests for the alarm dedup key (BE-M1-B)."""

from __future__ import annotations

from app.common.dedup import event_id


def test_same_window_same_inputs_produces_same_id():
    a = event_id("task1", "0,0,10,10", "person", ts_ms=1_000_000, window_s=3)
    b = event_id("task1", "0,0,10,10", "person", ts_ms=1_000_500, window_s=3)
    assert a == b


def test_different_class_produces_different_id():
    a = event_id("task1", "0,0,10,10", "person", ts_ms=1_000_000, window_s=3)
    b = event_id("task1", "0,0,10,10", "car", ts_ms=1_000_000, window_s=3)
    assert a != b


def test_crossing_window_boundary_produces_different_id():
    # window_s=3 -> bucket = floor(ts_s/3). 1.0s and 4.0s are different buckets.
    a = event_id("task1", "0,0,10,10", "person", ts_ms=1_000, window_s=3)
    b = event_id("task1", "0,0,10,10", "person", ts_ms=4_000, window_s=3)
    assert a != b


def test_different_task_produces_different_id():
    a = event_id("task1", "roi", "person", ts_ms=0, window_s=3)
    b = event_id("task2", "roi", "person", ts_ms=0, window_s=3)
    assert a != b


def test_event_id_is_stable_hex_string():
    eid = event_id("t", "r", "person", ts_ms=0, window_s=3)
    assert isinstance(eid, str)
    assert len(eid) == 16
    int(eid, 16)  # parses as hex
