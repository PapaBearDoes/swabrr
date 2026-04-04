-- ============================================================================
-- Migration 003: Add recent title bonus settings to scoring_weights
-- ============================================================================
-- Adds two configurable columns:
--   recent_age_threshold   — max age in years to qualify (1–5)
--   recent_bonus_points    — flat bonus added to keep_score (0–10)
--
-- FILE VERSION: v1.0.0
-- LAST MODIFIED: 2026-04-04
-- COMPONENT: swabrr-db
-- ============================================================================

ALTER TABLE scoring_weights
    ADD COLUMN IF NOT EXISTS recent_age_threshold INTEGER NOT NULL DEFAULT 2,
    ADD COLUMN IF NOT EXISTS recent_bonus_points  NUMERIC(4,1) NOT NULL DEFAULT 5.0;
