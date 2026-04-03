"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Scheduler manager using APScheduler. Runs scoring jobs on a cron schedule
inside the FastAPI process. Provides next-run info and schedule management.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.scoring.engine import ScoringEngine

SCORING_JOB_ID = "swabrr_scoring_run"


class SchedulerManager:
    """Manages APScheduler for automated scoring runs."""

    def __init__(
        self,
        scoring_engine: ScoringEngine,
        log: logging.Logger,
    ) -> None:
        self._engine = scoring_engine
        self._log = log
        self._scheduler = AsyncIOScheduler()
        self._cron_expr = os.environ.get("SWABRR_SCORE_CRON", "0 3 * * 0")

    async def _run_scoring(self) -> None:
        """Callback executed by APScheduler on schedule."""
        self._log.info("Scheduled scoring run triggered")
        try:
            result = await self._engine.run(trigger="scheduled")
            self._log.success(
                f"Scheduled run complete: {result.titles_scored} scored, "
                f"{result.candidates_flagged} candidates"
            )
        except Exception as e:
            self._log.error(f"Scheduled scoring run failed: {e}", exc_info=True)

    def start(self) -> None:
        """Start the scheduler with the configured cron expression."""
        trigger = self._parse_cron(self._cron_expr)
        self._scheduler.add_job(
            self._run_scoring,
            trigger=trigger,
            id=SCORING_JOB_ID,
            name="Swabrr Scoring Run",
            replace_existing=True,
        )
        self._scheduler.start()
        next_run = self.get_next_run()
        self._log.success(
            f"Scheduler started — cron: {self._cron_expr}, next run: {next_run}"
        )

    def stop(self) -> None:
        """Shut down the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._log.info("Scheduler stopped")

    def get_next_run(self) -> str | None:
        """Get the next scheduled run time as ISO string."""
        job = self._scheduler.get_job(SCORING_JOB_ID)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return None

    def get_schedule(self) -> dict:
        """Get current schedule info."""
        return {
            "cron_expression": self._cron_expr,
            "next_run": self.get_next_run(),
            "scheduler_running": self._scheduler.running,
        }

    def update_schedule(self, cron_expr: str) -> bool:
        """Update the scoring schedule with a new cron expression."""
        try:
            trigger = self._parse_cron(cron_expr)
        except ValueError as e:
            self._log.error(f"Invalid cron expression '{cron_expr}': {e}")
            return False

        self._cron_expr = cron_expr
        self._scheduler.reschedule_job(
            SCORING_JOB_ID,
            trigger=trigger,
        )
        next_run = self.get_next_run()
        self._log.success(f"Schedule updated — cron: {cron_expr}, next run: {next_run}")
        return True

    @staticmethod
    def _parse_cron(expr: str) -> CronTrigger:
        """Parse a standard 5-field cron expression into an APScheduler trigger.

        Format: minute hour day_of_month month day_of_week
        """
        parts = expr.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Expected 5 fields, got {len(parts)}")
        return CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_scheduler_manager(
    scoring_engine: ScoringEngine,
    log: logging.Logger,
) -> SchedulerManager:
    """Create a SchedulerManager instance."""
    return SchedulerManager(scoring_engine=scoring_engine, log=log)


__all__ = ["SchedulerManager", "create_scheduler_manager"]
