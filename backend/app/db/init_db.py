"""Apply SQL migrations to MySQL on container startup (BE-M1-D / YU-56).

Run as a one-shot Compose service before the app/workers start:

    python -m app.db.init_db

Connection params come from the same env the app uses (app.common.config).
All migrations are ``CREATE TABLE IF NOT EXISTS`` so re-running is a no-op. A
missing/unreachable MySQL is fatal here (unlike the lazy app path) because the
whole point of this step is to guarantee the schema before the stack comes up.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

from app.common.config import get_config
from app.db.sql_statements import split_sql_statements

logger = logging.getLogger(__name__)

# Order matters only loosely (no FKs), but keep a stable, readable sequence.
MIGRATION_FILES = [
    "sources.sql",
    "tasks.sql",
    "alarms.sql",
    "vlm_endpoints.sql",
    "system_configs.sql",
]

_SQL_DIR = Path(__file__).resolve().parent.parent.parent / "sql"


def apply_migrations(conn: Any, migrations: dict[str, str]) -> int:
    """Execute every statement in ``migrations`` (name -> sql body). Returns the
    number of statements run. Commits once at the end."""
    total = 0
    for name, body in migrations.items():
        statements = split_sql_statements(body)
        for stmt in statements:
            with conn.cursor() as cur:
                cur.execute(stmt)
            total += 1
        logger.info("migration %s: %d statement(s)", name, len(statements))
    conn.commit()
    return total


def _load_migrations() -> dict[str, str]:
    migrations: dict[str, str] = {}
    for name in MIGRATION_FILES:
        path = _SQL_DIR / name
        if not path.exists():
            logger.warning("migration file missing, skipping: %s", path)
            continue
        migrations[name] = path.read_text(encoding="utf-8")
    return migrations


def _connect(cfg, attempts: int = 30, delay_s: float = 2.0):
    import pymysql

    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return pymysql.connect(
                host=cfg.mysql.host,
                port=cfg.mysql.port,
                user=cfg.mysql.user,
                password=cfg.mysql.password,
                database=cfg.mysql.db,
                connect_timeout=5,
            )
        except Exception as exc:  # pragma: no cover - depends on env
            last_exc = exc
            logger.warning(
                "MySQL not ready (attempt %d/%d): %s", i + 1, attempts, exc
            )
            time.sleep(delay_s)
    raise SystemExit(f"MySQL unreachable after {attempts} attempts: {last_exc}")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    cfg = get_config()
    logger.info(
        "applying migrations to mysql://%s:%s/%s",
        cfg.mysql.host,
        cfg.mysql.port,
        cfg.mysql.db,
    )
    conn = _connect(cfg)
    try:
        count = apply_migrations(conn, _load_migrations())
        logger.info("migrations complete: %d statement(s) executed", count)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
