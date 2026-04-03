"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Media router — media details, protect/unprotect titles.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ProtectRequest(BaseModel):
    """Optional reason for protecting a title."""

    reason: str | None = None


@router.get("/{tmdb_id}")
async def get_media_detail(request: Request, tmdb_id: int):
    """Get full media details including watch data and score."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM media_items WHERE tmdb_id = $1", tmdb_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Title not found")

        protected = await conn.fetchrow(
            "SELECT * FROM protected_titles WHERE media_item_id = $1",
            row["id"],
        )

    return dict(row) | {
        "is_protected": protected is not None,
        "protect_reason": protected["reason"] if protected else None,
    }


@router.post("/{tmdb_id}/protect")
async def protect_title(
    request: Request, tmdb_id: int, body: ProtectRequest | None = None
):
    """Add a title to the protected list."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        item = await conn.fetchrow(
            "SELECT id FROM media_items WHERE tmdb_id = $1", tmdb_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Title not found")

        reason = body.reason if body else None
        await conn.execute(
            """
            INSERT INTO protected_titles (media_item_id, reason)
            VALUES ($1, $2)
            ON CONFLICT (media_item_id) DO UPDATE SET reason = $2
            """,
            item["id"],
            reason,
        )
    return {"status": "protected", "tmdb_id": tmdb_id}


@router.delete("/{tmdb_id}/protect")
async def unprotect_title(request: Request, tmdb_id: int):
    """Remove a title from the protected list."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        item = await conn.fetchrow(
            "SELECT id FROM media_items WHERE tmdb_id = $1", tmdb_id
        )
        if not item:
            raise HTTPException(status_code=404, detail="Title not found")
        await conn.execute(
            "DELETE FROM protected_titles WHERE media_item_id = $1",
            item["id"],
        )
    return {"status": "unprotected", "tmdb_id": tmdb_id}


@router.get("/protected/list")
async def list_protected(request: Request):
    """List all protected titles."""
    db = request.app.state.db_manager
    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mi.tmdb_id, mi.title, mi.year, mi.media_type,
                   mi.file_size_bytes, mi.poster_url,
                   pt.reason, pt.protected_at
            FROM protected_titles pt
            JOIN media_items mi ON pt.media_item_id = mi.id
            ORDER BY pt.protected_at DESC
            """
        )
    return {"protected": [dict(r) for r in rows]}
