"""YU-58 Stage1: UserRepo + password helpers."""

from __future__ import annotations

import pytest

from app.api.models import User
from app.api.repository import (
    InMemoryUserRepo,
    MySQLUserRepo,
    hash_password,
    verify_password,
)


class TestPasswordHelpers:
    def test_hash_is_deterministic(self):
        assert hash_password("hunter2") == hash_password("hunter2")

    def test_different_passwords_hash_differently(self):
        assert hash_password("hunter2") != hash_password("hunter3")

    def test_verify_password_accepts_correct_password(self):
        h = hash_password("hunter2")
        assert verify_password("hunter2", h) is True

    def test_verify_password_rejects_wrong_password(self):
        h = hash_password("hunter2")
        assert verify_password("hunter3", h) is False

    def test_verify_password_rejects_empty_hash(self):
        assert verify_password("anything", "") is False


class TestInMemoryUserRepo:
    def _user(self, username="alice", password="secret", business_line="phase1"):
        return User(
            username=username,
            password_hash=hash_password(password),
            business_line=business_line,
        )

    def test_create_assigns_id(self):
        repo = InMemoryUserRepo()
        user = repo.create(self._user())
        assert user.id
        assert repo.get_by_id(user.id) is user

    def test_create_duplicate_username_raises(self):
        repo = InMemoryUserRepo()
        repo.create(self._user(username="alice"))
        with pytest.raises(ValueError):
            repo.create(self._user(username="alice"))

    def test_get_by_username(self):
        repo = InMemoryUserRepo()
        user = repo.create(self._user(username="alice"))
        assert repo.get_by_username("alice") is user
        assert repo.get_by_username("nobody") is None

    def test_authenticate_returns_user_on_correct_password(self):
        repo = InMemoryUserRepo()
        created = repo.create(self._user(username="alice", password="secret"))
        assert repo.authenticate("alice", "secret") is created

    def test_authenticate_returns_none_on_wrong_password(self):
        repo = InMemoryUserRepo()
        repo.create(self._user(username="alice", password="secret"))
        assert repo.authenticate("alice", "wrong") is None

    def test_authenticate_returns_none_for_unknown_user(self):
        repo = InMemoryUserRepo()
        assert repo.authenticate("ghost", "anything") is None

    def test_authenticate_returns_none_for_disabled_user(self):
        repo = InMemoryUserRepo()
        user = self._user(username="alice", password="secret")
        user.enabled = False
        repo.create(user)
        assert repo.authenticate("alice", "secret") is None


class TestMySQLUserRepo:
    def test_create_duplicate_username_raises(self):
        repo = MySQLUserRepo({})

        class _Err(Exception):
            def __init__(self, code, msg):
                super().__init__(msg)
                self.args = (code, msg)

        class _Cur:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                raise _Err(1062, "Duplicate entry")

        class _Conn:
            def cursor(self):
                return _Cur()

            def commit(self):
                pass

        repo._connect = lambda: _Conn()

        import pymysql.err
        # simulate the real IntegrityError shape so _is_duplicate_key matches
        def raise_dup():
            raise pymysql.err.IntegrityError(1062, "Duplicate entry")

        # patch _connect's cursor to raise the real IntegrityError
        class _Cur2:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, sql, params=None):
                raise_dup()

        class _Conn2:
            def cursor(self):
                return _Cur2()

            def commit(self):
                pass

        repo._connect = lambda: _Conn2()

        with pytest.raises(ValueError):
            repo.create(User(username="dup", password_hash="x"))
