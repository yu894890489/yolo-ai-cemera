"""TDD for app.db.init_db: applying migration files against a connection."""

from app.db.init_db import apply_migrations, MIGRATION_FILES


class _FakeCursor:
    def __init__(self, recorder):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql):
        self._recorder.append(sql)


class _FakeConn:
    def __init__(self):
        self.executed = []
        self.commits = 0

    def cursor(self):
        return _FakeCursor(self.executed)

    def commit(self):
        self.commits += 1


def test_apply_migrations_executes_each_statement_and_commits():
    conn = _FakeConn()
    migrations = {
        "a.sql": "CREATE TABLE a (id INT);",
        "b.sql": "CREATE TABLE b (id INT);\nCREATE TABLE c (id INT);",
    }
    count = apply_migrations(conn, migrations)
    assert count == 3
    assert conn.executed == [
        "CREATE TABLE a (id INT)",
        "CREATE TABLE b (id INT)",
        "CREATE TABLE c (id INT)",
    ]
    assert conn.commits == 1


def test_apply_migrations_skips_comment_only_files():
    conn = _FakeConn()
    count = apply_migrations(conn, {"empty.sql": "-- just a comment\n"})
    assert count == 0
    assert conn.executed == []


def test_migration_files_list_covers_required_tables():
    # The acceptance needs sources/tasks/alarms/vlm_endpoints to exist.
    names = set(MIGRATION_FILES)
    assert {"sources.sql", "tasks.sql", "alarms.sql", "vlm_endpoints.sql"} <= names
