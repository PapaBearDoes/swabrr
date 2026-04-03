"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Radarr API client. Fetches movie metadata, file sizes, quality profiles,
and TMDB IDs for all movies in the library.

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
class RadarrMovie:
    """Structured movie data from Radarr."""

    radarr_id: int
    tmdb_id: int
    title: str
    year: int | None
    file_size_bytes: int
    quality_profile: str | None
    added_at: str | None
    has_file: bool


class RadarrClient(BaseClient):
    """Client for the Radarr v3 API."""

    @property
    def service_name(self) -> str:
        return "radarr"

    async def _get_headers(self) -> dict:
        return {"X-Api-Key": self._api_key}

    async def health_check(self) -> bool:
        """Check Radarr is reachable via its system status endpoint."""
        result = await self._get(
            "/api/v3/system/status",
            headers=await self._get_headers(),
        )
        if result is not None:
            self._log.success(
                f"Radarr connected — version {result.get('version', 'unknown')}"
            )
            return True
        return False

    async def get_movies(self) -> list[RadarrMovie]:
        """Fetch all movies from Radarr.

        Returns a list of RadarrMovie objects. Returns empty list on failure.
        """
        data = await self._get(
            "/api/v3/movie",
            headers=await self._get_headers(),
        )
        if data is None:
            self._log.warning("Radarr: Failed to fetch movie list")
            return []

        movies: list[RadarrMovie] = []
        for item in data:
            try:
                tmdb_id = item.get("tmdbId")
                if not tmdb_id:
                    continue

                # Determine quality from movie file if present
                quality = None
                movie_file = item.get("movieFile")
                if movie_file and movie_file.get("quality"):
                    q = movie_file["quality"].get("quality", {})
                    quality = q.get("name")

                movies.append(
                    RadarrMovie(
                        radarr_id=item.get("id", 0),
                        tmdb_id=tmdb_id,
                        title=item.get("title", "Unknown"),
                        year=item.get("year"),
                        file_size_bytes=item.get("sizeOnDisk", 0),
                        quality_profile=quality,
                        added_at=item.get("added"),
                        has_file=item.get("hasFile", False),
                    )
                )
            except Exception as e:
                self._log.warning(f"Radarr: Skipping malformed movie entry: {e}")
                continue

        self._log.info(f"Radarr: Fetched {len(movies)} movies")
        return movies


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_radarr_client(
    base_url: str,
    api_key: str,
    log: logging.Logger,
) -> RadarrClient:
    """Create a RadarrClient instance."""
    return RadarrClient(base_url=base_url, api_key=api_key, log=log)


__all__ = ["RadarrClient", "RadarrMovie", "create_radarr_client"]
