"""Video source API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flask import Blueprint, jsonify, request

from app.api.auth import current_business_line
from app.api.models import Source
from app.api.repository import SourceRepo


def _error(message: str, status: int = 422):
    return jsonify({"error": message}), status


def _require_text(data: dict[str, Any], field: str) -> str | None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _source_from_payload(data: dict[str, Any], existing: Source | None = None) -> tuple[Source | None, str | None]:
    name = _require_text(data, "name")
    protocol = _require_text(data, "protocol")
    address = _require_text(data, "address")
    if name is None:
        return None, "name is required"
    if protocol is None:
        return None, "protocol is required"
    if address is None:
        return None, "address is required"
    enabled = data.get("enabled", True if existing is None else existing.enabled)
    if not isinstance(enabled, bool):
        return None, "enabled must be boolean"
    note = data.get("note", "" if existing is None else existing.note)
    if note is None:
        note = ""
    if not isinstance(note, str):
        return None, "note must be string"
    source = existing or Source()
    source.name = name
    source.protocol = protocol
    source.address = address
    source.enabled = enabled
    source.note = note
    return source, None


def _to_json(source: Source) -> dict[str, Any]:
    return asdict(source)


def make_sources_blueprint(repo: SourceRepo) -> Blueprint:
    bp = Blueprint("sources", __name__)

    @bp.post("/sources")
    def create_source():
        data = request.get_json(silent=True) or {}
        source, err = _source_from_payload(data)
        if err:
            return _error(err)
        assert source is not None
        source.business_line = current_business_line()
        return jsonify(_to_json(repo.create(source))), 201

    @bp.get("/sources")
    def list_sources():
        return jsonify([_to_json(s) for s in repo.list(business_line=current_business_line())])

    @bp.get("/sources/<source_id>")
    def get_source(source_id: str):
        source = repo.get(source_id, business_line=current_business_line())
        if source is None:
            return _error("source not found", 404)
        return jsonify(_to_json(source))

    @bp.put("/sources/<source_id>")
    def update_source(source_id: str):
        existing = repo.get(source_id, business_line=current_business_line())
        if existing is None:
            return _error("source not found", 404)
        source, err = _source_from_payload(request.get_json(silent=True) or {}, existing)
        if err:
            return _error(err)
        assert source is not None
        source.business_line = existing.business_line
        updated = repo.update(source, business_line=current_business_line())
        if updated is None:
            return _error("source not found", 404)
        return jsonify(_to_json(updated))

    @bp.delete("/sources/<source_id>")
    def delete_source(source_id: str):
        if not repo.delete(source_id, business_line=current_business_line()):
            return _error("source not found", 404)
        return "", 204

    return bp
