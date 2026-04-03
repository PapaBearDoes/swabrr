"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Actions router — trigger scoring runs, mark titles as removed,
view removal history.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import asyncio

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# Module-level lock to prevent concurrent scoring runs
_scoring_lock = asyncio.Lock()
_scoring_status = {"running": False, "last_result": None}


@router.post("/score")
async def trigger_scoring_run(request: Request):
    """Trigger a manual scoring run."""
    if _scoring_lock.locked():
        raise HTTPException(
            status_code=409, detail="A scoring run is already in progress"
        )

    engine = request.app.state.scoring_engine

    async def _run():
        _scoring_status["running"] = True
        try:
            result = await engine.run(trigger="manual")
            _scoring_status["last_result"] = {
                "run_id": result.run_id,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat()
                if result.completed_at
                else None,
                "titles_scored": result.titles_scored,
                "candidates_flagged": result.candidates_flagged,
                "space_reclaimable_bytes": result.space_reclaimable_bytes,
                "partial_data": result.partial_data,
                "notes": result.notes,
            }
        finally:
            _scoring_status["running"] = False

    async with _scoring_lock:
        asyncio.create_task(_run())

    return {"status": "started", "message": "Scoring run initiated"}


# ---------------------------------------------------------------------------
# GET /api/actions/status — Current run status
# ---------------------------------------------------------------------------
@router.get("/status")
async def get_status(request: Request):
    """Get current scoring run status and schedule info."""
    scheduler = getattr(request.app.state, "scheduler", None)
    schedule_info = scheduler.get_schedule() if scheduler else None
    return {
        "running": _scoring_status["running"],
        "last_result": _scoring_status["last_result"],
        "schedule": schedule_info,
    }


# ---------------------------------------------------------------------------
# POST /api/actions/remove/{tmdb_id} — Mark title as removed
# ---------------------------------------------------------------------------
@router.post("/remove/{tmdb_id}")
async def mark_removed(request: Request, tmdb_id: int):
    """Mark a title as removed. User has already deleted it in Radarr/Sonarr."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        item = await conn.fetchrow(
            "SELECT * FROM media_items WHERE tmdb_id = $1", tmdb_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Title not found")

        # Get the most recent score for this title
        score_row = await conn.fetchrow(
            """
            SELECT keep_score FROM media_scores
            WHERE media_item_id = $1
            ORDER BY scored_at DESC LIMIT 1
            """,
            item["id"],
        )
        final_score = float(score_row["keep_score"]) if score_row else None

        # Insert into removal history
        await conn.execute(
            """
            INSERT INTO removal_history (
                media_item_id, tmdb_id, title, media_type,
                file_size_bytes, final_keep_score
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            item["id"],
            item["tmdb_id"],
            item["title"],
            item["media_type"],
            item["file_size_bytes"],
            final_score,
        )

        # Remove from protected titles if it was protected
        await conn.execute(
            "DELETE FROM protected_titles WHERE media_item_id = $1",
            item["id"],
        )

    return {
        "status": "removed",
        "tmdb_id": tmdb_id,
        "title": item["title"],
        "file_size_bytes": item["file_size_bytes"],
        "final_keep_score": final_score,
    }


# ---------------------------------------------------------------------------
# GET /api/actions/removal-history — Removal history with space reclaimed
# ---------------------------------------------------------------------------
@router.get("/removal-history")
async def removal_history(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Get removal history with cumulative space reclaimed."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM removal_history")
        total_removed = await conn.fetchval(
            "SELECT COALESCE(SUM(file_size_bytes), 0) FROM removal_history"
        )

        offset = (page - 1) * per_page
        rows = await conn.fetch(
            """
            SELECT tmdb_id, title, media_type, file_size_bytes,
                   final_keep_score, removed_at
            FROM removal_history
            ORDER BY removed_at DESC
            LIMIT $1 OFFSET $2
            """,
            per_page,
            offset,
        )

    return {
        "removals": [dict(r) for r in rows],
        "total": count_row["total"],
        "total_removed_bytes": total_removed,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# GET /api/actions/schedule — Get current schedule
# ---------------------------------------------------------------------------
@router.get("/schedule")
async def get_schedule(request: Request):
    """Get the current scoring schedule."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")
    return scheduler.get_schedule()


class ScheduleUpdate(BaseModel):
    """Request body for updating the schedule."""

    cron_expression: str


# ---------------------------------------------------------------------------
# PUT /api/actions/schedule — Update schedule
# ---------------------------------------------------------------------------
@router.put("/schedule")
async def update_schedule(request: Request, body: ScheduleUpdate):
    """Update the scoring schedule cron expression."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        raise HTTPException(status_code=503, detail="Scheduler not initialized")

    success = scheduler.update_schedule(body.cron_expression)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid cron expression")
    return scheduler.get_schedule()


# ---------------------------------------------------------------------------
# GET /api/actions/runs — Scoring run history
# ---------------------------------------------------------------------------
@router.get("/runs")
async def run_history(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Get past scoring run history with stats."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        count_row = await conn.fetchrow("SELECT COUNT(*) as total FROM scoring_runs")
        offset = (page - 1) * per_page
        rows = await conn.fetch(
            """
            SELECT id, started_at, completed_at, trigger,
                   titles_scored, candidates_flagged,
                   space_reclaimable_bytes, partial_data, notes
            FROM scoring_runs
            ORDER BY started_at DESC
            LIMIT $1 OFFSET $2
            """,
            per_page,
            offset,
        )

    return {
        "runs": [dict(r) for r in rows],
        "total": count_row["total"],
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# POST /api/actions/remove-batch — Batch mark titles as removed
# ---------------------------------------------------------------------------
class BatchRemoveRequest(BaseModel):
    """Request body for batch removal."""

    tmdb_ids: list[int]


@router.post("/remove-batch")
async def batch_mark_removed(request: Request, body: BatchRemoveRequest):
    """Mark multiple titles as removed in one operation."""
    if not body.tmdb_ids:
        return {"status": "no_items", "removed": [], "total_freed_bytes": 0}

    db = request.app.state.db_manager
    removed = []
    total_freed = 0

    async with db.acquire() as conn:
        for tmdb_id in body.tmdb_ids:
            item = await conn.fetchrow(
                "SELECT * FROM media_items WHERE tmdb_id = $1", tmdb_id
            )
            if not item:
                continue

            score_row = await conn.fetchrow(
                "SELECT keep_score FROM media_scores "
                "WHERE media_item_id = $1 ORDER BY scored_at DESC LIMIT 1",
                item["id"],
            )
            final_score = float(score_row["keep_score"]) if score_row else None

            await conn.execute(
                """
                INSERT INTO removal_history (
                    media_item_id, tmdb_id, title, media_type,
                    file_size_bytes, final_keep_score
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                item["id"],
                item["tmdb_id"],
                item["title"],
                item["media_type"],
                item["file_size_bytes"],
                final_score,
            )
            await conn.execute(
                "DELETE FROM protected_titles WHERE media_item_id = $1",
                item["id"],
            )

            total_freed += item["file_size_bytes"]
            removed.append(
                {
                    "tmdb_id": tmdb_id,
                    "title": item["title"],
                    "file_size_bytes": item["file_size_bytes"],
                }
            )

    return {
        "status": "removed",
        "removed": removed,
        "total_freed_bytes": total_freed,
    }


# ---------------------------------------------------------------------------
# GET /api/actions/export/candidates — CSV export of candidates
# ---------------------------------------------------------------------------
@router.get("/export/candidates")
async def export_candidates(request: Request):
    """Export current removal candidates as CSV."""
    from fastapi.responses import StreamingResponse
    import io, csv

    db = request.app.state.db_manager
    async with db.acquire() as conn:
        latest_run = await conn.fetchrow(
            "SELECT id FROM scoring_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT 1"
        )
        if not latest_run:
            return StreamingResponse(
                iter(["No scoring data available"]),
                media_type="text/csv",
            )

        rows = await conn.fetch(
            """
            SELECT mi.tmdb_id, mi.title, mi.year, mi.media_type,
                   mi.file_size_bytes, ms.keep_score,
                   ms.watch_activity_score, ms.rarity_score,
                   ms.request_score, ms.size_efficiency_score,
                   ms.cultural_value_score
            FROM media_scores ms
            JOIN media_items mi ON ms.media_item_id = mi.id
            WHERE ms.scoring_run_id = $1 AND ms.is_candidate = TRUE
            ORDER BY ms.keep_score ASC
            """,
            latest_run["id"],
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tmdb_id",
            "title",
            "year",
            "type",
            "size_bytes",
            "keep_score",
            "watch_activity",
            "rarity",
            "request",
            "size_efficiency",
            "cultural_value",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["tmdb_id"],
                r["title"],
                r["year"],
                r["media_type"],
                r["file_size_bytes"],
                float(r["keep_score"]),
                float(r["watch_activity_score"] or 0),
                float(r["rarity_score"] or 0),
                float(r["request_score"] or 0),
                float(r["size_efficiency_score"] or 0),
                float(r["cultural_value_score"] or 0),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=swabrr-candidates.csv"},
    )


# ---------------------------------------------------------------------------
# GET /api/actions/export/history — CSV export of removal history
# ---------------------------------------------------------------------------
@router.get("/export/history")
async def export_history(request: Request):
    """Export removal history as CSV."""
    from fastapi.responses import StreamingResponse
    import io, csv

    db = request.app.state.db_manager
    async with db.acquire() as conn:
        rows = await conn.fetch(
            "SELECT tmdb_id, title, media_type, file_size_bytes, "
            "final_keep_score, removed_at FROM removal_history "
            "ORDER BY removed_at DESC"
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "tmdb_id",
            "title",
            "type",
            "size_bytes",
            "final_score",
            "removed_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["tmdb_id"],
                r["title"],
                r["media_type"],
                r["file_size_bytes"],
                float(r["final_keep_score"]) if r["final_keep_score"] else "",
                r["removed_at"].isoformat() if r["removed_at"] else "",
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=swabrr-removal-history.csv"
        },
    )
