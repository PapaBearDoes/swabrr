"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Pydantic and dataclass models for the scoring engine.
Defines the unified MediaRecord that merges data from all sources,
plus score result models.

----------------------------------------------------------------------------
FILE VERSION: v1.2.0
LAST MODIFIED: 2026-04-04
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MediaRecord:
    """Unified record for a single media title, merged from all sources.

    This is the input to the scoring engine — one record per TMDB ID.
    """

    # Identity (from Radarr/Sonarr)
    tmdb_id: int
    title: str
    year: int | None
    media_type: str  # 'movie' or 'series'
    file_size_bytes: int = 0
    quality_profile: str | None = None
    arr_id: int | None = None
    arr_source: str | None = None  # 'radarr', 'sonarr', 'sonarr-anime'
    episode_count: int | None = None
    poster_url: str | None = None
    added_at: str | None = None

    # Watch data (from Tautulli)
    total_plays: int = 0
    unique_viewers: int = 0
    last_watched_at: str | None = None
    avg_completion_pct: float = 0.0

    # Request data (from Seerr)
    requested_by: str | None = None
    requestor_watched: bool | None = None
    request_date: str | None = None

    # Cultural/rarity data (from TMDB — Phase 7)
    tmdb_rating: float | None = None
    tmdb_vote_count: int | None = None
    streaming_service_count: int | None = None

    # Series status data (from Sonarr — Phase 9)
    series_status: str | None = None  # 'continuing', 'ended', 'upcoming'
    series_total_episodes: int | None = None  # Total known episodes

    # Flags
    is_protected: bool = False


@dataclass
class ScoreBreakdown:
    """Score result for a single media title with full breakdown."""

    tmdb_id: int
    keep_score: float
    watch_activity_score: float
    rarity_score: float
    request_score: float
    size_efficiency_score: float
    cultural_value_score: float
    is_candidate: bool
    file_size_bytes: int = 0
    title: str = ""
    media_type: str = ""


@dataclass
class ScoringWeights:
    """User-configurable scoring weights from the database."""

    watch_activity: float = 40.0
    rarity: float = 20.0
    request_accountability: float = 15.0
    size_efficiency: float = 15.0
    cultural_value: float = 10.0
    candidate_threshold: float = 30.0
    classic_age_threshold: int = 20  # Years — titles older than this get bonus
    classic_bonus_points: float = 5.0  # Flat points added to keep_score (0–10)
    recent_age_threshold: int = 2  # Years — titles newer than this get bonus
    recent_bonus_points: float = 5.0  # Flat points added to keep_score (0–10)


@dataclass
class ScoringRunResult:
    """Summary of a completed scoring run."""

    run_id: int
    started_at: datetime
    completed_at: datetime | None = None
    trigger: str = "manual"
    titles_scored: int = 0
    candidates_flagged: int = 0
    space_reclaimable_bytes: int = 0
    partial_data: bool = False
    notes: str = ""
    scores: list[ScoreBreakdown] = field(default_factory=list)


__all__ = [
    "MediaRecord",
    "ScoreBreakdown",
    "ScoringWeights",
    "ScoringRunResult",
]
