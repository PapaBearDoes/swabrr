"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Health router — overall health and per-service status checks.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def health_check(request: Request):
    """Overall health — checks DB connectivity."""
    db = request.app.state.db_manager
    try:
        async with db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_healthy = True
    except Exception:
        db_healthy = False

    status = "healthy" if db_healthy else "degraded"
    return {
        "status": status,
        "service": "swabrr-api",
        "version": "0.1.0",
        "database": "connected" if db_healthy else "disconnected",
    }


@router.get("/services")
async def service_status(request: Request):
    """Check connectivity to each external service."""
    clients = getattr(request.app.state, "clients", {})
    results = {}

    for name, client in clients.items():
        try:
            healthy = await client.health_check()
            results[name] = "connected" if healthy else "unreachable"
        except Exception:
            results[name] = "error"

    # Check which services are configured but not connected
    expected = ["radarr", "sonarr", "sonarr_anime", "tautulli", "seerr"]
    for svc in expected:
        if svc not in results:
            results[svc] = "not_configured"

    return {"services": results}
