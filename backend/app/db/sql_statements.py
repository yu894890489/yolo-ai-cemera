"""Parse a .sql file body into individually executable statements.

The migration files use ``CREATE TABLE IF NOT EXISTS`` (idempotent) and only
``--`` line comments. pymysql's ``cursor.execute`` runs one statement at a time,
so we strip line comments and split on ``;``.
"""

from __future__ import annotations


def split_sql_statements(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    statements = []
    for chunk in cleaned.split(";"):
        stmt = chunk.strip()
        if stmt:
            statements.append(stmt)
    return statements
