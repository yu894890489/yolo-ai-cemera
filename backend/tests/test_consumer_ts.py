"""Replay-safe ts_ms resolution for the consumer (BE-M1-B review fix).

event_id is derived from ts_ms, so a non-deterministic fallback (wall clock)
would shift a replayed frame into a different dedup window and duplicate the
alarm. The Redis stream entry-id millisecond prefix is stable across
re-delivery, so it is the correct deterministic fallback.
"""

from __future__ import annotations

from app.workers.consumer import _resolve_ts_ms


def test_uses_fields_ts_ms_when_present():
    assert _resolve_ts_ms({"ts_ms": "1234"}, "9999999-0") == 1234


def test_falls_back_to_entry_id_ms_when_missing():
    assert _resolve_ts_ms({}, "1700000000000-3") == 1700000000000


def test_falls_back_to_entry_id_ms_when_invalid():
    assert _resolve_ts_ms({"ts_ms": "abc"}, "1700000000000-0") == 1700000000000


def test_zero_ts_ms_treated_as_missing():
    assert _resolve_ts_ms({"ts_ms": "0"}, "1700000000000-0") == 1700000000000
