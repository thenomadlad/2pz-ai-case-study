import datetime
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.config import Settings, settings as default_settings

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def _load(name: str):
        return json.loads((settings.processed_dir / name).read_text())

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/branches")
    def branches():
        features = _load("branch_features.json")["branches"]
        decisions = {d["branch_id"]: d for d in _load("decisions.json")}
        return [{**f, **decisions.get(f["branch_id"], {})} for f in features]

    @app.get("/api/communities")
    def communities():
        assignments = _load("community_assignment.json")
        raw_communities = {c["id"]: c for c in _load("communities.json")}
        merged = []
        for a in assignments:
            c = raw_communities.get(a["community_id"], {})
            merged.append({
                **a,
                "lat": c.get("lat"),
                "lng": c.get("lng"),
                "name_en": c.get("name_en"),
                "is_estimated": c.get("is_estimated"),
            })
        return merged

    @app.get("/api/network")
    def network():
        payload = _load("branch_features.json")
        mtime = (settings.processed_dir / "branch_features.json").stat().st_mtime
        run_meta_path = settings.processed_dir / "run_meta.json"
        if run_meta_path.exists():
            model_backend = json.loads(run_meta_path.read_text())["model_backend"]
        else:
            model_backend = settings.model_backend
        return {
            "stats": payload["network"],
            "model_backend": model_backend,
            "data_sources": {
                "branches": "seed" if not settings.enable_scrape else "seed (scrape unimplemented)",
                "communities": "seed" if not settings.dubai_pulse_enabled
                                else "seed (pulse unimplemented)",
            },
            "pipeline_run_at": datetime.datetime.fromtimestamp(mtime).isoformat(),
        }

    return app


app = create_app()
