"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Scores router — exposes score results, candidates, breakdowns, trends,
and dashboard summary statistics.

----------------------------------------------------------------------------
FILE VERSION: v1.0.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/scores — Paginated score list (latest run)
# ---------------------------------------------------------------------------
@router.get("")
async def list_scores(
    request: Request,
    media_type: str | None = Query(None, regex="^(movie|series)$"),
    sort_by: str = Query("keep_score", regex="^(keep_score|file_size|title|last_watched)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
):
    """List scores from the latest scoring run with filtering and pagination."""
    db = request.app.state.db_manager

    # Find latest scoring run
    async with db.acquire() as conn:
        latest_run = await conn.fetchrow(
            "SELECT id FROM scoring_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1"
        )
        if not latest_run:
            return {"scores": [], "total": 0, "page": page, "per_page": per_page}

        run_id = latest_run["id"]

        # Build query dynamically
        conditions = ["ms.scoring_run_id = $1"]
        params: list = [run_id]
        idx = 2

        if media_type:
            conditions.append(f"mi.media_type = ${idx}")
            params.append(media_type)
            idx += 1

        if min_score is not None:
            conditions.append(f"ms.keep_score >= ${idx}")
            params.append(min_score)
            idx += 1
        if max_score is not None:
            conditions.append(f"ms.keep_score <= ${idx}")
            params.append(max_score)
            idx += 1

        where = " AND ".join(conditions)

        # Sort mapping
        sort_map = {
            "keep_score": "ms.keep_score",
            "file_size": "mi.file_size_bytes",
            "title": "mi.title",
            "last_watched": "wdc.last_watched_at",
        }
        order_col = sort_map.get(sort_by, "ms.keep_score")
        order_dir = "ASC" if sort_order == "asc" else "DESC"
        nulls = "NULLS LAST" if sort_order == "asc" else "NULLS FIRST"

        # Count total
        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM media_scores ms "
            f"JOIN media_items mi ON ms.media_item_id = mi.id "
            f"LEFT JOIN watch_data_cache wdc ON wdc.media_item_id = mi.id AND wdc.scoring_run_id = ms.scoring_run_id "
            f"WHERE {where}",
            *params,
        )
        total = count_row["total"]

        offset = (page - 1) * per_page
        params.extend([per_page, offset])

        rows = await conn.fetch(
            f"""
            SELECT mi.tmdb_id, mi.title, mi.year, mi.media_type,
                   mi.file_size_bytes, mi.quality_profile, mi.episode_count,
                   mi.poster_url,
                   ms.keep_score, ms.watch_activity_score, ms.rarity_score,
                   ms.request_score, ms.size_efficiency_score,
                   ms.cultural_value_score, ms.is_candidate,
                   wdc.last_watched_at, wdc.total_plays, wdc.unique_viewers,
                   pt.id AS protected_id
            FROM media_scores ms
            JOIN media_items mi ON ms.media_item_id = mi.id
            LEFT JOIN watch_data_cache wdc
                ON wdc.media_item_id = mi.id
                AND wdc.scoring_run_id = ms.scoring_run_id
            LEFT JOIN protected_titles pt ON pt.media_item_id = mi.id
            WHERE {where}
            ORDER BY {order_col} {order_dir} {nulls}
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

    scores = [
        {
            "tmdb_id": r["tmdb_id"],
            "title": r["title"],
            "year": r["year"],
            "media_type": r["media_type"],
            "file_size_bytes": r["file_size_bytes"],
            "quality_profile": r["quality_profile"],
            "episode_count": r["episode_count"],
            "poster_url": r["poster_url"],
            "keep_score": float(r["keep_score"]),
            "watch_activity_score": float(r["watch_activity_score"] or 0),
            "rarity_score": float(r["rarity_score"] or 0),
            "request_score": float(r["request_score"] or 0),
            "size_efficiency_score": float(r["size_efficiency_score"] or 0),
            "cultural_value_score": float(r["cultural_value_score"] or 0),
            "is_candidate": r["is_candidate"],
            "is_protected": r["protected_id"] is not None,
            "last_watched_at": r["last_watched_at"],
            "total_plays": r["total_plays"],
            "unique_viewers": r["unique_viewers"],
        }
        for r in rows
    ]

    return {
        "scores": scores,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# GET /api/scores/candidates — Only titles below threshold
# ---------------------------------------------------------------------------
@router.get("/candidates")
async def list_candidates(
    request: Request,
    media_type: str | None = Query(None, regex="^(movie|series)$"),
    sort_by: str = Query("keep_score", regex="^(keep_score|file_size|title)$"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List only removal candidates from the latest run."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        latest_run = await conn.fetchrow(
            "SELECT id FROM scoring_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1"
        )
        if not latest_run:
            return {"scores": [], "total": 0, "page": page, "per_page": per_page}

        conditions = ["ms.scoring_run_id = $1", "ms.is_candidate = TRUE", "pt.id IS NULL"]
        params: list = [latest_run["id"]]
        idx = 2

        if media_type:
            conditions.append(f"mi.media_type = ${idx}")
            params.append(media_type)
            idx += 1

        where = " AND ".join(conditions)
        sort_map = {"keep_score": "ms.keep_score", "file_size": "mi.file_size_bytes", "title": "mi.title"}
        order_col = sort_map.get(sort_by, "ms.keep_score")
        order_dir = "ASC" if sort_order == "asc" else "DESC"

        count_row = await conn.fetchrow(
            f"SELECT COUNT(*) as total FROM media_scores ms "
            f"JOIN media_items mi ON ms.media_item_id = mi.id "
            f"LEFT JOIN protected_titles pt ON pt.media_item_id = mi.id "
            f"WHERE {where}",
            *params,
        )

        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        rows = await conn.fetch(
            f"""
            SELECT mi.tmdb_id, mi.title, mi.year, mi.media_type,
                   mi.file_size_bytes, mi.poster_url, mi.episode_count,
                   ms.keep_score, ms.watch_activity_score, ms.rarity_score,
                   ms.request_score, ms.size_efficiency_score,
                   ms.cultural_value_score
            FROM media_scores ms
            JOIN media_items mi ON ms.media_item_id = mi.id
            LEFT JOIN protected_titles pt ON pt.media_item_id = mi.id
            WHERE {where}
            ORDER BY {order_col} {order_dir}
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params,
        )

    return {
        "scores": [dict(r) for r in rows],
        "total": count_row["total"],
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# GET /api/scores/summary — Dashboard summary stats
# ---------------------------------------------------------------------------
@router.get("/summary")
async def score_summary(request: Request):
    """Dashboard summary: library size, candidates, reclaimable space."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        latest_run = await conn.fetchrow(
            "SELECT * FROM scoring_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1"
        )
        if not latest_run:
            return {"has_scores": False}

        total_size = await conn.fetchval(
            "SELECT COALESCE(SUM(file_size_bytes), 0) FROM media_items"
        )
        total_removed = await conn.fetchval(
            "SELECT COALESCE(SUM(file_size_bytes), 0) FROM removal_history"
        )

    return {
        "has_scores": True,
        "last_run_at": latest_run["completed_at"].isoformat() if latest_run["completed_at"] else None,
        "last_run_trigger": latest_run["trigger"],
        "titles_scored": latest_run["titles_scored"],
        "candidates_flagged": latest_run["candidates_flagged"],
        "space_reclaimable_bytes": latest_run["space_reclaimable_bytes"],
        "partial_data": latest_run["partial_data"],
        "total_library_bytes": total_size,
        "total_removed_bytes": total_removed,
    }


# ---------------------------------------------------------------------------
# GET /api/scores/{tmdb_id} — Single title score + breakdown
# ---------------------------------------------------------------------------
@router.get("/{tmdb_id}")
async def get_score(request: Request, tmdb_id: int):
    """Get the current score and breakdown for a single title."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT mi.*, ms.keep_score, ms.watch_activity_score,
                   ms.rarity_score, ms.request_score,
                   ms.size_efficiency_score, ms.cultural_value_score,
                   ms.is_candidate, ms.scored_at,
                   wdc.total_plays, wdc.unique_viewers, wdc.last_watched_at,
                   wdc.avg_completion_pct, wdc.requested_by,
                   wdc.requestor_watched, wdc.request_date,
                   pt.id AS protected_id
            FROM media_items mi
            JOIN media_scores ms ON ms.media_item_id = mi.id
            LEFT JOIN watch_data_cache wdc
                ON wdc.media_item_id = mi.id
                AND wdc.scoring_run_id = ms.scoring_run_id
            LEFT JOIN protected_titles pt ON pt.media_item_id = mi.id
            WHERE mi.tmdb_id = $1
            ORDER BY ms.scored_at DESC LIMIT 1
            """,
            tmdb_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Title not found")
    return dict(row) | {"is_protected": row["protected_id"] is not None}


# ---------------------------------------------------------------------------
# GET /api/scores/{tmdb_id}/history — Score trend over past N runs
# ---------------------------------------------------------------------------
@router.get("/{tmdb_id}/history")
async def score_history(
    request: Request,
    tmdb_id: int,
    limit: int = Query(10, ge=1, le=50),
):
    """Get score trend for a title over the last N scoring runs."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ms.keep_score, ms.watch_activity_score, ms.rarity_score,
                   ms.request_score, ms.size_efficiency_score,
                   ms.cultural_value_score, ms.is_candidate, ms.scored_at,
                   sr.started_at AS run_date, sr.trigger
            FROM media_scores ms
            JOIN media_items mi ON ms.media_item_id = mi.id
            JOIN scoring_runs sr ON ms.scoring_run_id = sr.id
            WHERE mi.tmdb_id = $1
            ORDER BY sr.started_at DESC
            LIMIT $2
            """,
            tmdb_id, limit,
        )
    if not rows:
        raise HTTPException(status_code=404, detail="No score history found")
    return {"tmdb_id": tmdb_id, "history": [dict(r) for r in rows]}
