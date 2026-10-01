"""Export the live API's responses as static JSON files for a frozen Netlify demo.

Not part of the test suite or the runtime app -- a one-off build script. Run it
from the repo root again (`uv run python scripts/build_static_demo.py`)
whenever you want to refresh the demo's baked-in snapshot (e.g. after
re-running `just all` and `just scenario ...` against updated data).

Hits the real FastAPI routes in-process via httpx's ASGI transport, so the
static JSON is guaranteed byte-for-byte identical to what the live API would
return for the current on-disk data/processed/ state -- no reimplementation
of the join logic in app.py, no risk of static/live drift.
"""

import asyncio
import datetime
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient

from src.config import REPO_ROOT
from src.serve.app import create_app

STATIC_SRC = REPO_ROOT / "src" / "serve" / "static"
DEMO_DIR = REPO_ROOT / "static-site"

ROUTES = ["/api/branches", "/api/communities", "/api/network", "/api/diff"]


async def export() -> None:
    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    DEMO_DIR.mkdir(parents=True)
    (DEMO_DIR / "api").mkdir()

    # index.html references these as /static/app.js and /static/style.css
    # (matching FastAPI's StaticFiles mount) -- mirror that exact layout here
    # so the HTML needs no path rewriting.
    (DEMO_DIR / "static").mkdir()
    shutil.copy(STATIC_SRC / "app.js", DEMO_DIR / "static" / "app.js")
    shutil.copy(STATIC_SRC / "style.css", DEMO_DIR / "static" / "style.css")

    # Static-demo-only banner, inserted into the copy -- never touches the
    # live app's index.html. Frozen snapshots should say so, matching this
    # project's own provenance/honesty principle (estimated fields, backend
    # provenance in the header, etc.) -- a visitor shouldn't mistake this for
    # a live, perturbable instance.
    html = (STATIC_SRC / "index.html").read_text()
    snapshot_at = datetime.datetime.now().isoformat(timespec="minutes")
    banner = (
        f'<div id="static-demo-banner" style="background:#b36b00;color:#fff;'
        f'padding:0.4rem 1rem;font-size:0.85rem;text-align:center;">'
        f"Frozen static demo — snapshot taken {snapshot_at}. "
        f"No live backend: perturbation/scenario runs aren't interactive here. "
        f'See <a href="https://github.com/thenomadlad/2pz-ai-case-study" '
        f'style="color:#fff;">the repo</a> to run it live.</div>'
    )
    html = html.replace("<body>", f"<body>\n    {banner}", 1)
    (DEMO_DIR / "index.html").write_text(html)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://static-export") as client:
        for route in ROUTES:
            resp = await client.get(route)
            resp.raise_for_status()
            # Served at the exact same path the frontend already fetches (no
            # extension), so app.js needs zero changes and no Netlify
            # redirect rules are required -- Netlify serves static files by
            # exact path match.
            out_path = DEMO_DIR / route.lstrip("/")
            out_path.write_bytes(resp.content)
            print(f"wrote {out_path.relative_to(REPO_ROOT)} ({len(resp.content)} bytes)")

    print(f"\nStatic demo exported to {DEMO_DIR.relative_to(REPO_ROOT)}/")


if __name__ == "__main__":
    asyncio.run(export())
