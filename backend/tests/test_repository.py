"""Tests for repository mapping behavior."""

from __future__ import annotations

from app.api.repository import MySQLSourceRepo


def test_mysql_source_row_converts_enabled_to_bool():
    row = ("src1", "Cam", "rtsp", "rtsp://x/stream", 1, "", "created", "updated")

    source = MySQLSourceRepo._source_from_row(row)

    assert source.enabled is True


def test_mysql_source_row_converts_disabled_to_bool():
    row = ("src1", "Cam", "rtsp", "rtsp://x/stream", 0, "", "created", "updated")

    source = MySQLSourceRepo._source_from_row(row)

    assert source.enabled is False
