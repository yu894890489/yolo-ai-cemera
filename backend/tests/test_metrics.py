"""Tests for app.common.metrics — exercise required series + worker label."""

from __future__ import annotations

from prometheus_client import generate_latest

from app.common import metrics as metrics_mod


def test_required_series_present():
    registry = metrics_mod.new_registry()
    m = metrics_mod.build_metrics(registry, worker="consumer")
    m.frame_in_total.labels(task_id="t1").inc(0)
    m.frame_drop_total.labels(reason="backpressure").inc(0)
    m.yolo_latency_ms.observe(12.3)
    m.alarm_emit_total.labels(rule_id="demo").inc(0)
    m.stream_lag.labels(stream="frame:t1").set(0)
    m.process_up.labels(worker="consumer").set(1)

    text = generate_latest(registry).decode("utf-8")
    for needle in (
        "frame_in_total",
        "frame_drop_total",
        "yolo_latency_ms",
        "alarm_emit_total",
        "stream_lag",
        "process_up",
    ):
        assert needle in text, f"metric {needle} missing from export"
