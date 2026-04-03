"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

TMDB API client. Fetches streaming availability (watch providers),
ratings, vote counts, and resolves TVDB IDs to TMDB IDs.

----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-04-02
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field

from src.clients.base_client import BaseClient


@dataclass
class TMDBMediaInfo:
    """Enriched media data from TMDB."""

    tmdb_id: int
    media_type: str  # 'movie' or 'series'
    vote_average: float | None = None
    vote_count: int = 0
    streaming_services: list[str] = field(default_factory=list)
    streaming_service_count: int = 0
    genres: list[str] = field(default_factory=list)
    release_date: str | None = None


class TMDBClient(BaseClient):
    """Client for The Movie Database (TMDB) API v3."""

    def __init__(
        self,
        api_key: str,
        log: logging.Logger,
        region: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            base_url="https://api.themoviedb.org",
            api_key=api_key,
            log=log,
            **kwargs,
        )
        self._region = region or os.environ.get("SWABBARR_TMDB_REGION", "US")
        self._rate_delay = 0.05  # ~20 req/s, conservative under TMDB's 40/s limit

    @property
    def service_name(self) -> str:
        return "tmdb"

    async def _tmdb_get(self, path: str, params: dict | None = None) -> dict | None:
        """Make a TMDB API request with auth header."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "accept": "application/json",
        }
        await asyncio.sleep(self._rate_delay)
        return await self._get(path, params=params, headers=headers)

    async def health_check(self) -> bool:
        """Verify TMDB API is reachable."""
        result = await self._tmdb_get("/3/configuration")
        if result is not None:
            self._log.success("TMDB connected")
            return True
        return False

    # -------------------------------------------------------------------
    # TVDB → TMDB resolution
    # -------------------------------------------------------------------
    async def resolve_tvdb_id(self, tvdb_id: int) -> int | None:
        """Resolve a TVDB ID to a TMDB ID via TMDB's find endpoint."""
        result = await self._tmdb_get(
            f"/3/find/{tvdb_id}",
            params={"external_source": "tvdb_id"},
        )
        if not result:
            return None

        tv_results = result.get("tv_results", [])
        if tv_results:
            return tv_results[0].get("id")

        # Also check movie results in case it's a TV movie
        movie_results = result.get("movie_results", [])
        if movie_results:
            return movie_results[0].get("id")

        return None

    # -------------------------------------------------------------------
    # Media details
    # -------------------------------------------------------------------
    async def get_movie_info(self, tmdb_id: int) -> TMDBMediaInfo | None:
        """Fetch movie details and watch providers."""
        details = await self._tmdb_get(f"/3/movie/{tmdb_id}")
        if not details:
            return None

        providers = await self._get_watch_providers("movie", tmdb_id)

        return TMDBMediaInfo(
            tmdb_id=tmdb_id,
            media_type="movie",
            vote_average=details.get("vote_average"),
            vote_count=details.get("vote_count", 0),
            streaming_services=providers,
            streaming_service_count=len(providers),
            genres=[g.get("name", "") for g in details.get("genres", [])],
            release_date=details.get("release_date"),
        )

    async def get_series_info(self, tmdb_id: int) -> TMDBMediaInfo | None:
        """Fetch TV series details and watch providers."""
        details = await self._tmdb_get(f"/3/tv/{tmdb_id}")
        if not details:
            return None

        providers = await self._get_watch_providers("tv", tmdb_id)

        return TMDBMediaInfo(
            tmdb_id=tmdb_id,
            media_type="series",
            vote_average=details.get("vote_average"),
            vote_count=details.get("vote_count", 0),
            streaming_services=providers,
            streaming_service_count=len(providers),
            genres=[g.get("name", "") for g in details.get("genres", [])],
            release_date=details.get("first_air_date"),
        )

    async def get_info(self, tmdb_id: int, media_type: str) -> TMDBMediaInfo | None:
        """Fetch info for either a movie or series."""
        if media_type == "movie":
            return await self.get_movie_info(tmdb_id)
        return await self.get_series_info(tmdb_id)

    # -------------------------------------------------------------------
    # Watch providers (streaming availability)
    # -------------------------------------------------------------------
    async def _get_watch_providers(
        self, media_type_path: str, tmdb_id: int
    ) -> list[str]:
        """Get flat-rate streaming services for a title in the configured region.

        media_type_path: 'movie' or 'tv' (TMDB API path segment)
        """
        result = await self._tmdb_get(
            f"/3/{media_type_path}/{tmdb_id}/watch/providers",
        )
        if not result:
            return []

        region_data = result.get("results", {}).get(self._region, {})
        flatrate = region_data.get("flatrate", [])
        return [p.get("provider_name", "") for p in flatrate if p.get("provider_name")]

    # -------------------------------------------------------------------
    # Batch fetch with caching
    # -------------------------------------------------------------------
    async def batch_fetch(
        self,
        tmdb_ids: list[tuple[int, str]],
        db_manager=None,
    ) -> dict[int, TMDBMediaInfo]:
        """Batch fetch TMDB data for multiple titles, using DB cache.

        Args:
            tmdb_ids: List of (tmdb_id, media_type) tuples
            db_manager: Optional DBManager for caching

        Returns dict keyed by tmdb_id.
        """
        results: dict[int, TMDBMediaInfo] = {}
        to_fetch: list[tuple[int, str]] = []

        # Check cache first
        if db_manager:
            async with db_manager.acquire() as conn:
                for tmdb_id, media_type in tmdb_ids:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM tmdb_cache
                        WHERE tmdb_id = $1
                        AND streaming_expires_at > NOW()
                        AND cultural_expires_at > NOW()
                        """,
                        tmdb_id,
                    )
                    if row:
                        results[tmdb_id] = TMDBMediaInfo(
                            tmdb_id=tmdb_id,
                            media_type=row["media_type"],
                            vote_average=float(row["vote_average"])
                            if row["vote_average"]
                            else None,
                            vote_count=row["vote_count"],
                            streaming_services=(row["streaming_services"] or "").split(
                                ","
                            )
                            if row["streaming_services"]
                            else [],
                            streaming_service_count=row["streaming_service_count"],
                            genres=(row["genres"] or "").split(",")
                            if row["genres"]
                            else [],
                            release_date=row.get("release_date"),
                        )
                    else:
                        to_fetch.append((tmdb_id, media_type))
        else:
            to_fetch = list(tmdb_ids)

        # Fetch uncached titles from TMDB API
        total_to_fetch = len(to_fetch)
        self._log.info(f"TMDB: {len(results)} cached, {total_to_fetch} to fetch")

        fetched = 0
        skipped = 0
        last_progress = time.monotonic()

        for tmdb_id, media_type in to_fetch:
            info = await self.get_info(tmdb_id, media_type)
            if info:
                results[tmdb_id] = info
                # Write to cache
                if db_manager:
                    await self._cache_result(db_manager, info)
                fetched += 1
            else:
                skipped += 1

            # Progress log every 5 seconds
            now = time.monotonic()
            if now - last_progress >= 5.0:
                done = fetched + skipped
                pct = (done / total_to_fetch * 100) if total_to_fetch else 0
                self._log.info(
                    f"TMDB: {done}/{total_to_fetch} processed "
                    f"({pct:.0f}%) — {fetched} enriched, {skipped} not found"
                )
                last_progress = now

        self._log.success(
            f"TMDB: Complete — {fetched} enriched, {skipped} not found, "
            f"{len(results)} total (incl. cached)"
        )
        return results

    async def _cache_result(self, db_manager, info: TMDBMediaInfo) -> None:
        """Write a TMDB result to the cache table."""
        try:
            async with db_manager.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tmdb_cache (
                        tmdb_id, media_type, vote_average, vote_count,
                        streaming_services, streaming_service_count,
                        streaming_region, genres, release_date
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (tmdb_id) DO UPDATE SET
                        vote_average = EXCLUDED.vote_average,
                        vote_count = EXCLUDED.vote_count,
                        streaming_services = EXCLUDED.streaming_services,
                        streaming_service_count = EXCLUDED.streaming_service_count,
                        genres = EXCLUDED.genres,
                        release_date = EXCLUDED.release_date,
                        fetched_at = NOW(),
                        streaming_expires_at = NOW() + INTERVAL '7 days',
                        cultural_expires_at = NOW() + INTERVAL '30 days'
                    """,
                    info.tmdb_id,
                    info.media_type,
                    info.vote_average,
                    info.vote_count,
                    ",".join(info.streaming_services),
                    info.streaming_service_count,
                    self._region,
                    ",".join(info.genres),
                    info.release_date,
                )
        except Exception as e:
            self._log.warning(f"TMDB: Failed to cache result for {info.tmdb_id}: {e}")


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_tmdb_client(
    api_key: str,
    log: logging.Logger,
    region: str | None = None,
) -> TMDBClient:
    """Create a TMDBClient instance."""
    return TMDBClient(api_key=api_key, log=log, region=region)


__all__ = ["TMDBClient", "TMDBMediaInfo", "create_tmdb_client"]
