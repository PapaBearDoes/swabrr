-- ============================================================================
-- Swabbarr — Media Library Pruning Engine
-- ============================================================================
--
-- Full PostgreSQL schema for Swabbarr.
-- Apply with: psql -U swabbarr -d swabbarr -f schema.sql
--
-- FILE VERSION: v1.0.0
-- LAST MODIFIED: 2026-04-01
-- COMPONENT: swabbarr-db
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Extensions
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- Table: media_items
-- Canonical record for every title in the library.
-- Created during data ingestion, updated on each scoring run.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_items (
    id              SERIAL PRIMARY KEY,
    tmdb_id         INTEGER NOT NULL UNIQUE,
    media_type      VARCHAR(10) NOT NULL CHECK (media_type IN ('movie', 'series')),
    title           VARCHAR(500) NOT NULL,
    year            INTEGER,
    added_at        TIMESTAMPTZ,
    file_size_bytes BIGINT DEFAULT 0,
    quality_profile VARCHAR(100),
    arr_id          INTEGER,
    arr_source      VARCHAR(20) CHECK (arr_source IN ('radarr', 'sonarr', 'sonarr-anime')),
    episode_count   INTEGER,
    poster_url      VARCHAR(500),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_items_tmdb_id ON media_items (tmdb_id);
CREATE INDEX IF NOT EXISTS idx_media_items_media_type ON media_items (media_type);

-- ----------------------------------------------------------------------------
-- Table: scoring_runs
-- One row per scoring execution. Tracks when runs happen and their outcomes.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scoring_runs (
    id                      SERIAL PRIMARY KEY,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    trigger                 VARCHAR(20) NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
    titles_scored           INTEGER DEFAULT 0,
    candidates_flagged      INTEGER DEFAULT 0,
    space_reclaimable_bytes BIGINT DEFAULT 0,
    partial_data            BOOLEAN NOT NULL DEFAULT FALSE,
    notes                   TEXT
);

-- ----------------------------------------------------------------------------
-- Table: media_scores
-- Per-title, per-run score results with full breakdown.
-- This is the heart of the audit trail — every score is explainable.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS media_scores (
    id                      SERIAL PRIMARY KEY,
    media_item_id           INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    scoring_run_id          INTEGER NOT NULL REFERENCES scoring_runs(id) ON DELETE CASCADE,
    keep_score              NUMERIC(5,2) NOT NULL,
    watch_activity_score    NUMERIC(5,2),
    rarity_score            NUMERIC(5,2),
    request_score           NUMERIC(5,2),
    size_efficiency_score   NUMERIC(5,2),
    cultural_value_score    NUMERIC(5,2),
    is_candidate            BOOLEAN NOT NULL DEFAULT FALSE,
    scored_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_media_score_per_run UNIQUE (media_item_id, scoring_run_id)
);

CREATE INDEX IF NOT EXISTS idx_media_scores_item ON media_scores (media_item_id);
CREATE INDEX IF NOT EXISTS idx_media_scores_run ON media_scores (scoring_run_id);
CREATE INDEX IF NOT EXISTS idx_media_scores_keep ON media_scores (keep_score);
CREATE INDEX IF NOT EXISTS idx_media_scores_candidate ON media_scores (is_candidate) WHERE is_candidate = TRUE;

-- ----------------------------------------------------------------------------
-- Table: scoring_weights
-- User-configurable weights. Single row, updated via dashboard.
-- Check constraint ensures weights always sum to 100.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scoring_weights (
    id                      SERIAL PRIMARY KEY,
    watch_activity          NUMERIC(5,2) NOT NULL DEFAULT 40.00,
    rarity                  NUMERIC(5,2) NOT NULL DEFAULT 20.00,
    request_accountability  NUMERIC(5,2) NOT NULL DEFAULT 15.00,
    size_efficiency         NUMERIC(5,2) NOT NULL DEFAULT 15.00,
    cultural_value          NUMERIC(5,2) NOT NULL DEFAULT 10.00,
    candidate_threshold     NUMERIC(5,2) NOT NULL DEFAULT 30.00,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_weights_sum_100 CHECK (
        watch_activity + rarity + request_accountability
        + size_efficiency + cultural_value = 100.00
    )
);

-- ----------------------------------------------------------------------------
-- Table: protected_titles
-- Titles manually flagged as "never suggest for removal."
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protected_titles (
    id              SERIAL PRIMARY KEY,
    media_item_id   INTEGER NOT NULL UNIQUE REFERENCES media_items(id) ON DELETE CASCADE,
    reason          VARCHAR(500),
    protected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Table: removal_history
-- Tracks items the user has removed and marked complete in the dashboard.
-- Intentionally preserves data even after the media_item record is gone.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS removal_history (
    id              SERIAL PRIMARY KEY,
    media_item_id   INTEGER REFERENCES media_items(id) ON DELETE SET NULL,
    tmdb_id         INTEGER NOT NULL,
    title           VARCHAR(500) NOT NULL,
    media_type      VARCHAR(10) NOT NULL CHECK (media_type IN ('movie', 'series')),
    file_size_bytes BIGINT DEFAULT 0,
    final_keep_score NUMERIC(5,2),
    removed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Table: watch_data_cache
-- Raw watch/request data from Tautulli and Seerr, cached per scoring run
-- to provide a data snapshot for auditability.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS watch_data_cache (
    id                  SERIAL PRIMARY KEY,
    media_item_id       INTEGER NOT NULL REFERENCES media_items(id) ON DELETE CASCADE,
    scoring_run_id      INTEGER NOT NULL REFERENCES scoring_runs(id) ON DELETE CASCADE,
    total_plays         INTEGER NOT NULL DEFAULT 0,
    unique_viewers      INTEGER NOT NULL DEFAULT 0,
    last_watched_at     TIMESTAMPTZ,
    avg_completion_pct  NUMERIC(5,2),
    requested_by        VARCHAR(100),
    requestor_watched   BOOLEAN,
    request_date        TIMESTAMPTZ,

    CONSTRAINT uq_watch_cache_per_run UNIQUE (media_item_id, scoring_run_id)
);

-- ----------------------------------------------------------------------------
-- Table: tvdb_tmdb_map
-- Cache for TVDB → TMDB ID resolution (Sonarr series use TVDB IDs).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tvdb_tmdb_map (
    id          SERIAL PRIMARY KEY,
    tvdb_id     INTEGER NOT NULL UNIQUE,
    tmdb_id     INTEGER NOT NULL,
    title       VARCHAR(500),
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tvdb_tmdb_map_tvdb ON tvdb_tmdb_map (tvdb_id);

-- ----------------------------------------------------------------------------
-- Table: tmdb_cache
-- Cached TMDB data per title. Streaming availability refreshes every 7 days,
-- cultural data (ratings, vote count) every 30 days.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tmdb_cache (
    id                      SERIAL PRIMARY KEY,
    tmdb_id                 INTEGER NOT NULL UNIQUE,
    media_type              VARCHAR(10) NOT NULL CHECK (media_type IN ('movie', 'series')),
    vote_average            NUMERIC(4,2),
    vote_count              INTEGER DEFAULT 0,
    streaming_services      TEXT,
    streaming_service_count INTEGER DEFAULT 0,
    streaming_region        VARCHAR(5) DEFAULT 'US',
    genres                  TEXT,
    release_date            VARCHAR(20),
    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    streaming_expires_at    TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days',
    cultural_expires_at     TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX IF NOT EXISTS idx_tmdb_cache_tmdb_id ON tmdb_cache (tmdb_id);

-- ----------------------------------------------------------------------------
-- Seed data: default scoring weights (single row)
-- ----------------------------------------------------------------------------
INSERT INTO scoring_weights (watch_activity, rarity, request_accountability, size_efficiency, cultural_value, candidate_threshold)
VALUES (40.00, 20.00, 15.00, 15.00, 10.00, 30.00)
ON CONFLICT DO NOTHING;

-- ----------------------------------------------------------------------------
-- Function: update_updated_at()
-- Auto-update the updated_at timestamp on row modification.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER trg_media_items_updated_at
    BEFORE UPDATE ON media_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_scoring_weights_updated_at
    BEFORE UPDATE ON scoring_weights
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
