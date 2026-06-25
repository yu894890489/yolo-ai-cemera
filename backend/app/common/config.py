"""Configuration loader.

Two layers:
  1. Environment variables (12-factor) — always read first; required for bootstrap.
  2. MySQL ``system_configs`` table — overlays runtime-tunable keys. The S2 schema
     is not delivered yet (06-26 deadline), so the loader here defines the
     contract and degrades to env-only when the table is missing.

Reload is triggered by SIGHUP; see :mod:`app.common.signals`. Rule-level hot
reload (parsing rule definitions) is M1 work and is intentionally out of scope.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.common.vlm import VLMEndpoint

logger = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: str | None = None


@dataclass
class MySQLConfig:
    host: str = "mysql"
    port: int = 3306
    user: str = "yolo"
    password: str = ""
    db: str = "yolo_vlm"


@dataclass
class MinioConfig:
    endpoint: str = "minio:9000"
    access_key: str = "minioadmin"
    secret_key: str = ""
    bucket_alarms: str = "alarms"
    bucket_recordings: str = "recordings"
    secure: bool = False


@dataclass
class StreamConfig:
    frame_prefix: str = "frame:"
    alarm_raw: str = "alarm:raw"
    alarm_pushed: str = "alarm:pushed"
    group_consumer: str = "g:consumer"
    group_saver: str = "g:saver"


@dataclass
class WorkerPorts:
    producer: int = 9101
    consumer: int = 9102
    saver: int = 9103
    flask: int = 8000


@dataclass
class YoloConfig:
    model: str = "yolov8n.pt"
    device: str = "cpu"


@dataclass
class TaskConfig:
    confidence: float = 0.5
    roi: list[int] | None = None
    prompt: str = ""
    vlm_enabled: bool = False


@dataclass
class VLMConfig:
    queue_high_watermark: int = 100
    queue_timeout_ms: int = 30000
    disable_thinking: bool = False
    max_retries: int = 2
    backoff_base_s: float = 0.2


@dataclass
class AppConfig:
    redis: RedisConfig = field(default_factory=RedisConfig)
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    minio: MinioConfig = field(default_factory=MinioConfig)
    streams: StreamConfig = field(default_factory=StreamConfig)
    ports: WorkerPorts = field(default_factory=WorkerPorts)
    yolo: YoloConfig = field(default_factory=YoloConfig)
    task: TaskConfig = field(default_factory=TaskConfig)
    vlm: VLMConfig = field(default_factory=VLMConfig)
    flask_secret_key: str = "change-me"
    overlay: dict[str, Any] = field(default_factory=dict)
    version: int = 0


_lock = RLock()
_cached: AppConfig | None = None
_version: int = 0


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("env %s=%r is not an int, falling back to %d", name, raw, default)
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "y", "on")


def _parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).lower() in ("1", "true", "yes", "y", "on")


def _parse_roi(raw: Any) -> list[int]:
    if isinstance(raw, list):
        vals = raw
    else:
        vals = [part.strip() for part in str(raw).split(",") if part.strip()]
    roi = [int(val) for val in vals]
    if len(roi) != 4:
        raise ValueError("task.roi must contain exactly four integers")
    return roi


def _overlay_keys(before: AppConfig, after: AppConfig) -> list[str]:
    changed: list[str] = []
    if before.task != after.task:
        changed.extend(key for key in after.overlay if key.startswith("task."))
    if before.vlm != after.vlm:
        changed.extend(key for key in after.overlay if key.startswith("vlm."))
    return sorted(set(changed))


def apply_overlay(cfg: AppConfig, overlay: dict[str, Any]) -> AppConfig:
    cfg.overlay = overlay
    for key, raw in overlay.items():
        if key == "task.confidence":
            cfg.task.confidence = float(raw)
        elif key == "task.roi":
            cfg.task.roi = _parse_roi(raw)
        elif key == "task.prompt":
            cfg.task.prompt = str(raw)
        elif key == "task.vlm_enabled":
            cfg.task.vlm_enabled = _parse_bool(raw)
        elif key == "vlm.queue_high_watermark":
            cfg.vlm.queue_high_watermark = int(raw)
        elif key == "vlm.queue_timeout_ms":
            cfg.vlm.queue_timeout_ms = int(raw)
        elif key == "vlm.disable_thinking":
            cfg.vlm.disable_thinking = _parse_bool(raw)
        elif key == "vlm.max_retries":
            cfg.vlm.max_retries = int(raw)
        elif key == "vlm.backoff_base_s":
            cfg.vlm.backoff_base_s = float(raw)
    return cfg


def load_from_env() -> AppConfig:
    """Build :class:`AppConfig` from environment variables only.

    Used at bootstrap and as the base layer before applying the MySQL overlay.
    """
    return AppConfig(
        redis=RedisConfig(
            host=_env("REDIS_HOST", "redis") or "redis",
            port=_env_int("REDIS_PORT", 6379),
            db=_env_int("REDIS_DB", 0),
            password=_env("REDIS_PASSWORD"),
        ),
        mysql=MySQLConfig(
            host=_env("MYSQL_HOST", "mysql") or "mysql",
            port=_env_int("MYSQL_PORT", 3306),
            user=_env("MYSQL_USER", "yolo") or "yolo",
            password=_env("MYSQL_PASSWORD", "") or "",
            db=_env("MYSQL_DB", "yolo_vlm") or "yolo_vlm",
        ),
        minio=MinioConfig(
            endpoint=_env("MINIO_ENDPOINT", "minio:9000") or "minio:9000",
            access_key=_env("MINIO_ACCESS_KEY", "minioadmin") or "minioadmin",
            secret_key=_env("MINIO_SECRET_KEY", "") or "",
            bucket_alarms=_env("MINIO_BUCKET_ALARMS", "alarms") or "alarms",
            bucket_recordings=_env("MINIO_BUCKET_RECORDINGS", "recordings") or "recordings",
            secure=_env_bool("MINIO_SECURE", False),
        ),
        streams=StreamConfig(
            frame_prefix=_env("STREAM_FRAME_PREFIX", "frame:") or "frame:",
            alarm_raw=_env("STREAM_ALARM_RAW", "alarm:raw") or "alarm:raw",
            alarm_pushed=_env("STREAM_ALARM_PUSHED", "alarm:pushed") or "alarm:pushed",
            group_consumer=_env("CONSUMER_GROUP_CONSUMER", "g:consumer") or "g:consumer",
            group_saver=_env("CONSUMER_GROUP_SAVER", "g:saver") or "g:saver",
        ),
        ports=WorkerPorts(
            producer=_env_int("PRODUCER_METRICS_PORT", 9101),
            consumer=_env_int("CONSUMER_METRICS_PORT", 9102),
            saver=_env_int("SAVER_METRICS_PORT", 9103),
            flask=_env_int("FLASK_PORT", 8000),
        ),
        yolo=YoloConfig(
            model=_env("YOLO_MODEL", "yolov8n.pt") or "yolov8n.pt",
            device=_env("YOLO_DEVICE", "cpu") or "cpu",
        ),
        flask_secret_key=_env("FLASK_SECRET_KEY", "change-me") or "change-me",
    )


def fetch_mysql_overlay(cfg: AppConfig) -> dict[str, Any]:
    """Read the ``system_configs`` table and return a flat key->value dict.

    Schema is owned by S2 (BE-M0-S2). Until it lands, the table either does not
    exist or is empty; either case is non-fatal — we log and return ``{}`` so
    the worker continues with env-only config.
    """
    try:
        import pymysql  # type: ignore
    except ImportError:
        logger.debug("pymysql not installed; skipping MySQL overlay")
        return {}

    try:
        conn = pymysql.connect(
            host=cfg.mysql.host,
            port=cfg.mysql.port,
            user=cfg.mysql.user,
            password=cfg.mysql.password,
            database=cfg.mysql.db,
            connect_timeout=3,
            read_timeout=3,
        )
    except Exception as exc:  # pragma: no cover - depends on env
        logger.warning("MySQL overlay unavailable (%s); falling back to env-only", exc)
        return {}

    try:
        with conn.cursor() as cur:
            # Expected S2 schema (subject to confirmation):
            #   CREATE TABLE system_configs (
            #     `key`   VARCHAR(128) PRIMARY KEY,
            #     `value` TEXT NOT NULL,
            #     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            #   );
            try:
                cur.execute("SELECT `key`, `value` FROM system_configs")
            except Exception as exc:
                logger.info("system_configs not ready (%s); env-only", exc)
                return {}
            rows = cur.fetchall() or []
            return {row[0]: row[1] for row in rows}
    finally:
        conn.close()


def fetch_vlm_endpoints(cfg: AppConfig) -> list[VLMEndpoint]:
    """Read cloud VLM provider configuration from ``vlm_endpoints``.

    The expected columns are provider, endpoint_url, enabled, priority,
    timeout_ms and max_tokens. Missing table or database connectivity is
    non-fatal so the small-only path stays available.
    """
    try:
        import pymysql  # type: ignore
    except ImportError:
        logger.debug("pymysql not installed; skipping vlm_endpoints")
        return []

    try:
        conn = pymysql.connect(
            host=cfg.mysql.host,
            port=cfg.mysql.port,
            user=cfg.mysql.user,
            password=cfg.mysql.password,
            database=cfg.mysql.db,
            connect_timeout=3,
            read_timeout=3,
        )
    except Exception as exc:  # pragma: no cover - depends on env
        logger.warning("vlm_endpoints unavailable (%s); VLM disabled", exc)
        return []

    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT provider, endpoint_url, enabled, priority, timeout_ms, max_tokens "
                    "FROM vlm_endpoints ORDER BY priority ASC"
                )
            except Exception as exc:
                logger.info("vlm_endpoints not ready (%s); VLM disabled", exc)
                return []
            return [
                VLMEndpoint(
                    provider=str(row[0]),
                    url=str(row[1]),
                    enabled=bool(row[2]),
                    priority=int(row[3]),
                    timeout_s=float(row[4]) / 1000.0,
                    max_tokens=int(row[5]),
                )
                for row in (cur.fetchall() or [])
            ]
    finally:
        conn.close()


def reload_config() -> AppConfig:
    global _cached, _version
    old = _cached or load_from_env()
    cfg = load_from_env()
    overlay = fetch_mysql_overlay(cfg)
    try:
        apply_overlay(cfg, overlay)
    except Exception as exc:
        logger.error("config reload REJECTED — overlay parse failed: %s", exc)
        return old
    _version += 1
    cfg.version = _version
    changed = _overlay_keys(old, cfg)
    with _lock:
        _cached = cfg
    logger.info(
        "config reloaded: version=%d overlay_keys=%d changed=%s",
        cfg.version,
        len(cfg.overlay),
        changed if changed else "none",
    )
    return cfg


def get_config() -> AppConfig:
    """Return the currently active config; load lazily on first access."""
    global _cached
    with _lock:
        if _cached is None:
            _cached = load_from_env()
            _cached.overlay = fetch_mysql_overlay(_cached)
            apply_overlay(_cached, _cached.overlay)
        return _cached
