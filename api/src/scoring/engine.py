"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Core scoring engine. Orchestrates the full scoring pipeline:
fetch data → merge into unified records → apply signal calculators →
compute weighted scores → persist results to PostgreSQL.

----------------------------------------------------------------------------
FILE VERSION: v1.2.0
LAST MODIFIED: 2026-04-02
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import logging
import statistics
from datetime import datetime, timezone

from src.managers.db_manager import DBManager
from src.managers.config_manager import ConfigManager
from src.clients.radarr_client import RadarrClient
from src.clients.sonarr_client import SonarrClient
from src.clients.tautulli_client import TautulliClient
from src.clients.seerr_client import SeerrClient
from src.clients.tmdb_client import TMDBClient
from src.scoring.models import (
    MediaRecord,
    ScoreBreakdown,
    ScoringRunResult,
    ScoringWeights,
)
from src.scoring.signals import (
    calc_watch_activity,
    calc_rarity,
    calc_request_accountability,
    calc_size_efficiency,
    calc_cultural_value,
)


class ScoringEngine:
    """Orchestrates the full scoring pipeline."""

    def __init__(
        self,
        db_manager: DBManager,
        config_manager: ConfigManager,
        radarr: RadarrClient | None,
        sonarr: SonarrClient | None,
        sonarr_anime: SonarrClient | None,
        tautulli: TautulliClient | None,
        seerr: SeerrClient | None,
        tmdb: TMDBClient | None,
        log: logging.Logger,
        build_clients_fn=None,
    ) -> None:
        self._db = db_manager
        self._config = config_manager
        self._radarr = radarr
        self._sonarr = sonarr
        self._sonarr_anime = sonarr_anime
        self._tautulli = tautulli
        self._seerr = seerr
        self._tmdb = tmdb
        self._log = log
        self._build_clients_fn = build_clients_fn

    # -----------------------------------------------------------------------
    # Client refresh — reload from DB settings before each run
    # -----------------------------------------------------------------------
    async def _refresh_clients(self) -> None:
        """Rebuild API clients from current DB settings.

        Ensures dashboard-configured services take effect without a restart.
        Closes any existing clients before replacing them.
        """
        if not self._build_clients_fn:
            return

        # Close existing clients
        for client in [
            self._radarr, self._sonarr, self._sonarr_anime,
            self._tautulli, self._seerr, self._tmdb,
        ]:
            if client:
                try:
                    await client.close()
                except Exception:
                    pass

        clients = await self._build_clients_fn()
        self._radarr = clients.get("radarr")
        self._sonarr = clients.get("sonarr")
        self._sonarr_anime = clients.get("sonarr_anime")
        self._tautulli = clients.get("tautulli")
        self._seerr = clients.get("seerr")
        self._tmdb = clients.get("tmdb")
        self._log.info(f"Refreshed clients: {list(clients.keys())}")

    # -----------------------------------------------------------------------
    # Step 1: Fetch data from all sources
    # -----------------------------------------------------------------------
    async def _fetch_all(self) -> tuple[list[MediaRecord], list[str]]:
        """Fetch data from all clients and merge into MediaRecords.

        Returns (records, warnings) — warnings list notes any unavailable APIs.
        """
        records_by_tmdb: dict[int, MediaRecord] = {}
        warnings: list[str] = []

        # --- Radarr: movies ---
        if self._radarr:
            movies = await self._radarr.get_movies()
            for m in movies:
                records_by_tmdb[m.tmdb_id] = MediaRecord(
                    tmdb_id=m.tmdb_id,
                    title=m.title,
                    year=m.year,
                    media_type="movie",
                    file_size_bytes=m.file_size_bytes,
                    quality_profile=m.quality_profile,
                    arr_id=m.radarr_id,
                    arr_source="radarr",
                    added_at=m.added_at,
                )
            self._log.info(f"Merged {len(movies)} movies from Radarr")
        else:
            warnings.append("Radarr unavailable")

        # --- Sonarr: TV series ---
        for client_name, client in [
            ("sonarr", self._sonarr),
            ("sonarr-anime", self._sonarr_anime),
        ]:
            if client:
                series_list = await client.get_series()
                for s in series_list:
                    # Use tmdb_id if available, resolve via TMDB if not
                    tmdb_id = s.tmdb_id
                    if not tmdb_id and s.tvdb_id and self._tmdb:
                        # Check tvdb_tmdb_map cache first
                        async with self._db.acquire() as conn:
                            cached = await conn.fetchrow(
                                "SELECT tmdb_id FROM tvdb_tmdb_map WHERE tvdb_id = $1",
                                s.tvdb_id,
                            )
                        if cached:
                            tmdb_id = cached["tmdb_id"]
                        else:
                            # Resolve via TMDB API
                            resolved = await self._tmdb.resolve_tvdb_id(s.tvdb_id)
                            if resolved:
                                tmdb_id = resolved
                                async with self._db.acquire() as conn:
                                    await conn.execute(
                                        "INSERT INTO tvdb_tmdb_map (tvdb_id, tmdb_id, title) "
                                        "VALUES ($1, $2, $3) ON CONFLICT (tvdb_id) DO NOTHING",
                                        s.tvdb_id, tmdb_id, s.title,
                                    )
                    if not tmdb_id:
                        self._log.debug(
                            f"Skipping {s.title} — could not resolve TMDB ID (TVDB: {s.tvdb_id})"
                        )
                        continue
                    records_by_tmdb[tmdb_id] = MediaRecord(
                        tmdb_id=tmdb_id,
                        title=s.title,
                        year=s.year,
                        media_type="series",
                        file_size_bytes=s.file_size_bytes,
                        episode_count=s.episode_count,
                        arr_id=s.sonarr_id,
                        arr_source=s.arr_source,
                        added_at=s.added_at,
                    )
                self._log.info(
                    f"Merged {len(series_list)} series from {client_name}"
                )
            else:
                warnings.append(f"{client_name} unavailable")

        # --- Tautulli: watch data ---
        if self._tautulli:
            raw_history = await self._tautulli.get_history()
            summaries = self._tautulli.aggregate_by_media(raw_history)

            # Match Tautulli summaries to existing records by title+year
            # (Tautulli uses Plex rating_keys, not TMDB IDs directly)
            matched = 0
            for record in records_by_tmdb.values():
                for summary in summaries.values():
                    if (
                        summary.title.lower() == record.title.lower()
                        and summary.year == record.year
                    ):
                        record.total_plays = summary.total_plays
                        record.unique_viewers = summary.unique_viewers
                        record.last_watched_at = summary.last_watched_at
                        record.avg_completion_pct = summary.avg_completion_pct
                        matched += 1
                        break

            self._log.info(
                f"Matched Tautulli watch data to {matched}/{len(records_by_tmdb)} titles"
            )
        else:
            warnings.append("Tautulli unavailable")

        # --- Seerr: request data ---
        if self._seerr:
            requests = await self._seerr.get_requests()
            by_tmdb = self._seerr.get_requests_by_tmdb_id(requests)
            matched = 0
            for tmdb_id, record in records_by_tmdb.items():
                req = by_tmdb.get(tmdb_id)
                if req:
                    record.requested_by = req.requested_by
                    record.request_date = req.requested_at
                    # Check if requestor watched it (cross-ref with Tautulli)
                    # For now, mark as watched if the title has any plays
                    # TODO: More precise check against requestor's username
                    record.requestor_watched = record.total_plays > 0
                    matched += 1
            self._log.info(
                f"Matched Seerr requests to {matched}/{len(records_by_tmdb)} titles"
            )
        else:
            warnings.append("Seerr unavailable")

        # --- TMDB: cultural value + streaming availability ---
        if self._tmdb:
            tmdb_ids = [
                (r.tmdb_id, r.media_type) for r in records_by_tmdb.values()
            ]
            tmdb_data = await self._tmdb.batch_fetch(
                tmdb_ids, db_manager=self._db
            )
            enriched = 0
            for tmdb_id, info in tmdb_data.items():
                record = records_by_tmdb.get(tmdb_id)
                if record:
                    record.tmdb_rating = info.vote_average
                    record.tmdb_vote_count = info.vote_count
                    record.streaming_service_count = info.streaming_service_count
                    enriched += 1
            self._log.info(
                f"Enriched {enriched}/{len(records_by_tmdb)} titles with TMDB data"
            )
        else:
            warnings.append("TMDB unavailable — using neutral rarity/cultural scores")

        records = list(records_by_tmdb.values())
        self._log.info(f"Total media records: {len(records)}")
        return records, warnings

    # -----------------------------------------------------------------------
    # Step 2: Score all records
    # -----------------------------------------------------------------------
    def _score_records(
        self,
        records: list[MediaRecord],
        weights: ScoringWeights,
    ) -> list[ScoreBreakdown]:
        """Apply signal calculators and weighted sum to all records.

        Deterministic: same inputs always produce same scores.
        """
        if not records:
            return []

        # Calculate median file size for the size efficiency signal
        sizes = [r.file_size_bytes for r in records if r.file_size_bytes > 0]
        median_size = int(statistics.median(sizes)) if sizes else 1

        scores: list[ScoreBreakdown] = []

        for record in records:
            # Skip protected titles — they still get scored but flagged
            watch = calc_watch_activity(record)
            rarity = calc_rarity(record)
            request = calc_request_accountability(record)
            size_eff = calc_size_efficiency(record, median_size)
            cultural = calc_cultural_value(record)

            # Weighted sum (weights are percentages, signals are 0–100)
            keep_score = (
                watch * (weights.watch_activity / 100.0)
                + rarity * (weights.rarity / 100.0)
                + request * (weights.request_accountability / 100.0)
                + size_eff * (weights.size_efficiency / 100.0)
                + cultural * (weights.cultural_value / 100.0)
            )
            keep_score = round(min(max(keep_score, 0.0), 100.0), 2)

            is_candidate = (
                keep_score < weights.candidate_threshold
                and not record.is_protected
            )

            scores.append(ScoreBreakdown(
                tmdb_id=record.tmdb_id,
                keep_score=keep_score,
                watch_activity_score=round(watch, 2),
                rarity_score=round(rarity, 2),
                request_score=round(request, 2),
                size_efficiency_score=round(size_eff, 2),
                cultural_value_score=round(cultural, 2),
                is_candidate=is_candidate,
                file_size_bytes=record.file_size_bytes,
                title=record.title,
                media_type=record.media_type,
            ))

        return scores

    # -----------------------------------------------------------------------
    # Step 3: Persist results to PostgreSQL
    # -----------------------------------------------------------------------
    async def _persist(
        self,
        run_id: int,
        records: list[MediaRecord],
        scores: list[ScoreBreakdown],
    ) -> None:
        """Write media items, scores, and watch data cache to the DB."""
        async with self._db.acquire() as conn:
            for record in records:
                # Upsert media_items
                await conn.execute(
                    """
                    INSERT INTO media_items (
                        tmdb_id, media_type, title, year, added_at,
                        file_size_bytes, quality_profile, arr_id,
                        arr_source, episode_count
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (tmdb_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        file_size_bytes = EXCLUDED.file_size_bytes,
                        quality_profile = EXCLUDED.quality_profile,
                        arr_id = EXCLUDED.arr_id,
                        arr_source = EXCLUDED.arr_source,
                        episode_count = EXCLUDED.episode_count,
                        updated_at = NOW()
                    """,
                    record.tmdb_id, record.media_type, record.title,
                    record.year, record.added_at, record.file_size_bytes,
                    record.quality_profile, record.arr_id, record.arr_source,
                    record.episode_count,
                )

            # Get media_item IDs for FK references
            rows = await conn.fetch(
                "SELECT id, tmdb_id FROM media_items WHERE tmdb_id = ANY($1)",
                [s.tmdb_id for s in scores],
            )
            id_map = {row["tmdb_id"]: row["id"] for row in rows}

            # Insert scores
            for score in scores:
                item_id = id_map.get(score.tmdb_id)
                if not item_id:
                    continue
                await conn.execute(
                    """
                    INSERT INTO media_scores (
                        media_item_id, scoring_run_id, keep_score,
                        watch_activity_score, rarity_score, request_score,
                        size_efficiency_score, cultural_value_score,
                        is_candidate
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                    item_id, run_id, score.keep_score,
                    score.watch_activity_score, score.rarity_score,
                    score.request_score, score.size_efficiency_score,
                    score.cultural_value_score, score.is_candidate,
                )

            # Insert watch data cache
            for record in records:
                item_id = id_map.get(record.tmdb_id)
                if not item_id:
                    continue
                await conn.execute(
                    """
                    INSERT INTO watch_data_cache (
                        media_item_id, scoring_run_id, total_plays,
                        unique_viewers, last_watched_at, avg_completion_pct,
                        requested_by, requestor_watched, request_date
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                    item_id, run_id, record.total_plays,
                    record.unique_viewers, record.last_watched_at,
                    record.avg_completion_pct, record.requested_by,
                    record.requestor_watched, record.request_date,
                )

    # -----------------------------------------------------------------------
    # Public: Run a full scoring cycle
    # -----------------------------------------------------------------------
    async def run(self, trigger: str = "manual") -> ScoringRunResult:
        """Execute a full scoring run: fetch → merge → score → persist.

        This is the main entry point. Called by APScheduler or manual trigger.
        """
        started_at = datetime.now(timezone.utc)
        self._log.info(f"Scoring run started (trigger: {trigger})")

        # Refresh clients from DB settings (picks up dashboard changes)
        await self._refresh_clients()

        # Create scoring_runs record
        async with self._db.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO scoring_runs (started_at, trigger)
                VALUES ($1, $2)
                RETURNING id
                """,
                started_at, trigger,
            )
            run_id = row["id"]

        result = ScoringRunResult(
            run_id=run_id,
            started_at=started_at,
            trigger=trigger,
        )

        try:
            # Step 1: Fetch and merge
            records, warnings = await self._fetch_all()
            result.partial_data = len(warnings) > 0
            result.notes = "; ".join(warnings) if warnings else ""

            if not records:
                self._log.warning("No media records found — nothing to score")
                result.completed_at = datetime.now(timezone.utc)
                return result

            # Load protected titles
            async with self._db.acquire() as conn:
                protected_rows = await conn.fetch(
                    """
                    SELECT mi.tmdb_id FROM protected_titles pt
                    JOIN media_items mi ON pt.media_item_id = mi.id
                    """
                )
            protected_ids = {row["tmdb_id"] for row in protected_rows}
            for record in records:
                if record.tmdb_id in protected_ids:
                    record.is_protected = True

            # Step 2: Score
            weights = await self._config.get_weights()
            scores = self._score_records(records, weights)

            # Step 3: Persist
            await self._persist(run_id, records, scores)

            # Step 4: Stale candidate detection
            # Titles in media_items that are no longer in *arr responses
            # were deleted outside Swabbarr — auto-move to removal_history
            current_tmdb_ids = {r.tmdb_id for r in records}
            stale_count = 0
            async with self._db.acquire() as conn:
                existing = await conn.fetch(
                    "SELECT id, tmdb_id, title, media_type, file_size_bytes "
                    "FROM media_items"
                )
                for row in existing:
                    if row["tmdb_id"] not in current_tmdb_ids:
                        # Get last score
                        last_score = await conn.fetchval(
                            "SELECT keep_score FROM media_scores "
                            "WHERE media_item_id = $1 ORDER BY scored_at DESC LIMIT 1",
                            row["id"],
                        )
                        await conn.execute(
                            """
                            INSERT INTO removal_history (
                                media_item_id, tmdb_id, title, media_type,
                                file_size_bytes, final_keep_score
                            ) VALUES ($1, $2, $3, $4, $5, $6)
                            """,
                            row["id"], row["tmdb_id"], row["title"],
                            row["media_type"], row["file_size_bytes"],
                            float(last_score) if last_score else None,
                        )
                        stale_count += 1

            if stale_count > 0:
                self._log.info(
                    f"Stale detection: {stale_count} titles removed outside "
                    f"Swabbarr — moved to removal history"
                )

            # Finalize run
            candidates = [s for s in scores if s.is_candidate]
            reclaimable = sum(s.file_size_bytes for s in candidates)
            completed_at = datetime.now(timezone.utc)

            async with self._db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE scoring_runs SET
                        completed_at = $1, titles_scored = $2,
                        candidates_flagged = $3, space_reclaimable_bytes = $4,
                        partial_data = $5, notes = $6
                    WHERE id = $7
                    """,
                    completed_at, len(scores), len(candidates),
                    reclaimable, result.partial_data, result.notes, run_id,
                )

            result.completed_at = completed_at
            result.titles_scored = len(scores)
            result.candidates_flagged = len(candidates)
            result.space_reclaimable_bytes = reclaimable
            result.scores = scores

            reclaimable_gb = reclaimable / (1024 ** 3)
            self._log.success(
                f"Scoring complete: {len(scores)} titles scored, "
                f"{len(candidates)} candidates, "
                f"{reclaimable_gb:.1f} GB reclaimable"
            )

        except Exception as e:
            self._log.error(f"Scoring run failed: {e}", exc_info=True)
            result.notes = f"Run failed: {e}"
            async with self._db.acquire() as conn:
                await conn.execute(
                    "UPDATE scoring_runs SET notes = $1 WHERE id = $2",
                    result.notes, run_id,
                )

        return result


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_scoring_engine(
    db_manager: DBManager,
    config_manager: ConfigManager,
    clients: dict,
    log: logging.Logger,
    build_clients_fn=None,
) -> ScoringEngine:
    """Create a ScoringEngine with all dependencies injected."""
    return ScoringEngine(
        db_manager=db_manager,
        config_manager=config_manager,
        radarr=clients.get("radarr"),
        sonarr=clients.get("sonarr"),
        sonarr_anime=clients.get("sonarr_anime"),
        tautulli=clients.get("tautulli"),
        seerr=clients.get("seerr"),
        tmdb=clients.get("tmdb"),
        log=log,
        build_clients_fn=build_clients_fn,
    )


__all__ = ["ScoringEngine", "create_scoring_engine"]
