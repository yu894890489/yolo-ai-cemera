"""Data access layer for video sources, tasks, alarms, and users.

Two implementations per repo:

* :class:`InMemory*Repo` — in-process dict, used in tests.
* :class:`MySQL*Repo` — real MySQL backed (M1 production).

Every read method takes an optional ``business_line`` filter. The API layer
threads the caller's business_line through; workers / migrations pass ``None``
to see all rows. ``None`` means "no filter" — it does NOT mean phase1.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.api.models import DEFAULT_BUSINESS_LINE, Alarm, Source, Task, User


class SourceRepo(ABC):
    @abstractmethod
    def create(self, source: Source) -> Source: ...

    @abstractmethod
    def get(self, source_id: str, business_line: str | None = None) -> Source | None: ...

    @abstractmethod
    def list(self, business_line: str | None = None) -> list[Source]: ...

    @abstractmethod
    def update(self, source: Source, business_line: str | None = None) -> Source | None: ...

    @abstractmethod
    def delete(self, source_id: str, business_line: str | None = None) -> bool: ...


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

    def get(self, source_id: str, business_line: str | None = None) -> Source | None:
        src = self._store.get(source_id)
        if src is None:
            return None
        if business_line is not None and src.business_line != business_line:
            return None
        return src

    def list(self, business_line: str | None = None) -> list[Source]:
        if business_line is None:
            return list(self._store.values())
        return [s for s in self._store.values() if s.business_line == business_line]

    def update(self, source: Source, business_line: str | None = None) -> Source | None:
        existing = self._store.get(source.id)
        if existing is None:
            return None
        if business_line is not None and existing.business_line != business_line:
            return None
        source.updated_at = _ts()
        self._store[source.id] = source
        return source

    def delete(self, source_id: str, business_line: str | None = None) -> bool:
        existing = self._store.get(source_id)
        if existing is None:
            return False
        if business_line is not None and existing.business_line != business_line:
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
        # row order: id, name, protocol, address, enabled, note, business_line, created_at, updated_at
        return Source(
            id=row[0], name=row[1], protocol=row[2], address=row[3],
            enabled=bool(row[4]), note=row[5], business_line=row[6],
            created_at=row[7], updated_at=row[8],
        )

    _COLUMNS = (
        "id, name, protocol, address, enabled, note, business_line, created_at, updated_at"
    )

    def create(self, source: Source) -> Source:
        conn = self._connect()
        now = _ts()
        source.id = uuid.uuid4().hex[:12]
        source.created_at = now
        source.updated_at = now
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sources (id, name, protocol, address, enabled, note, business_line, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (source.id, source.name, source.protocol, source.address,
                 source.enabled, source.note, source.business_line,
                 source.created_at, source.updated_at),
            )
            conn.commit()
        return source

    def get(self, source_id: str, business_line: str | None = None) -> Source | None:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM sources WHERE id = %s", (source_id,)
                )
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM sources WHERE id = %s AND business_line = %s",
                    (source_id, business_line),
                )
            row = cur.fetchone()
            if row is None:
                return None
            return self._source_from_row(row)

    def list(self, business_line: str | None = None) -> list[Source]:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(f"SELECT {self._COLUMNS} FROM sources")
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM sources WHERE business_line = %s",
                    (business_line,),
                )
            return [self._source_from_row(row) for row in cur.fetchall()]

    def update(self, source: Source, business_line: str | None = None) -> Source | None:
        conn = self._connect()
        source.updated_at = _ts()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    "UPDATE sources SET name=%s, protocol=%s, address=%s, enabled=%s, "
                    "note=%s, business_line=%s, updated_at=%s WHERE id=%s",
                    (source.name, source.protocol, source.address, source.enabled,
                     source.note, source.business_line, source.updated_at, source.id),
                )
            else:
                cur.execute(
                    "UPDATE sources SET name=%s, protocol=%s, address=%s, enabled=%s, "
                    "note=%s, business_line=%s, updated_at=%s "
                    "WHERE id=%s AND business_line=%s",
                    (source.name, source.protocol, source.address, source.enabled,
                     source.note, source.business_line, source.updated_at,
                     source.id, business_line),
                )
            conn.commit()
            if cur.rowcount == 0:
                return None
            return source

    def delete(self, source_id: str, business_line: str | None = None) -> bool:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute("DELETE FROM sources WHERE id = %s", (source_id,))
            else:
                cur.execute(
                    "DELETE FROM sources WHERE id = %s AND business_line = %s",
                    (source_id, business_line),
                )
            conn.commit()
            return cur.rowcount > 0


class TaskRepo(ABC):
    @abstractmethod
    def create(self, task: Task) -> Task: ...

    @abstractmethod
    def get(self, task_id: str, business_line: str | None = None) -> Task | None: ...

    @abstractmethod
    def list(self, business_line: str | None = None) -> list[Task]: ...

    @abstractmethod
    def update(self, task: Task, business_line: str | None = None) -> Task | None: ...


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

    def get(self, task_id: str, business_line: str | None = None) -> Task | None:
        t = self._store.get(task_id)
        if t is None:
            return None
        if business_line is not None and t.business_line != business_line:
            return None
        return t

    def list(self, business_line: str | None = None) -> list[Task]:
        if business_line is None:
            return list(self._store.values())
        return [t for t in self._store.values() if t.business_line == business_line]

    def update(self, task: Task, business_line: str | None = None) -> Task | None:
        existing = self._store.get(task.id)
        if existing is None:
            return None
        if business_line is not None and existing.business_line != business_line:
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

    _COLUMNS = (
        "id, source_id, algorithm_id, roi, prompt, confidence, status, "
        "error_message, business_line, created_at, updated_at"
    )

    def create(self, task: Task) -> Task:
        conn = self._connect()
        now = _ts()
        task.id = uuid.uuid4().hex[:12]
        task.created_at = now
        task.updated_at = now
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (id, source_id, algorithm_id, roi, prompt, confidence, "
                "status, error_message, business_line, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (task.id, task.source_id, task.algorithm_id, task.roi, task.prompt,
                 task.confidence, task.status, task.error_message, task.business_line,
                 task.created_at, task.updated_at),
            )
            conn.commit()
        return task

    def _task_from_row(self, row) -> Task:
        return Task(
            id=row[0], source_id=row[1], algorithm_id=row[2], roi=row[3],
            prompt=row[4], confidence=float(row[5]), status=row[6],
            error_message=row[7], business_line=row[8],
            created_at=row[9], updated_at=row[10],
        )

    def get(self, task_id: str, business_line: str | None = None) -> Task | None:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM tasks WHERE id=%s", (task_id,)
                )
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM tasks WHERE id=%s AND business_line=%s",
                    (task_id, business_line),
                )
            row = cur.fetchone()
            return self._task_from_row(row) if row else None

    def list(self, business_line: str | None = None) -> list[Task]:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(f"SELECT {self._COLUMNS} FROM tasks")
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM tasks WHERE business_line=%s",
                    (business_line,),
                )
            return [self._task_from_row(row) for row in cur.fetchall()]

    def update(self, task: Task, business_line: str | None = None) -> Task | None:
        conn = self._connect()
        task.updated_at = _ts()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    "UPDATE tasks SET source_id=%s, algorithm_id=%s, roi=%s, prompt=%s, "
                    "confidence=%s, status=%s, error_message=%s, business_line=%s, "
                    "updated_at=%s WHERE id=%s",
                    (task.source_id, task.algorithm_id, task.roi, task.prompt,
                     task.confidence, task.status, task.error_message,
                     task.business_line, task.updated_at, task.id),
                )
            else:
                cur.execute(
                    "UPDATE tasks SET source_id=%s, algorithm_id=%s, roi=%s, prompt=%s, "
                    "confidence=%s, status=%s, error_message=%s, business_line=%s, "
                    "updated_at=%s WHERE id=%s AND business_line=%s",
                    (task.source_id, task.algorithm_id, task.roi, task.prompt,
                     task.confidence, task.status, task.error_message,
                     task.business_line, task.updated_at, task.id, business_line),
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
    def get(self, alarm_id: str, business_line: str | None = None) -> Alarm | None: ...

    @abstractmethod
    def list(
        self, limit: int = 50, business_line: str | None = None
    ) -> list[Alarm]: ...


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

    def get(self, alarm_id: str, business_line: str | None = None) -> Alarm | None:
        a = self._store.get(alarm_id)
        if a is None:
            return None
        if business_line is not None and a.business_line != business_line:
            return None
        return a

    def list(self, limit: int = 50, business_line: str | None = None) -> list[Alarm]:
        rows = self._store.values()
        if business_line is not None:
            rows = [a for a in rows if a.business_line == business_line]
        ordered = sorted(rows, key=lambda a: a.ts_ms, reverse=True)
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

    _COLUMNS = (
        "id, event_id, task_id, rule_id, class, score, bbox, roi, mode, "
        "vlm_status, vlm_reason, vlm_confidence, screenshot_object, ts_ms, "
        "business_line, created_at"
    )

    @staticmethod
    def _from_row(row) -> Alarm:
        return Alarm(
            id=row[0], event_id=row[1], task_id=row[2], rule_id=row[3],
            class_name=row[4], score=float(row[5]), bbox=row[6], roi=row[7],
            mode=row[8], vlm_status=row[9], vlm_reason=row[10],
            vlm_confidence=float(row[11]), screenshot_object=row[12],
            ts_ms=int(row[13]), business_line=row[14], created_at=row[15],
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
                    "INSERT INTO alarms (id, event_id, task_id, rule_id, class, score, "
                    "bbox, roi, mode, vlm_status, vlm_reason, vlm_confidence, "
                    "screenshot_object, ts_ms, business_line, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (alarm.id, alarm.event_id, alarm.task_id, alarm.rule_id,
                     alarm.class_name, alarm.score, alarm.bbox, alarm.roi,
                     alarm.mode, alarm.vlm_status, alarm.vlm_reason,
                     alarm.vlm_confidence, alarm.screenshot_object, alarm.ts_ms,
                     alarm.business_line, alarm.created_at),
                )
                conn.commit()
        except pymysql.err.IntegrityError:
            conn.rollback()
            return None
        return alarm

    def get(self, alarm_id: str, business_line: str | None = None) -> Alarm | None:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM alarms WHERE id=%s", (alarm_id,)
                )
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM alarms WHERE id=%s AND business_line=%s",
                    (alarm_id, business_line),
                )
            row = cur.fetchone()
            return self._from_row(row) if row else None

    def list(self, limit: int = 50, business_line: str | None = None) -> list[Alarm]:
        conn = self._connect()
        with conn.cursor() as cur:
            if business_line is None:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM alarms ORDER BY ts_ms DESC LIMIT %s",
                    (int(limit),),
                )
            else:
                cur.execute(
                    f"SELECT {self._COLUMNS} FROM alarms WHERE business_line=%s "
                    "ORDER BY ts_ms DESC LIMIT %s",
                    (business_line, int(limit)),
                )
            return [self._from_row(row) for row in cur.fetchall()]


class UserRepo(ABC):
    """User accounts — drives the auth middleware's business_line resolution."""

    @abstractmethod
    def create(self, user: User) -> User:
        """Persist a new user. Raises if username already exists."""

    @abstractmethod
    def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    def list(self) -> list[User]: ...

    @abstractmethod
    def authenticate(self, username: str, password: str) -> User | None:
        """Return the user if the password verifies, else None."""


def hash_password(password: str, *, salt: str = "") -> str:
    """Deterministic salted SHA-256 hash.

    Production deployments should swap this for bcrypt/argon2; this module
    keeps the dependency surface minimal for the Stage1 skeleton. The salt
    argument lets callers mix in a per-deployment secret.
    """
    if not isinstance(password, str):
        raise TypeError("password must be str")
    h = hashlib.sha256()
    h.update(salt.encode("utf-8"))
    h.update(b":")
    h.update(password.encode("utf-8"))
    return f"sha256${h.hexdigest()}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    if not password_hash.startswith("sha256$"):
        return False
    _, digest = password_hash.split("$", 1)
    expected = hash_password(password).split("$", 1)[1]
    return hmac.compare_digest(digest, expected)


class InMemoryUserRepo(UserRepo):
    def __init__(self) -> None:
        self._store: dict[str, User] = {}
        self._by_username: dict[str, str] = {}

    def create(self, user: User) -> User:
        if not user.id:
            user.id = uuid.uuid4().hex
        if not user.created_at:
            user.created_at = _ts()
        if user.username in self._by_username:
            raise ValueError(f"username already exists: {user.username}")
        self._store[user.id] = user
        self._by_username[user.username] = user.id
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self._store.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        uid = self._by_username.get(username)
        return self._store.get(uid) if uid else None

    def list(self) -> list[User]:
        return list(self._store.values())

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get_by_username(username)
        if user is None or not user.enabled:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None


class MySQLUserRepo(UserRepo):
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

    _COLUMNS = "id, username, password_hash, business_line, enabled, created_at"

    def create(self, user: User) -> User:
        import pymysql

        conn = self._connect()
        if not user.id:
            user.id = uuid.uuid4().hex
        if not user.created_at:
            user.created_at = _ts()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (id, username, password_hash, business_line, enabled, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user.id, user.username, user.password_hash,
                     user.business_line, 1 if user.enabled else 0, user.created_at),
                )
                conn.commit()
        except pymysql.err.IntegrityError as exc:
            if _is_duplicate_key(exc):
                raise ValueError(f"username already exists: {user.username}") from exc
            raise
        return user

    def _user_from_row(self, row) -> User:
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            business_line=row[3], enabled=bool(row[4]), created_at=row[5],
        )

    def get_by_id(self, user_id: str) -> User | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLUMNS} FROM users WHERE id=%s", (user_id,)
            )
            row = cur.fetchone()
            return self._user_from_row(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {self._COLUMNS} FROM users WHERE username=%s", (username,)
            )
            row = cur.fetchone()
            return self._user_from_row(row) if row else None

    def list(self) -> list[User]:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(f"SELECT {self._COLUMNS} FROM users")
            return [self._user_from_row(row) for row in cur.fetchall()]

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get_by_username(username)
        if user is None or not user.enabled:
            return None
        if verify_password(password, user.password_hash):
            return user
        return None


def _is_duplicate_key(exc: Exception) -> bool:
    code = getattr(exc, "args", None)
    if code and isinstance(code, tuple) and code and isinstance(code[0], int):
        return code[0] == 1062  # ER_DUP_ENTRY
    return False


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "DEFAULT_BUSINESS_LINE",
    "AlarmRepo",
    "InMemoryAlarmRepo",
    "MySQLAlarmRepo",
    "SourceRepo",
    "InMemorySourceRepo",
    "MySQLSourceRepo",
    "TaskRepo",
    "InMemoryTaskRepo",
    "MySQLTaskRepo",
    "UserRepo",
    "InMemoryUserRepo",
    "MySQLUserRepo",
    "User",
    "hash_password",
    "verify_password",
]
