from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.assets import router as assets_router
from backend.app.db.session import Base, engine
from backend.app.models.assets import Asset


# ============================================================
# DATABASE
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Asset & Warranty Vault",
    description=(
        "Digital asset, receipt, warranty "
        "and maintenance management system."
    ),
    version="0.1.0"
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(assets_router)


# ============================================================
# FRONTEND
# ============================================================

FRONTEND_DIR = Path("frontend")


app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


@app.get("/", include_in_schema=False)
def serve_frontend():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    return {
        "status": "healthy"
    }