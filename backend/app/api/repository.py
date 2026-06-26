"""Data access layer for video sources.

Two implementations:

* :class:`InMemorySourceRepo` — in-process dict, used in tests.
* :class:`MySQLSourceRepo` — real MySQL backed (M1 production).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from typing import Any

from app.api.models import Alarm, Source, Task, _ts


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


class AlarmRepo(ABC):
    @abstractmethod
    def create(self, alarm: Alarm) -> Alarm | None:
        """Insert an alarm. Return None when ``event_id`` already exists."""

    @abstractmethod
    def get(self, alarm_id: str) -> Alarm | None: ...

    @abstractmethod
    def list(self, limit: int = 50) -> list[Alarm]: ...


class InMemoryAlarmRepo(AlarmRepo):
    def __init__(self) -> None:
        self._store: dict[str, Alarm] = {}
        self._seen_events: set[str] = set()

    def create(self, alarm: Alarm) -> Alarm | None:
        if alarm.event_id in self._seen_events:
            return None
        self._seen_events.add(alarm.event_id)
        if not alarm.id:
            alarm.id = uuid.uuid4().hex
        alarm.created_at = _ts()
        self._store[alarm.id] = alarm
        return alarm

    def get(self, alarm_id: str) -> Alarm | None:
        return self._store.get(alarm_id)

    def list(self, limit: int = 50) -> list[Alarm]:
        ordered = sorted(self._store.values(), key=lambda a: a.ts_ms, reverse=True)
        return ordered[:limit]


class MySQLAlarmRepo(AlarmRepo):
    """Real MySQL implementation. ``event_id`` is UNIQUE so a duplicate insert
    raises IntegrityError, which we treat as "already recorded" -> None."""

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

    @staticmethod
    def _from_row(row) -> Alarm:
        return Alarm(
            event_id=row[1], task_id=row[2], rule_id=row[3], class_name=row[4],
            score=float(row[5]), bbox=row[6], roi=row[7], mode=row[8],
            vlm_status=row[9], vlm_reason=row[10], vlm_confidence=float(row[11]),
            screenshot_object=row[12], ts_ms=int(row[13]), id=row[0], created_at=row[14],
        )

    def create(self, alarm: Alarm) -> Alarm | None:
        import pymysql

        conn = self._connect()
        if not alarm.id:
            alarm.id = uuid.uuid4().hex
        alarm.created_at = _ts()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO alarms (id, event_id, task_id, rule_id, class, score, bbox, roi, "
                    "mode, vlm_status, vlm_reason, vlm_confidence, screenshot_object, ts_ms, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (alarm.id, alarm.event_id, alarm.task_id, alarm.rule_id, alarm.class_name,
                     alarm.score, alarm.bbox, alarm.roi, alarm.mode, alarm.vlm_status,
                     alarm.vlm_reason, alarm.vlm_confidence, alarm.screenshot_object,
                     alarm.ts_ms, alarm.created_at),
                )
                conn.commit()
        except pymysql.err.IntegrityError:
            conn.rollback()
            return None
        return alarm

    def get(self, alarm_id: str) -> Alarm | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, event_id, task_id, rule_id, class, score, bbox, roi, mode, "
                "vlm_status, vlm_reason, vlm_confidence, screenshot_object, ts_ms, created_at "
                "FROM alarms WHERE id=%s", (alarm_id,))
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def list(self, limit: int = 50) -> list[Alarm]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, event_id, task_id, rule_id, class, score, bbox, roi, mode, "
                "vlm_status, vlm_reason, vlm_confidence, screenshot_object, ts_ms, created_at "
                "FROM alarms ORDER BY ts_ms DESC LIMIT %s", (int(limit),))
            return [self._from_row(row) for row in cur.fetchall()]
