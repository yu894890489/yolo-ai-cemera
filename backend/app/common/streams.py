"""Redis client + Stream helpers.

The wrapper here is intentionally thin — it centralises:
  * connection construction (so a single env-variable change moves all workers),
  * Consumer Group creation idempotency (``MKSTREAM`` + ``BUSYGROUP`` swallow),
  * a ``read_group`` helper that returns plain dicts to keep workers
    framework-free.

Zero-loss guarantee comes from Consumer Group + ``XACK`` only after the
downstream write is durable; that contract is the workers' responsibility, not
this module's.
"""

from __future__ import annotations

import logging
from typing import Iterable

import redis

from .config import AppConfig

logger = logging.getLogger(__name__)


def make_client(cfg: AppConfig) -> redis.Redis:
    """Build a Redis client. Decoded responses for cleaner worker code."""
    return redis.Redis(
        host=cfg.redis.host,
        port=cfg.redis.port,
        db=cfg.redis.db,
        password=cfg.redis.password or None,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    )


def ensure_group(client: redis.Redis, stream: str, group: str) -> None:
    """Create the consumer group if missing; idempotent.

    ``MKSTREAM`` creates the stream if it does not exist (first run, before any
    Producer push). ``BUSYGROUP`` is the expected error on re-run and is
    silenced.
    """
    try:
        client.xgroup_create(name=stream, groupname=group, id="0", mkstream=True)
        logger.info("created consumer group %s on %s", group, stream)
    except redis.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.debug("consumer group %s already exists on %s", group, stream)
        else:
            raise


def read_group(
    client: redis.Redis,
    *,
    stream: str,
    group: str,
    consumer: str,
    count: int = 16,
    block_ms: int = 1000,
) -> list[tuple[str, dict[str, str]]]:
    """Read pending entries for ``consumer`` from the group.

    Returns a flat list of ``(entry_id, fields_dict)``. Empty list when the
    block timeout elapses with no new data — workers should treat empty as
    "tick, do bookkeeping".
    """
    resp = client.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: ">"},
        count=count,
        block=block_ms,
    )
    if not resp:
        return []
    out: list[tuple[str, dict[str, str]]] = []
    for _stream_name, entries in resp:
        out.extend(entries)
    return out


def ack(client: redis.Redis, stream: str, group: str, entry_ids: Iterable[str]) -> int:
    """XACK a batch of entry ids. Returns the count the server acknowledged."""
    ids = list(entry_ids)
    if not ids:
        return 0
    return int(client.xack(stream, group, *ids))


def pending_count(client: redis.Redis, stream: str, group: str) -> int:
    """Return the number of pending (un-ack'd) entries for a group.

    Cheap call — uses ``XPENDING`` summary form. Used to feed ``stream_lag``.
    """
    try:
        info = client.xpending(stream, group)
        # Newer redis-py returns dict; older returns list. Normalise.
        if isinstance(info, dict):
            return int(info.get("pending", 0))
        return int(info[0]) if info else 0
    except redis.ResponseError:
        # Group not yet created -> no lag.
        return 0
