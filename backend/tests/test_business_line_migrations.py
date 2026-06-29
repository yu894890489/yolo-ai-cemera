"""YU-58 Stage1: SQL migrations include users + business_line columns/indexes."""

from __future__ import annotations

from app.db.init_db import MIGRATION_FILES


def test_users_migration_is_registered():
    assert "users.sql" in MIGRATION_FILES


def test_add_business_line_migration_is_registered():
    assert "add_business_line.sql" in MIGRATION_FILES


def _read(name: str) -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "sql" / name
    return root.read_text(encoding="utf-8")


def test_sources_sql_has_business_line_column_and_index():
    sql = _read("sources.sql")
    assert "business_line" in sql
    assert "idx_business_line" in sql


def test_tasks_sql_has_business_line_column_and_index():
    sql = _read("tasks.sql")
    assert "business_line" in sql
    assert "idx_business_line" in sql


def test_alarms_sql_has_business_line_column_and_index():
    sql = _read("alarms.sql")
    assert "business_line" in sql
    assert "idx_business_line" in sql


def test_users_sql_has_required_columns():
    sql = _read("users.sql")
    for col in ("id", "username", "password_hash", "business_line", "created_at", "enabled"):
        assert col in sql
    assert "uq_username" in sql


def test_add_business_line_alter_is_idempotent_pattern():
    sql = _read("add_business_line.sql")
    assert "ALTER TABLE sources" in sql
    assert "ALTER TABLE tasks" in sql
    assert "ALTER TABLE alarms" in sql
