"""Server-rendered frontend pages (BE-M1-D / YU-56).

The Vite build emits hashed JS/CSS bundles + ``manifest.json`` into
``app/static/frontend/`` (served by Flask at ``/static/frontend/``), but no HTML
— so Flask renders minimal page shells that load the correct hashed entry and
inject runtime config as ``<meta>`` tags (api-base / minio-base), which the
frontend reads in app/api/bootstrap.ts. This removes the need for ``pnpm preview``.
"""

from __future__ import annotations

import json
import logging
import os
from html import escape
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, abort

logger = logging.getLogger(__name__)

# route -> entry (manifest key under Vite root 'src') + page <title>.
PAGES: list[dict[str, str]] = [
    {"route": "/", "entry": "entries/task-create.ts", "title": "创建分析任务 · YOLO-VLM"},
    {"route": "/tasks/new", "entry": "entries/task-create.ts", "title": "创建分析任务 · YOLO-VLM"},
    {"route": "/monitor", "entry": "entries/monitor-preview.ts", "title": "监控预览 · YOLO-VLM"},
    {"route": "/alarms", "entry": "entries/alarm-list.ts", "title": "实时告警 · YOLO-VLM"},
]


def render_page(
    manifest: dict[str, Any],
    entry: str,
    *,
    title: str,
    meta: dict[str, str],
    static_prefix: str = "/static/frontend",
) -> str:
    """Build an HTML shell for ``entry`` using the Vite manifest. Raises
    ``KeyError`` if the entry is not present (build missing/stale)."""
    record = manifest[entry]
    prefix = static_prefix.rstrip("/")
    css_links = "".join(
        f'<link rel="stylesheet" href="{prefix}/{href}">' for href in record.get("css", [])
    )
    meta_tags = "".join(
        f'<meta name="{escape(name, quote=True)}" content="{escape(value, quote=True)}">'
        for name, value in meta.items()
    )
    script = f'<script type="module" src="{prefix}/{record["file"]}"></script>'
    return (
        "<!DOCTYPE html>"
        '<html lang="zh-CN"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"{meta_tags}"
        f"<title>{escape(title)}</title>"
        f"{css_links}"
        "</head><body>"
        '<main id="app"></main>'
        f"{script}"
        "</body></html>"
    )


def _runtime_meta() -> dict[str, str]:
    """Runtime config injected into every page, from env (see bootstrap.ts)."""
    meta: dict[str, str] = {}
    api_base = os.environ.get("FRONTEND_API_BASE", "")
    if api_base:
        meta["api-base"] = api_base
    meta["minio-base"] = os.environ.get(
        "FRONTEND_MINIO_BASE", "http://192.168.10.83:19000"
    )
    if os.environ.get("FRONTEND_API_MOCK") == "1":
        meta["api-mock"] = "1"
    return meta


def _load_manifest(static_root: Path) -> dict[str, Any] | None:
    path = static_root / "frontend" / "manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("frontend manifest missing at %s; pages will 503", path)
        return None
    except Exception:
        logger.exception("failed to parse frontend manifest at %s", path)
        return None


def make_web_blueprint(static_root: Path) -> Blueprint:
    bp = Blueprint("web", __name__)

    def _make_view(entry: str, title: str):
        def view():
            manifest = _load_manifest(static_root)
            if manifest is None:
                abort(503, "frontend not built")
            meta = _runtime_meta()
            try:
                html = render_page(manifest, entry, title=title, meta=meta)
            except KeyError:
                abort(503, f"frontend entry not built: {entry}")
            return Response(html, mimetype="text/html")

        return view

    for page in PAGES:
        bp.add_url_rule(
            page["route"],
            endpoint=f"page_{page['route']}",
            view_func=_make_view(page["entry"], page["title"]),
        )
    return bp
