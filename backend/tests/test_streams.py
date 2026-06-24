"""Tests for app.common.streams against fakeredis."""

from __future__ import annotations

import pytest

fakeredis = pytest.importorskip("fakeredis")

from app.common import streams


@pytest.fixture
def client():
    server = fakeredis.FakeServer()
    return fakeredis.FakeStrictRedis(server=server, decode_responses=True)


def test_ensure_group_idempotent(client):
    streams.ensure_group(client, "frame:demo", "g:consumer")
    streams.ensure_group(client, "frame:demo", "g:consumer")
    info = client.xinfo_groups("frame:demo")
    assert any(g["name"] == "g:consumer" for g in info)


def test_read_group_returns_entries(client):
    stream = "frame:demo"
    streams.ensure_group(client, stream, "g:consumer")
    client.xadd(stream, {"task_id": "demo", "seq": "1", "ts_ms": "0", "frame_jpeg_b64": ""})
    client.xadd(stream, {"task_id": "demo", "seq": "2", "ts_ms": "0", "frame_jpeg_b64": ""})

    entries = streams.read_group(
        client,
        stream=stream,
        group="g:consumer",
        consumer="c1",
        count=10,
        block_ms=0,
    )
    assert len(entries) == 2
    seqs = [int(fields["seq"]) for _id, fields in entries]
    assert seqs == [1, 2]


def test_unacked_entry_is_redelivered_after_pending_recovery(client):
    """Zero-loss invariant: an entry without ACK stays pending."""
    stream = "frame:demo"
    streams.ensure_group(client, stream, "g:consumer")
    client.xadd(stream, {"task_id": "demo", "seq": "1", "ts_ms": "0", "frame_jpeg_b64": ""})

    entries = streams.read_group(
        client,
        stream=stream,
        group="g:consumer",
        consumer="c1",
        count=10,
        block_ms=0,
    )
    assert len(entries) == 1
    # Simulate crash: we never ACK.
    assert streams.pending_count(client, stream, "g:consumer") == 1


def test_ack_drains_pending(client):
    stream = "frame:demo"
    streams.ensure_group(client, stream, "g:consumer")
    client.xadd(stream, {"task_id": "demo", "seq": "1", "ts_ms": "0", "frame_jpeg_b64": ""})

    entries = streams.read_group(
        client,
        stream=stream,
        group="g:consumer",
        consumer="c1",
        count=10,
        block_ms=0,
    )
    assert len(entries) == 1
    entry_id, _ = entries[0]
    assert streams.ack(client, stream, "g:consumer", [entry_id]) == 1
    assert streams.pending_count(client, stream, "g:consumer") == 0
