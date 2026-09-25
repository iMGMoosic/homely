"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from homely import __version__
from homely.web.errors import install_error_handlers
from homely.web.routers import geocode, modules, settings, system, transit, ws_events, ws_preview

if TYPE_CHECKING:
    from homely.app import Runtime

STATIC_DIR = Path(__file__).parent / "static"

FALLBACK_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>homely</title>
<style>body{font-family:system-ui;background:#0f1117;color:#e6e6e6;display:grid;place-items:center;height:100vh;margin:0}
main{max-width:34rem;padding:2rem;line-height:1.5}code{background:#1c2030;padding:.1rem .4rem;border-radius:4px}</style></head>
<body><main><h1>homely is running</h1><p>The web UI has not been built into this install.
From a source checkout run <code>make build-web</code> (or use a release wheel).</p>
<p>The API is available: <a href="/docs" style="color:#00a8ff">/docs</a>, <a href="/api/system" style="color:#00a8ff">/api/system</a>.</p></main></body></html>"""


def create_app(runtime: Runtime, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="homely", version=__version__, docs_url="/docs", redoc_url=None)
    app.state.runtime = runtime
    install_error_handlers(app)
    routers = (system, modules, settings, geocode, transit, ws_preview, ws_events)
    for r in routers:
        app.include_router(r.router)

    static = static_dir or STATIC_DIR
    if (static / "index.html").exists():
        app.mount("/", StaticFiles(directory=static, html=True), name="static")
    else:

        @app.get("/", include_in_schema=False, response_class=HTMLResponse)
        async def fallback() -> str:
            return FALLBACK_HTML

    return app
