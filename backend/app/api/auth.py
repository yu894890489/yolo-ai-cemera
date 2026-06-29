"""Authentication + business_line resolution middleware (YU-58 二期 Stage1).

The middleware resolves the caller's ``business_line`` and stores it on
``flask.g`` so blueprints can thread it into every repo query. Two resolution
paths, in order:

1. ``Authorization: Bearer <token>`` — token is the user id; the UserRepo is
   consulted and the user's ``business_line`` wins.
2. ``X-Business-Line: <name>`` — convenience header for tests and internal
   scripts. Only honored when ``trust_business_line_header=True`` (default off
   in production).

When neither path matches and ``require_auth=False`` (the phase1-compat
default), the request runs as the default business_line (``phase1``) so
existing curl calls and worker-side tests keep working. With
``require_auth=True`` the request is rejected with 401.

Login is exposed at ``POST /api/auth/login`` with ``{username, password}``;
the response carries ``{token, business_line}`` where ``token`` is the user id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from flask import Blueprint, g, jsonify, request

from app.api.models import DEFAULT_BUSINESS_LINE, User
from app.api.repository import UserRepo

logger = logging.getLogger(__name__)


@dataclass
class AuthConfig:
    require_auth: bool = False
    trust_business_line_header: bool = False
    default_business_line: str = DEFAULT_BUSINESS_LINE


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def init_auth(app, user_repo: UserRepo | None, cfg: AuthConfig | None = None) -> None:
    """Register a before_request hook that resolves ``g.user`` and
    ``g.business_line``. Skip auth entirely on healthz / metrics / login."""
    cfg = cfg or AuthConfig()
    app.config["AUTH_CONFIG"] = cfg
    app.config["USER_REPO"] = user_repo

    skip_paths = {"/healthz", "/metrics", "/api/auth/login"}

    @app.before_request
    def _resolve_user():
        from flask import request as _req

        if _req.path in skip_paths:
            return None

        token = _bearer_token()
        if token is not None and user_repo is not None:
            user = user_repo.get_by_id(token)
            if user is not None and user.enabled:
                g.user = user
                g.business_line = user.business_line
                return None
            # token present but invalid → treat as unauthenticated
            if cfg.require_auth:
                return jsonify({"error": "invalid token"}), 401

        if cfg.trust_business_line_header:
            bl = _req.headers.get("X-Business-Line", "").strip()
            if bl:
                g.business_line = bl
                return None

        if cfg.require_auth:
            return jsonify({"error": "authentication required"}), 401

        g.business_line = cfg.default_business_line
        return None


def current_business_line() -> str:
    """Read the resolved business_line for this request. Falls back to the
    phase1 default if the middleware never ran (e.g. tests wiring a blueprint
    without ``init_auth``)."""
    bl = getattr(g, "business_line", None)
    return bl or DEFAULT_BUSINESS_LINE


def make_auth_blueprint(user_repo: UserRepo) -> Blueprint:
    bp = Blueprint("auth", __name__)

    @bp.post("/auth/login")
    def login():
        data: dict[str, Any] = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify({"error": "username and password are required"}), 422
        user: User | None = user_repo.authenticate(username, password)
        if user is None:
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify({"token": user.id, "business_line": user.business_line})

    return bp


__all__ = ["AuthConfig", "init_auth", "current_business_line", "make_auth_blueprint"]
