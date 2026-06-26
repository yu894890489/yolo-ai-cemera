"""Data access layer for video sources.

Two implementations:

* :class:`InMemorySourceRepo` — in-process dict, used in tests.
* :class:`MySQLSourceRepo` — real MySQL backed (M1 production).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from typing import Any

from app.api.models import Source, Task, _ts


class SourceRepo(ABC):
    @abstractmethod
    def create(self, source: Source) -> Source: ...

    @abstractmethod
    def get(self, source_id: str) -> Source | None: ...

    @abstractmethod
    def list(self) -> list[Source]: ...

    @abstractmethod
    def update(self, source: Source) -> Source | None: ...

    @abstractmethod
    def delete(self, source_id: str) -> bool: ...


class InMemorySourceRepo(SourceRepo):
    def __init__(self) -> None:
        self._store: dict[str, Source] = {}

    def create(self, source: Source) -> Source:
        source.id = uuid.uuid4().hex[:12]
        now = _ts()
        source.created_at = now
        source.updated_at = now
        self._store[source.id] = source
        return source

    def get(self, source_id: str) -> Source | None:
        return self._store.get(source_id)

    def list(self) -> list[Source]:
        return list(self._store.values())

    def update(self, source: Source) -> Source | None:
        existing = self._store.get(source.id)
        if existing is None:
            return None
        source.updated_at = _ts()
        self._store[source.id] = source
        return source

    def delete(self, source_id: str) -> bool:
        if source_id not in self._store:
            return False
        del self._store[source_id]
        return True


class MySQLSourceRepo(SourceRepo):
    """Real MySQL implementation — wired in production."""

    def __init__(self, connection_params: dict[str, Any]) -> None:
        self._params = connection_params
        self._conn = None

    def _connect(self):
        if self._conn is None:
            import pymysql

            self._conn = pymysql.connect(**self._params)
        else:
            self._conn.ping(reconnect=True)
        return self._conn

    def _source_from_row(self, row) -> Source:
        return Source(row[0], row[1], row[2], row[3], bool(row[4]), row[5], row[6], row[7])

    def create(self, source: Source) -> Source:
        conn = self._connect()
        now = _ts()
        source.id = uuid.uuid4().hex[:12]
        source.created_at = now
        source.updated_at = now
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sources (id, name, protocol, address, enabled, note, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (source.id, source.name, source.protocol, source.address,
                 source.enabled, source.note, source.created_at, source.updated_at),
            )
            conn.commit()
        return source

    def get(self, source_id: str) -> Source | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, protocol, address, enabled, note, created_at, updated_at FROM sources WHERE id = %s", (source_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return self._source_from_row(row)

    def list(self) -> list[Source]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, protocol, address, enabled, note, created_at, updated_at FROM sources")
            return [self._source_from_row(row) for row in cur.fetchall()]

    def update(self, source: Source) -> Source | None:
        conn = self._connect()
        source.updated_at = _ts()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sources SET name=%s, protocol=%s, address=%s, enabled=%s, note=%s, updated_at=%s WHERE id=%s",
                (source.name, source.protocol, source.address, source.enabled, source.note, source.updated_at, source.id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return source

    def delete(self, source_id: str) -> bool:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
            conn.commit()
            return cur.rowcount > 0

class TaskRepo(ABC):
    @abstractmethod
    def create(self, task: Task) -> Task: ...

    @abstractmethod
    def get(self, task_id: str) -> Task | None: ...

    @abstractmethod
    def list(self) -> list[Task]: ...

    @abstractmethod
    def update(self, task: Task) -> Task | None: ...


class InMemoryTaskRepo(TaskRepo):
    def __init__(self) -> None:
        self._store: dict[str, Task] = {}

    def create(self, task: Task) -> Task:
        task.id = uuid.uuid4().hex[:12]
        now = _ts()
        task.created_at = now
        task.updated_at = now
        task.status = "created"
        self._store[task.id] = task
        return task

    def get(self, task_id: str) -> Task | None:
        return self._store.get(task_id)

    def list(self) -> list[Task]:
        return list(self._store.values())

    def update(self, task: Task) -> Task | None:
        existing = self._store.get(task.id)
        if existing is None:
            return None
        task.updated_at = _ts()
        self._store[task.id] = task
        return task


class MySQLTaskRepo(TaskRepo):
    """Real MySQL implementation — wired in production."""

    def __init__(self, connection_params: dict[str, Any]) -> None:
        self._params = connection_params
        self._conn = None

    def _connect(self):
        if self._conn is None:
            import pymysql
            self._conn = pymysql.connect(**self._params)
        else:
            self._conn.ping(reconnect=True)
        return self._conn

    def create(self, task: Task) -> Task:
        conn = self._connect()
        now = _ts()
        task.id = uuid.uuid4().hex[:12]
        task.created_at = now
        task.updated_at = now
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (id, source_id, algorithm_id, roi, prompt, confidence, status, error_message, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (task.id, task.source_id, task.algorithm_id, task.roi, task.prompt,
                 task.confidence, task.status, task.error_message, task.created_at, task.updated_at),
            )
            conn.commit()
        return task

    def get(self, task_id: str) -> Task | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, source_id, algorithm_id, roi, prompt, confidence, status, error_message, created_at, updated_at "
                "FROM tasks WHERE id=%s", (task_id,))
            row = cur.fetchone()
            if row is None:
                return None
            return Task(*row)

    def list(self) -> list[Task]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, source_id, algorithm_id, roi, prompt, confidence, status, error_message, created_at, updated_at FROM tasks")
            return [Task(*row) for row in cur.fetchall()]

    def update(self, task: Task) -> Task | None:
        conn = self._connect()
        task.updated_at = _ts()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET source_id=%s, algorithm_id=%s, roi=%s, prompt=%s, confidence=%s, "
                "status=%s, error_message=%s, updated_at=%s WHERE id=%s",
                (task.source_id, task.algorithm_id, task.roi, task.prompt, task.confidence,
                 task.status, task.error_message, task.updated_at, task.id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return task
