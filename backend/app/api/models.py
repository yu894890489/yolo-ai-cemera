"""Data models for M1 API surface."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Default business_line for the phase1 (一期) deployment. Phase2 tenants set
# this on the user row at provisioning time; see backend/docs/business_line.md.
DEFAULT_BUSINESS_LINE = "phase1"


@dataclass
class Source:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    protocol: str = ""
    address: str = ""
    enabled: bool = True
    note: str = ""
    business_line: str = DEFAULT_BUSINESS_LINE
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
    business_line: str = DEFAULT_BUSINESS_LINE
    created_at: str = field(default_factory=_ts)
    updated_at: str = field(default_factory=_ts)


@dataclass
class Alarm:
    event_id: str = ""
    task_id: str = ""
    rule_id: str = "demo"
    class_name: str = ""
    score: float = 0.0
    bbox: str = ""
    roi: str = ""
    mode: str = "default"
    vlm_status: str = ""
    vlm_reason: str = ""
    vlm_confidence: float = 0.0
    screenshot_object: str = ""
    ts_ms: int = 0
    business_line: str = DEFAULT_BUSINESS_LINE
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=_ts)


@dataclass
class User:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    username: str = ""
    password_hash: str = ""
    business_line: str = DEFAULT_BUSINESS_LINE
    enabled: bool = True
    created_at: str = field(default_factory=_ts)