"""Alarm dedup key.

A detected target produces a frame's worth of alarms many times a second; we
collapse repeats within a short window into a single event so the operator (and
MySQL) see one alarm per target per window.

``event_id`` = sha1(task_id | roi | class | floor(ts_s / window_s)). The
Saver uses it both as a Redis ``SET NX`` guard and as a unique key in MySQL.
"""

from __future__ import annotations

import hashlib


def event_id(task_id: str, roi: str, cls: str, *, ts_ms: int, window_s: int = 3) -> str:
    window_s = max(1, int(window_s))
    bucket = int(ts_ms) // 1000 // window_s
    raw = f"{task_id}|{roi}|{cls}|{bucket}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
