"""TDD for app.api.web: server-rendered frontend pages from the Vite manifest."""

from app.api.web import render_page, PAGES


_MANIFEST = {
    "entries/alarm-list.ts": {
        "file": "assets/alarm-list.abc123.js",
        "css": ["assets/alarm-list.def456.css"],
        "isEntry": True,
    },
    "entries/task-create.ts": {
        "file": "assets/task-create.aaa.js",
        "isEntry": True,
    },
}


def test_render_page_injects_hashed_entry_script():
    html = render_page(
        _MANIFEST, "entries/alarm-list.ts", title="告警", meta={}, static_prefix="/static/frontend"
    )
    assert '<script type="module" src="/static/frontend/assets/alarm-list.abc123.js">' in html
    assert "<title>告警</title>" in html
    assert '<main id="app"></main>' in html


def test_render_page_injects_css_links():
    html = render_page(_MANIFEST, "entries/alarm-list.ts", title="t", meta={})
    assert '<link rel="stylesheet" href="/static/frontend/assets/alarm-list.def456.css">' in html


def test_render_page_handles_entry_without_css():
    html = render_page(_MANIFEST, "entries/task-create.ts", title="t", meta={})
    assert "assets/task-create.aaa.js" in html
    assert "stylesheet" not in html


def test_render_page_injects_meta_tags():
    html = render_page(
        _MANIFEST,
        "entries/task-create.ts",
        title="t",
        meta={"api-base": "http://192.168.10.83:8010", "minio-base": "http://192.168.10.83:19000"},
    )
    assert '<meta name="api-base" content="http://192.168.10.83:8010">' in html
    assert '<meta name="minio-base" content="http://192.168.10.83:19000">' in html


def test_render_page_escapes_meta_content():
    html = render_page(_MANIFEST, "entries/task-create.ts", title="t", meta={"api-base": '"><x'})
    assert '"><x' not in html
    assert "&quot;&gt;&lt;x" in html


def test_render_page_missing_entry_raises_keyerror():
    try:
        render_page(_MANIFEST, "entries/does-not-exist.ts", title="t", meta={})
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown entry")


def test_pages_map_covers_core_routes():
    routes = {p["route"] for p in PAGES}
    assert {"/", "/tasks/new", "/monitor", "/alarms"} <= routes
