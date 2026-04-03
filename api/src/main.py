"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

FastAPI application entry point.
Manages application lifespan (startup/shutdown), database initialization,
and router registration.

----------------------------------------------------------------------------
FILE VERSION: v1.5.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.managers.logging_config_manager import create_logging_config_manager
from src.managers.db_manager import create_db_manager
from src.managers.config_manager import create_config_manager
from src.managers.settings_manager import create_settings_manager
from src.clients.radarr_client import create_radarr_client
from src.clients.sonarr_client import create_sonarr_client
from src.clients.tautulli_client import create_tautulli_client
from src.clients.seerr_client import create_seerr_client
from src.clients.tmdb_client import create_tmdb_client
from src.scoring.engine import create_scoring_engine
from src.managers.scheduler_manager import create_scheduler_manager


# ---------------------------------------------------------------------------
# Logging (initialized immediately — Rule #9)
# ---------------------------------------------------------------------------
log_manager = create_logging_config_manager(component="swabrr-api")
log = log_manager.get_logger("main")


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Manage startup and shutdown of shared resources."""

    # --- Startup ---
    log.info("Swabrr API starting up")

    # Database
    db_manager = await create_db_manager(
        log=log_manager.get_logger("db_manager"),
    )
    application.state.db_manager = db_manager
    log.success("Database manager ready")

    # Settings manager (reads service configs from DB)
    settings_manager = create_settings_manager(
        db_manager=db_manager,
        log=log_manager.get_logger("settings_manager"),
    )
    application.state.settings_manager = settings_manager
    log.success("Settings manager ready")

    # API Clients — build from DB settings (also used for refresh before scoring)
    async def build_clients_from_db() -> dict:
        """Build API client instances from current DB service settings.

        Called at startup and before each scoring run so that
        dashboard-configured settings take effect without a restart.
        """
        built: dict = {}
        try:
            services = await settings_manager.get_all_services()
            for svc in services:
                # TMDB has no base_url — it's hardcoded in the client
                requires_url = svc.service_name not in ("tmdb",)
                if not svc.enabled:
                    log.debug(f"Skipping {svc.service_name} — not enabled")
                    continue
                if not svc.api_key:
                    log.debug(f"Skipping {svc.service_name} — no API key")
                    continue
                if requires_url and not svc.base_url:
                    log.debug(f"Skipping {svc.service_name} — no base URL")
                    continue
                try:
                    if svc.service_name == "radarr":
                        built["radarr"] = create_radarr_client(
                            svc.base_url,
                            svc.api_key,
                            log_manager.get_logger("radarr_client"),
                        )
                    elif svc.service_name == "sonarr":
                        built["sonarr"] = create_sonarr_client(
                            svc.base_url,
                            svc.api_key,
                            log_manager.get_logger("sonarr_client"),
                            arr_source="sonarr",
                        )
                    elif svc.service_name == "sonarr_anime":
                        built["sonarr_anime"] = create_sonarr_client(
                            svc.base_url,
                            svc.api_key,
                            log_manager.get_logger("sonarr_anime_client"),
                            arr_source="sonarr-anime",
                        )
                    elif svc.service_name == "tautulli":
                        built["tautulli"] = create_tautulli_client(
                            svc.base_url,
                            svc.api_key,
                            log_manager.get_logger("tautulli_client"),
                        )
                    elif svc.service_name == "seerr":
                        built["seerr"] = create_seerr_client(
                            svc.base_url,
                            svc.api_key,
                            log_manager.get_logger("seerr_client"),
                        )
                    elif svc.service_name == "tmdb":
                        built["tmdb"] = create_tmdb_client(
                            svc.api_key, log_manager.get_logger("tmdb_client")
                        )
                except Exception as e:
                    log.warning(f"Failed to initialize {svc.service_name}: {e}")
        except Exception as e:
            log.warning(f"Could not load service settings from DB: {e}")
            log.info("Services can be configured via the dashboard Settings page")
        return built

    clients = await build_clients_from_db()
    application.state.clients = clients
    application.state.build_clients = build_clients_from_db
    log.success(f"API clients initialized: {list(clients.keys())}")

    # Scoring engine (Phase 3)
    config_manager = create_config_manager(
        db_manager=db_manager,
        log=log_manager.get_logger("config_manager"),
    )
    application.state.config_manager = config_manager

    scoring_engine = create_scoring_engine(
        db_manager=db_manager,
        config_manager=config_manager,
        clients=clients,
        log=log_manager.get_logger("scoring_engine"),
        build_clients_fn=build_clients_from_db,
    )
    application.state.scoring_engine = scoring_engine
    log.success("Scoring engine ready")

    # Scheduler (Phase 6)
    scheduler = create_scheduler_manager(
        scoring_engine=scoring_engine,
        log=log_manager.get_logger("scheduler"),
    )
    scheduler.start()
    application.state.scheduler = scheduler

    log.success("Swabrr API startup complete")

    yield

    # --- Shutdown ---
    log.info("Swabrr API shutting down")
    application.state.scheduler.stop()
    for name, client in application.state.clients.items():
        await client.close()
    await db_manager.close()
    log.info("Swabrr API shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Swabrr",
    description="Media Library Pruning Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (dashboard needs to call the API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:8484",  # API dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers (Phase 4)
# ---------------------------------------------------------------------------
from src.routers import scores, config, media, actions, health, settings

app.include_router(scores.router, prefix="/api/scores", tags=["scores"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(media.router, prefix="/api/media", tags=["media"])
app.include_router(actions.router, prefix="/api/actions", tags=["actions"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
