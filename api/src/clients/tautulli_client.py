"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Tautulli API client. Fetches watch history, play counts, viewer data,
and completion percentages from Tautulli's API v2.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import logging
from dataclasses import dataclass, field

from src.clients.base_client import BaseClient


@dataclass
class TautulliWatchRecord:
    """A single watch record from Tautulli history."""

    rating_key: str
    title: str
    year: int | None
    media_type: str  # 'movie' or 'episode'
    user: str
    watched_status: float  # 0.0 to 1.0
    play_count: int
    last_played: str | None
    grandparent_title: str | None  # Series title for episodes
    grandparent_rating_key: str | None  # Series rating_key


@dataclass
class TautulliMediaSummary:
    """Aggregated watch data for a single media item (movie or series)."""

    rating_key: str
    title: str
    year: int | None
    media_type: str  # 'movie' or 'series'
    total_plays: int = 0
    unique_viewers: int = 0
    last_watched_at: str | None = None
    avg_completion_pct: float = 0.0
    viewers: list[str] = field(default_factory=list)


class TautulliClient(BaseClient):
    """Client for the Tautulli API v2."""

    @property
    def service_name(self) -> str:
        return "tautulli"

    async def _tautulli_get(self, cmd: str, **params) -> dict | None:
        """Execute a Tautulli API command.

        Tautulli uses a single endpoint with cmd= parameter.
        """
        all_params = {"apikey": self._api_key, "cmd": cmd, **params}
        result = await self._get("/api/v2", params=all_params)
        if result and result.get("response", {}).get("result") == "success":
            return result["response"].get("data", {})
        return None

    async def health_check(self) -> bool:
        """Check Tautulli is reachable via the server info command."""
        data = await self._tautulli_get("get_server_info")
        if data is not None:
            self._log.success("Tautulli connected")
            return True
        return False

    async def get_library_media_info(
        self,
        section_id: int,
        length: int = 5000,
    ) -> list[dict]:
        """Fetch media info for an entire library section.

        Returns raw Tautulli data for each item in the section.
        """
        data = await self._tautulli_get(
            "get_library_media_info",
            section_id=section_id,
            length=length,
        )
        if data is None:
            return []
        return data.get("data", [])

    async def get_history(
        self,
        length: int = 5000,
        media_type: str | None = None,
    ) -> list[TautulliWatchRecord]:
        """Fetch full watch history from Tautulli.

        Paginates automatically to retrieve all records.
        Returns structured TautulliWatchRecord objects.
        """
        params = {"length": length, "order_column": "date", "order_dir": "desc"}
        if media_type:
            params["media_type"] = media_type

        data = await self._tautulli_get("get_history", **params)
        if data is None:
            self._log.warning("Tautulli: Failed to fetch watch history")
            return []

        records: list[TautulliWatchRecord] = []
        for item in data.get("data", []):
            try:
                records.append(
                    TautulliWatchRecord(
                        rating_key=str(item.get("rating_key", "")),
                        title=item.get("full_title", item.get("title", "Unknown")),
                        year=item.get("year"),
                        media_type=item.get("media_type", ""),
                        user=item.get("user", "Unknown"),
                        watched_status=float(item.get("watched_status", 0)),
                        play_count=1,  # Each history row is one play
                        last_played=item.get("started"),
                        grandparent_title=item.get("grandparent_title"),
                        grandparent_rating_key=str(
                            item.get("grandparent_rating_key", "")
                        )
                        if item.get("grandparent_rating_key")
                        else None,
                    )
                )
            except Exception as e:
                self._log.warning(f"Tautulli: Skipping malformed history entry: {e}")
                continue

        self._log.info(f"Tautulli: Fetched {len(records)} watch records")
        return records

    def aggregate_by_media(
        self,
        records: list[TautulliWatchRecord],
    ) -> dict[str, TautulliMediaSummary]:
        """Aggregate individual watch records into per-media summaries.

        Groups by rating_key for movies, by grandparent_rating_key for
        episodes (so we get one summary per series, not per episode).

        Returns a dict keyed by rating_key (movies) or
        grandparent_rating_key (series).
        """
        summaries: dict[str, TautulliMediaSummary] = {}

        for record in records:
            # For episodes, aggregate at the series level
            if record.media_type == "episode" and record.grandparent_rating_key:
                key = record.grandparent_rating_key
                title = record.grandparent_title or record.title
                media_type = "series"
            else:
                key = record.rating_key
                title = record.title
                media_type = "movie"

            if key not in summaries:
                summaries[key] = TautulliMediaSummary(
                    rating_key=key,
                    title=title,
                    year=record.year,
                    media_type=media_type,
                )

            summary = summaries[key]
            summary.total_plays += 1

            # Track unique viewers
            if record.user not in summary.viewers:
                summary.viewers.append(record.user)
                summary.unique_viewers = len(summary.viewers)

            # Track most recent watch
            if record.last_played:
                if (
                    summary.last_watched_at is None
                    or record.last_played > summary.last_watched_at
                ):
                    summary.last_watched_at = record.last_played

            # Running average of completion percentage
            current_total = summary.avg_completion_pct * (summary.total_plays - 1)
            summary.avg_completion_pct = (
                current_total + record.watched_status * 100
            ) / summary.total_plays

        self._log.info(f"Tautulli: Aggregated into {len(summaries)} media summaries")
        return summaries


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_tautulli_client(
    base_url: str,
    api_key: str,
    log: logging.Logger,
) -> TautulliClient:
    """Create a TautulliClient instance."""
    return TautulliClient(base_url=base_url, api_key=api_key, log=log)


__all__ = [
    "TautulliClient",
    "TautulliWatchRecord",
    "TautulliMediaSummary",
    "create_tautulli_client",
]
