"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Seerr (Overseerr/Jellyseerr) API client. Fetches media request history,
requestor identity, and request dates. Maps directly to TMDB IDs.

----------------------------------------------------------------------------
FILE VERSION: v1.0.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import logging
from dataclasses import dataclass

from src.clients.base_client import BaseClient


@dataclass
class SeerrRequest:
    """A single media request from Seerr."""
    request_id: int
    tmdb_id: int
    media_type: str  # 'movie' or 'tv'
    title: str | None
    requested_by: str
    requested_at: str | None
    status: str  # e.g. 'approved', 'available', 'pending'


class SeerrClient(BaseClient):
    """Client for the Overseerr/Jellyseerr API v1."""

    @property
    def service_name(self) -> str:
        return "seerr"

    async def _get_headers(self) -> dict:
        return {"X-Api-Key": self._api_key}

    async def health_check(self) -> bool:
        """Check Seerr is reachable via its status endpoint."""
        result = await self._get(
            "/api/v1/status",
            headers=await self._get_headers(),
        )
        if result is not None:
            version = result.get("version", "unknown")
            self._log.success(f"Seerr connected — version {version}")
            return True
        return False

    async def get_requests(self) -> list[SeerrRequest]:
        """Fetch all media requests from Seerr.

        Paginates through all requests automatically.
        Returns structured SeerrRequest objects with TMDB IDs.
        """
        all_requests: list[SeerrRequest] = []
        page = 1
        page_size = 50

        while True:
            data = await self._get(
                "/api/v1/request",
                params={
                    "take": page_size,
                    "skip": (page - 1) * page_size,
                    "sort": "added",
                },
                headers=await self._get_headers(),
            )
            if data is None:
                self._log.warning("Seerr: Failed to fetch requests")
                break

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                try:
                    media = item.get("media", {})
                    tmdb_id = media.get("tmdbId")
                    if not tmdb_id:
                        continue

                    # Normalize media type: Seerr uses 'tv', we use 'series'
                    raw_type = item.get("type", media.get("mediaType", ""))
                    media_type = "series" if raw_type == "tv" else "movie"

                    # Get requestor display name
                    requested_by_obj = item.get("requestedBy", {})
                    requested_by = (
                        requested_by_obj.get("displayName")
                        or requested_by_obj.get("username")
                        or "Unknown"
                    )

                    # Map status
                    status_code = media.get("status", 0)
                    status_map = {
                        1: "unknown",
                        2: "pending",
                        3: "processing",
                        4: "partially_available",
                        5: "available",
                    }
                    status = status_map.get(status_code, "unknown")

                    all_requests.append(SeerrRequest(
                        request_id=item.get("id", 0),
                        tmdb_id=tmdb_id,
                        media_type=media_type,
                        title=media.get("title") or media.get("name"),
                        requested_by=requested_by,
                        requested_at=item.get("createdAt"),
                        status=status,
                    ))
                except Exception as e:
                    self._log.warning(
                        f"Seerr: Skipping malformed request entry: {e}"
                    )
                    continue

            # Check if there are more pages
            page_info = data.get("pageInfo", {})
            total_pages = page_info.get("pages", 1)
            if page >= total_pages:
                break
            page += 1

        self._log.info(f"Seerr: Fetched {len(all_requests)} requests")
        return all_requests

    def get_requests_by_tmdb_id(
        self,
        requests: list[SeerrRequest],
    ) -> dict[int, SeerrRequest]:
        """Index requests by TMDB ID for fast lookup during scoring.

        If multiple requests exist for the same TMDB ID, keeps the
        most recent one.
        """
        by_tmdb: dict[int, SeerrRequest] = {}
        for req in requests:
            existing = by_tmdb.get(req.tmdb_id)
            if existing is None or (
                req.requested_at
                and existing.requested_at
                and req.requested_at > existing.requested_at
            ):
                by_tmdb[req.tmdb_id] = req
        return by_tmdb


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_seerr_client(
    base_url: str,
    api_key: str,
    log: logging.Logger,
) -> SeerrClient:
    """Create a SeerrClient instance."""
    return SeerrClient(base_url=base_url, api_key=api_key, log=log)


__all__ = ["SeerrClient", "SeerrRequest", "create_seerr_client"]
