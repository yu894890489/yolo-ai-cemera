"""Data models for M1 API surface."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Source:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    protocol: str = ""
    address: str = ""
    enabled: bool = True
    note: str = ""
    created_at: str = field(default_factory=_ts)
    updated_at: str = field(default_factory=_ts)


@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_id: str = ""
    algorithm_id: str = ""
    roi: str = ""
    prompt: str = ""
    confidence: float = 0.5
    status: str = "created"
    error_message: str = ""
    created_at: str = field(default_factory=_ts)
    updated_at: str = field(default_factory=_ts)