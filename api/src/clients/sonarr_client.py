"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Sonarr API client. Fetches TV series metadata, episode counts, file sizes,
and TVDB/TMDB IDs. Used for both Sonarr and Sonarr-Anime instances.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import logging
from dataclasses import dataclass

from src.clients.base_client import BaseClient


@dataclass
class SonarrSeries:
    """Structured series data from Sonarr."""

    sonarr_id: int
    tvdb_id: int | None
    tmdb_id: int | None
    title: str
    year: int | None
    file_size_bytes: int
    episode_count: int
    quality_profile: str | None
    added_at: str | None
    arr_source: str  # 'sonarr' or 'sonarr-anime'


class SonarrClient(BaseClient):
    """Client for the Sonarr v3 API.

    Used for both Sonarr and Sonarr-Anime instances — the arr_source
    parameter distinguishes them.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        log: logging.Logger,
        arr_source: str = "sonarr",
        **kwargs,
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, log=log, **kwargs)
        self._arr_source = arr_source

    @property
    def service_name(self) -> str:
        return self._arr_source

    async def _get_headers(self) -> dict:
        return {"X-Api-Key": self._api_key}

    async def health_check(self) -> bool:
        """Check Sonarr is reachable via its system status endpoint."""
        result = await self._get(
            "/api/v3/system/status",
            headers=await self._get_headers(),
        )
        if result is not None:
            self._log.success(
                f"{self.service_name}: Connected — "
                f"version {result.get('version', 'unknown')}"
            )
            return True
        return False

    async def get_series(self) -> list[SonarrSeries]:
        """Fetch all series from Sonarr.

        Returns a list of SonarrSeries objects. Returns empty list on failure.
        """
        data = await self._get(
            "/api/v3/series",
            headers=await self._get_headers(),
        )
        if data is None:
            self._log.warning(f"{self.service_name}: Failed to fetch series list")
            return []

        series_list: list[SonarrSeries] = []
        for item in data:
            try:
                stats = item.get("statistics", {})

                # Sonarr v4+ may include tmdbId directly
                tmdb_id = item.get("tmdbId")

                series_list.append(
                    SonarrSeries(
                        sonarr_id=item.get("id", 0),
                        tvdb_id=item.get("tvdbId"),
                        tmdb_id=tmdb_id,
                        title=item.get("title", "Unknown"),
                        year=item.get("year"),
                        file_size_bytes=stats.get("sizeOnDisk", 0),
                        episode_count=stats.get("episodeFileCount", 0),
                        quality_profile=item.get("qualityProfileId"),
                        added_at=item.get("added"),
                        arr_source=self._arr_source,
                    )
                )
            except Exception as e:
                self._log.warning(
                    f"{self.service_name}: Skipping malformed series entry: {e}"
                )
                continue

        self._log.info(f"{self.service_name}: Fetched {len(series_list)} series")
        return series_list


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_sonarr_client(
    base_url: str,
    api_key: str,
    log: logging.Logger,
    arr_source: str = "sonarr",
) -> SonarrClient:
    """Create a SonarrClient instance.

    Use arr_source='sonarr-anime' for the anime Sonarr instance.
    """
    return SonarrClient(
        base_url=base_url,
        api_key=api_key,
        log=log,
        arr_source=arr_source,
    )


__all__ = ["SonarrClient", "SonarrSeries", "create_sonarr_client"]
