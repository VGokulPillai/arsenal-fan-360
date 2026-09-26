"""Arsenal Fan 360 - FastAPI application (Databricks App)."""
import os, logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.routes import api as api_routes
from server import store, db, config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arsenal_fan_360")

app = FastAPI(title="Arsenal Fan 360", description="Turn supporter signals into the next best action.", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(api_routes.router, prefix="/api")


@app.on_event("startup")
def _startup():
    try:
        store.init()
    except Exception as e:
        logger.exception("store init failed: %s", e)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": "arsenal-fan-360",
        "data_source": store.source(),
        "lakebase": db.available(),
        "supporters_loaded": len(store._profiles),
    }


# ---- serve React frontend ----
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend_dist")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")
logger.info("Frontend dir: %s (exists=%s)", frontend_dir, os.path.exists(frontend_dir))

if os.path.exists(frontend_dir):
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    images_dir = os.path.join(frontend_dir, "images")
    if os.path.exists(images_dir):
        app.mount("/images", StaticFiles(directory=images_dir), name="images")

    @app.get("/")
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str = ""):
        if full_path.startswith(("api/", "assets/", "images/")):
            raise HTTPException(404, "Not found")
        index = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index):
            return FileResponse(index, media_type="text/html",
                                headers={"Cache-Control": "no-store, max-age=0"})
        return {"message": "Frontend not built. Run: cd frontend && npm run build"}
