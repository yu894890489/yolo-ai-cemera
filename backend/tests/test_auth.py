"""YU-58 Stage1: auth middleware + business_line resolution."""

from __future__ import annotations

import json

import pytest
from flask import Flask

from app.api.auth import AuthConfig, init_auth, make_auth_blueprint
from app.api.models import Source, User
from app.api.repository import (
    InMemorySourceRepo,
    InMemoryUserRepo,
    hash_password,
)
from app.api.sources import make_sources_blueprint


def _make_app(user_repo, auth_cfg, source_repo):
    app = Flask(__name__)
    app.config["TESTING"] = True
    init_auth(app, user_repo, auth_cfg)
    app.register_blueprint(make_auth_blueprint(user_repo), url_prefix="/api")
    app.register_blueprint(make_sources_blueprint(source_repo), url_prefix="/api")
    return app


@pytest.fixture
def user_repo():
    repo = InMemoryUserRepo()
    repo.create(User(
        username="alice",
        password_hash=hash_password("secret"),
        business_line="phase1",
    ))
    repo.create(User(
        username="bob",
        password_hash=hash_password("secret"),
        business_line="phase2",
    ))
    return repo


@pytest.fixture
def source_repo():
    repo = InMemorySourceRepo()
    repo.create(Source(name="p1-cam", protocol="rtsp", address="rtsp://x", business_line="phase1"))
    repo.create(Source(name="p2-cam", protocol="rtsp", address="rtsp://y", business_line="phase2"))
    return repo


class TestAuthDefault:
    def test_no_auth_defaults_to_phase1(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        with app.test_client() as c:
            resp = c.get("/api/sources")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.get_json()]
        assert names == ["p1-cam"]

    def test_bearer_token_resolves_user_business_line(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        alice = user_repo.get_by_username("alice")
        bob = user_repo.get_by_username("bob")
        with app.test_client() as c:
            phase1 = c.get("/api/sources", headers={"Authorization": f"Bearer {alice.id}"})
            phase2 = c.get("/api/sources", headers={"Authorization": f"Bearer {bob.id}"})
        assert [s["name"] for s in phase1.get_json()] == ["p1-cam"]
        assert [s["name"] for s in phase2.get_json()] == ["p2-cam"]

    def test_invalid_token_returns_401_when_required(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(require_auth=True), source_repo)
        with app.test_client() as c:
            resp = c.get("/api/sources", headers={"Authorization": "Bearer not-a-user"})
        assert resp.status_code == 401

    def test_no_token_returns_401_when_required(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(require_auth=True), source_repo)
        with app.test_client() as c:
            resp = c.get("/api/sources")
        assert resp.status_code == 401

    def test_invalid_token_falls_through_to_default_when_not_required(
        self, user_repo, source_repo
    ):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        with app.test_client() as c:
            resp = c.get("/api/sources", headers={"Authorization": "Bearer ghost"})
        assert resp.status_code == 200
        assert [s["name"] for s in resp.get_json()] == ["p1-cam"]


class TestAuthHeaderOverride:
    def test_business_line_header_trusted_when_enabled(self, user_repo, source_repo):
        app = _make_app(
            user_repo, AuthConfig(trust_business_line_header=True), source_repo
        )
        with app.test_client() as c:
            resp = c.get("/api/sources", headers={"X-Business-Line": "phase2"})
        assert resp.status_code == 200
        assert [s["name"] for s in resp.get_json()] == ["p2-cam"]

    def test_business_line_header_ignored_when_not_enabled(self, user_repo, source_repo):
        app = _make_app(
            user_repo, AuthConfig(trust_business_line_header=False), source_repo
        )
        with app.test_client() as c:
            resp = c.get("/api/sources", headers={"X-Business-Line": "phase2"})
        assert resp.status_code == 200
        # defaults to phase1
        assert [s["name"] for s in resp.get_json()] == ["p1-cam"]


class TestLogin:
    def test_login_returns_token_and_business_line(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        with app.test_client() as c:
            resp = c.post(
                "/api/auth/login",
                data=json.dumps({"username": "alice", "password": "secret"}),
                content_type="application/json",
            )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["token"] == user_repo.get_by_username("alice").id
        assert body["business_line"] == "phase1"

    def test_login_rejects_bad_credentials(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        with app.test_client() as c:
            resp = c.post(
                "/api/auth/login",
                data=json.dumps({"username": "alice", "password": "wrong"}),
                content_type="application/json",
            )
        assert resp.status_code == 401

    def test_login_rejects_missing_fields(self, user_repo, source_repo):
        app = _make_app(user_repo, AuthConfig(), source_repo)
        with app.test_client() as c:
            resp = c.post(
                "/api/auth/login",
                data=json.dumps({"username": "alice"}),
                content_type="application/json",
            )
        assert resp.status_code == 422


class TestWriteIsolation:
    def test_create_source_stamps_caller_business_line(self, user_repo, source_repo):
        app = _make_app(
            user_repo,
            AuthConfig(trust_business_line_header=True),
            source_repo,
        )
        with app.test_client() as c:
            resp = c.post(
                "/api/sources",
                data=json.dumps({"name": "new", "protocol": "rtsp", "address": "rtsp://x"}),
                content_type="application/json",
                headers={"X-Business-Line": "phase2"},
            )
            assert resp.status_code == 201
            new_id = resp.get_json()["id"]

        # phase1 caller cannot see it
        with app.test_client() as c:
            assert c.get(f"/api/sources/{new_id}").status_code == 404
        # phase2 caller can
        with app.test_client() as c:
            assert c.get(
                f"/api/sources/{new_id}", headers={"X-Business-Line": "phase2"}
            ).status_code == 200
