"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Settings router — manage external service connections (URLs, API keys)
through the dashboard instead of Docker Secrets.

----------------------------------------------------------------------------
FILE VERSION: v1.0.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ServiceUpdate(BaseModel):
    """Request body for updating a service's settings."""

    base_url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None


@router.get("")
async def list_services(request: Request):
    """List all external service configurations.

    API keys are masked in the response for security.
    """
    settings = request.app.state.settings_manager
    services = await settings.get_all_services()
    return {
        "services": [
            {
                "service_name": s.service_name,
                "display_name": s.display_name,
                "base_url": s.base_url or "",
                "has_api_key": s.api_key is not None and len(s.api_key or "") > 0,
                "api_key_preview": f"...{s.api_key[-4:]}"
                if s.api_key and len(s.api_key) > 4
                else "",
                "enabled": s.enabled,
                "last_verified": s.last_verified,
                "verify_status": s.verify_status,
            }
            for s in services
        ]
    }


@router.get("/{service_name}")
async def get_service(request: Request, service_name: str):
    """Get a single service configuration (key masked)."""
    settings = request.app.state.settings_manager
    s = await settings.get_service(service_name)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    return {
        "service_name": s.service_name,
        "display_name": s.display_name,
        "base_url": s.base_url or "",
        "has_api_key": s.api_key is not None and len(s.api_key or "") > 0,
        "api_key_preview": f"...{s.api_key[-4:]}"
        if s.api_key and len(s.api_key) > 4
        else "",
        "enabled": s.enabled,
        "last_verified": s.last_verified,
        "verify_status": s.verify_status,
    }


@router.put("/{service_name}")
async def update_service(request: Request, service_name: str, body: ServiceUpdate):
    """Update a service's connection settings."""
    settings = request.app.state.settings_manager
    success = await settings.update_service(
        service_name=service_name,
        base_url=body.base_url,
        api_key=body.api_key,
        enabled=body.enabled,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"status": "updated", "service_name": service_name}


@router.post("/{service_name}/verify")
async def verify_service(request: Request, service_name: str):
    """Test connectivity to a service and update its verify status."""
    settings = request.app.state.settings_manager
    s = await settings.get_service(service_name)
    if not s:
        raise HTTPException(status_code=404, detail="Service not found")
    # TMDB only needs an API key (base URL is hardcoded in the client)
    requires_url = service_name not in ("tmdb",)
    if (requires_url and not s.base_url) or not s.api_key:
        await settings.update_verify_status(service_name, "not_configured")
        return {"status": "not_configured", "message": "URL or API key missing"}

    # Dynamically create a temporary client and test connectivity
    from src.clients.radarr_client import create_radarr_client
    from src.clients.sonarr_client import create_sonarr_client
    from src.clients.tautulli_client import create_tautulli_client
    from src.clients.seerr_client import create_seerr_client
    from src.clients.tmdb_client import create_tmdb_client
    import logging

    temp_log = logging.getLogger(f"swabrr-api.verify.{service_name}")
    client = None

    try:
        if service_name == "radarr":
            client = create_radarr_client(s.base_url, s.api_key, temp_log)
        elif service_name in ("sonarr", "sonarr_anime"):
            client = create_sonarr_client(
                s.base_url, s.api_key, temp_log, arr_source=service_name
            )
        elif service_name == "tautulli":
            client = create_tautulli_client(s.base_url, s.api_key, temp_log)
        elif service_name == "seerr":
            client = create_seerr_client(s.base_url, s.api_key, temp_log)
        elif service_name == "tmdb":
            client = create_tmdb_client(s.api_key, temp_log)
        else:
            return {"status": "unknown_service"}

        healthy = await client.health_check()
        status = "connected" if healthy else "unreachable"
        await settings.update_verify_status(service_name, status)

        if client:
            await client.close()

        return {"status": status, "service_name": service_name}

    except Exception as e:
        await settings.update_verify_status(service_name, "error")
        if client:
            await client.close()
        return {"status": "error", "message": str(e)}
