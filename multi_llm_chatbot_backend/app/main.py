import os
from pathlib import Path

from app.core.env_loader import load_application_env

load_application_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# Load configuration FIRST so every module can use it
from app.config import load_settings
settings = load_settings()

# Import the new database functions
from app.core.database import connect_to_mongo, close_mongo_connection

# Import all route modules
from app.api.routes import router as main_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat_sessions import router as chat_sessions_router
from app.api.routes.phd_canvas import router as phd_canvas_router
from app.api.routes.user_profile import router as user_profile_router
from app.api.routes.onboarding import router as onboarding_router
from app.api.routes.journey import router as journey_router
from app.api.routes.user_knowledge import router as user_knowledge_router

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title=f"{settings.app.title} Backend",
    version="2.0.0",
    lifespan=lifespan
)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
cors_origins = [origin.strip() for origin in cors_origins]  # Clean whitespace

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(main_router)
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(chat_sessions_router, prefix="/api", tags=["chat-sessions"])
app.include_router(phd_canvas_router, prefix="/api", tags=["phd-canvas"])
app.include_router(user_profile_router, prefix="/api", tags=["user-profile"])
app.include_router(onboarding_router, prefix="/api", tags=["onboarding"])
app.include_router(journey_router, prefix="/api", tags=["journey"])
app.include_router(user_knowledge_router, prefix="/api", tags=["user-knowledge"])

# Serve bundled avatar images
_avatars_dir = Path(__file__).resolve().parent / "assets" / "avatars"
if _avatars_dir.is_dir():
    app.mount(
        "/api/avatars/bundled",
        StaticFiles(directory=_avatars_dir),
        name="bundled-avatars",
    )


# ---------------------------------------------------------------------------
# Public configuration endpoint — serves the frontend-safe subset
# ---------------------------------------------------------------------------
@app.get("/api/config")
def get_public_config():
    """Return the public (non-secret) application configuration."""
    return settings.get_frontend_config()


# ---------------------------------------------------------------------------
# Static SPA mount — Hugging Face Spaces / single-container deployment
# ---------------------------------------------------------------------------
# When the Docker build copies the React production bundle into ``./static``
# (sibling of this app/ directory), expose it at "/" so the API and the
# SPA share the FastAPI origin.
#
# IMPORTANT: Starlette matches path routes *before* mounts. Any ``GET /``
# API handler (see historical ``routes/root.py``) would shadow this SPA
# and make HF Spaces look like a bare JSON backend. Health lives at
# ``/health`` instead.
#
# In local API-only development the static dir is absent; ``/health`` and
# ``/docs`` remain available.
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_static_dir), html=True),
        name="spa",
    )
