"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Configuration manager for scoring weights and application settings.
Reads from and writes to PostgreSQL via DBManager.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import logging

from src.managers.db_manager import DBManager
from src.scoring.models import ScoringWeights


class ConfigManager:
    """Reads and writes scoring configuration from PostgreSQL."""

    def __init__(self, db_manager: DBManager, log: logging.Logger) -> None:
        self._db = db_manager
        self._log = log

    async def get_weights(self) -> ScoringWeights:
        """Load current scoring weights from the database."""
        async with self._db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM scoring_weights LIMIT 1")

        if row is None:
            self._log.warning("No scoring weights found — using defaults")
            return ScoringWeights()

        return ScoringWeights(
            watch_activity=float(row["watch_activity"]),
            rarity=float(row["rarity"]),
            request_accountability=float(row["request_accountability"]),
            size_efficiency=float(row["size_efficiency"]),
            cultural_value=float(row["cultural_value"]),
            candidate_threshold=float(row["candidate_threshold"]),
        )

    async def update_weights(self, weights: ScoringWeights) -> bool:
        """Update scoring weights in the database.

        Validates that weights sum to 100 before writing.
        Returns True on success, False on validation failure.
        """
        total = (
            weights.watch_activity
            + weights.rarity
            + weights.request_accountability
            + weights.size_efficiency
            + weights.cultural_value
        )
        if abs(total - 100.0) > 0.01:
            self._log.error(f"Weights must sum to 100, got {total}")
            return False

        async with self._db.acquire() as conn:
            await conn.execute(
                """
                UPDATE scoring_weights SET
                    watch_activity = $1,
                    rarity = $2,
                    request_accountability = $3,
                    size_efficiency = $4,
                    cultural_value = $5,
                    candidate_threshold = $6
                WHERE id = 1
                """,
                weights.watch_activity,
                weights.rarity,
                weights.request_accountability,
                weights.size_efficiency,
                weights.cultural_value,
                weights.candidate_threshold,
            )

        self._log.success("Scoring weights updated")
        return True


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_config_manager(
    db_manager: DBManager,
    log: logging.Logger,
) -> ConfigManager:
    """Create a ConfigManager instance."""
    return ConfigManager(db_manager=db_manager, log=log)


__all__ = ["ConfigManager", "create_config_manager"]
