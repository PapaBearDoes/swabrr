"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

FastAPI application entry point.
Manages application lifespan (startup/shutdown), database initialization,
and router registration.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.managers.logging_config_manager import create_logging_config_manager
from src.managers.db_manager import create_db_manager


# ---------------------------------------------------------------------------
# Logging (initialized immediately — Rule #9)
# ---------------------------------------------------------------------------
log_manager = create_logging_config_manager(component="swabbarr-api")
log = log_manager.get_logger("main")


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup and shutdown of shared resources."""

    # --- Startup ---
    log.info("Swabbarr API starting up")

    # Database
    db_manager = await create_db_manager(
        log=log_manager.get_logger("db_manager"),
    )
    application.state.db_manager = db_manager
    log.success("Database manager ready")

    # TODO Phase 2: Initialize API clients (Tautulli, Seerr, Radarr, Sonarr)
    # TODO Phase 3: Initialize scoring engine
    # TODO Phase 6: Initialize APScheduler

    log.success("Swabbarr API startup complete")

    yield

    # --- Shutdown ---
    log.info("Swabbarr API shutting down")
    await db_manager.close()
    log.info("Swabbarr API shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Swabbarr",
    description="Media Library Pruning Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (dashboard needs to call the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",     # Next.js dev server
        "http://localhost:8484",     # API dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health endpoint (always available, expanded in Phase 4)
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health_check():
    """Basic health check — returns 200 if the API is running."""
    return {
        "status": "healthy",
        "service": "swabbarr-api",
        "version": "0.1.0",
    }


# TODO Phase 4: Register routers
# from src.routers import scores, config, media, actions
# app.include_router(scores.router, prefix="/api/scores", tags=["scores"])
# app.include_router(config.router, prefix="/api/config", tags=["config"])
# app.include_router(media.router, prefix="/api/media", tags=["media"])
# app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
