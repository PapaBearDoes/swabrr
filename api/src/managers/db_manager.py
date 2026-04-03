"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

PostgreSQL connection pool manager using asyncpg.
Provides the acquire() context manager pattern for all database access.

----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-04-01
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import asyncpg
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator


class DBManager:
    """Manages the asyncpg connection pool for PostgreSQL."""

    def __init__(self, pool: asyncpg.Pool, log: logging.Logger) -> None:
        """Constructor with dependency injection. log is always last."""
        self._pool = pool
        self._log = log

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection from the pool as an async context manager."""
        try:
            async with self._pool.acquire() as conn:
                yield conn
        except asyncpg.PostgresError as e:
            self._log.error(f"Database error during acquire: {e}")
            raise
        except Exception as e:
            self._log.error(f"Unexpected error during acquire: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        await self._pool.close()
        self._log.info("Database connection pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        """Expose pool for health checks only."""
        return self._pool


# ---------------------------------------------------------------------------
# Secret reader (Rule #7)
# ---------------------------------------------------------------------------
def _read_secret(path: str) -> str:
    """Read a Docker Secret from its file path. Strips trailing whitespace."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise RuntimeError(f"Docker Secret not found at: {path}")
    except PermissionError:
        raise RuntimeError(f"Cannot read Docker Secret at: {path} — permission denied")


# ---------------------------------------------------------------------------
# Factory function (Rule #1: NEVER call constructor directly)
# ---------------------------------------------------------------------------
async def create_db_manager(log: logging.Logger) -> DBManager:
    """Create a DBManager with a connected asyncpg pool.

    Reads connection parameters from environment variables and
    the database password from Docker Secrets.
    """
    host = os.environ.get("SWABRR_DB_HOST", "swabrr-db")
    port = int(os.environ.get("SWABRR_DB_PORT", "5432"))
    database = os.environ.get("SWABRR_DB_NAME", "swabrr")
    user = os.environ.get("SWABRR_DB_USER", "swabrr")

    # Read password from Docker Secret
    secret_path = "/run/secrets/swabrr_db_password"
    password = _read_secret(secret_path)

    log.info(f"Connecting to PostgreSQL at {host}:{port}/{database}")

    try:
        pool = await asyncpg.create_pool(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl=False,
        )
    except Exception as e:
        log.critical(f"Failed to create database pool: {e}")
        raise

    log.success(
        f"Database pool created ({pool.get_min_size()}-{pool.get_max_size()} connections)"
    )
    return DBManager(pool=pool, log=log)


__all__ = ["DBManager", "create_db_manager"]
