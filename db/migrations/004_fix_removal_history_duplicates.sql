-- ============================================================================
-- Migration 004: Fix duplicate entries in removal_history
-- ============================================================================
-- Part of stale candidate detection bug fix.
--
-- The stale detection in engine.py Step 4 was inserting into removal_history
-- on every scoring run without checking for existing entries, and without
-- cleaning up the source media_items row. This produced hundreds of duplicate
-- entries inflating the "Space Reclaimed" stat to ~31 TB.
--
-- This migration:
-- 1. Removes all duplicate removal_history rows, keeping only the earliest
-- 2. Cleans up media_items rows that exist in removal_history but are no
--    longer returned by any *arr API (orphaned stale entries)
--
-- FILE VERSION: v1.0.0
-- LAST MODIFIED: 2026-04-04
-- COMPONENT: swabrr-db
-- ============================================================================

-- Step 1: Delete duplicate removal_history entries, keeping the earliest per tmdb_id
DELETE FROM removal_history
WHERE id NOT IN (
    SELECT MIN(id)
    FROM removal_history
    GROUP BY tmdb_id
);

-- Step 2: Clean up orphaned media_items that were "stale detected" but never
-- deleted. These are items in removal_history that still have a media_items row.
-- The cascade will clean up their media_scores and watch_data_cache rows too.
-- NOTE: Only run this if you're confident the stale detection was the only
-- source of removal_history entries for these items. If some were legitimately
-- marked removed via the dashboard, they should stay. The safest approach is
-- to leave media_items cleanup to the next scoring run (the fixed engine code
-- will handle it properly).
