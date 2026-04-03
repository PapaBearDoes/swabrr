"""
============================================================================
Swabrr — Media Library Pruning Engine
============================================================================

Settings manager for external service configuration (URLs and API keys).
API keys are encrypted at rest using pgcrypto. The encryption passphrase
is the only Docker Secret required.

----------------------------------------------------------------------------
FILE VERSION: v1.0.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabrr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabrr
============================================================================
"""

import logging
import os
from dataclasses import dataclass

from src.managers.db_manager import DBManager


@dataclass
class ServiceConfig:
    """Configuration for a single external service."""

    service_name: str
    display_name: str
    base_url: str | None
    api_key: str | None
    enabled: bool
    last_verified: str | None
    verify_status: str


class SettingsManager:
    """Manages external service connection settings in PostgreSQL."""

    def __init__(self, db_manager: DBManager, log: logging.Logger) -> None:
        self._db = db_manager
        self._log = log
        self._passphrase = self._load_passphrase()

    @staticmethod
    def _load_passphrase() -> str:
        """Load encryption passphrase from Docker Secret or env var."""
        secret_path = "/run/secrets/swabrr_encryption_key"
        try:
            with open(secret_path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            # Fallback to env var for development
            key = os.environ.get("SWABRR_ENCRYPTION_KEY", "")
            if not key:
                raise RuntimeError(
                    "No encryption key found. Set SWABRR_ENCRYPTION_KEY "
                    "or provide /run/secrets/swabrr_encryption_key"
                )
            return key

    async def get_all_services(self) -> list[ServiceConfig]:
        """Get all service configurations. API keys are decrypted."""
        async with self._db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT service_name, display_name, base_url, enabled,
                       last_verified, verify_status,
                       pgp_sym_decrypt(api_key_enc, $1) AS api_key
                FROM service_settings
                ORDER BY id
                """,
                self._passphrase,
            )
        services = []
        for r in rows:
            api_key = None
            try:
                api_key = r["api_key"]
            except Exception:
                pass  # Decryption returns None if no key stored
            services.append(
                ServiceConfig(
                    service_name=r["service_name"],
                    display_name=r["display_name"],
                    base_url=r["base_url"],
                    api_key=api_key,
                    enabled=r["enabled"],
                    last_verified=r["last_verified"].isoformat()
                    if r["last_verified"]
                    else None,
                    verify_status=r["verify_status"] or "unknown",
                )
            )
        return services

    async def get_service(self, service_name: str) -> ServiceConfig | None:
        """Get a single service configuration."""
        async with self._db.acquire() as conn:
            r = await conn.fetchrow(
                """
                SELECT service_name, display_name, base_url, enabled,
                       last_verified, verify_status,
                       pgp_sym_decrypt(api_key_enc, $1) AS api_key
                FROM service_settings
                WHERE service_name = $2
                """,
                self._passphrase,
                service_name,
            )
        if not r:
            return None
        api_key = None
        try:
            api_key = r["api_key"]
        except Exception:
            pass
        return ServiceConfig(
            service_name=r["service_name"],
            display_name=r["display_name"],
            base_url=r["base_url"],
            api_key=api_key,
            enabled=r["enabled"],
            last_verified=r["last_verified"].isoformat()
            if r["last_verified"]
            else None,
            verify_status=r["verify_status"] or "unknown",
        )

    async def update_service(
        self,
        service_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """Update a service's connection settings.

        Only updates fields that are provided (not None).
        API key is encrypted before storage.
        """
        async with self._db.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM service_settings WHERE service_name = $1",
                service_name,
            )
            if not existing:
                self._log.error(f"Service '{service_name}' not found")
                return False

            if base_url is not None:
                await conn.execute(
                    "UPDATE service_settings SET base_url = $1 WHERE service_name = $2",
                    base_url,
                    service_name,
                )

            if api_key is not None:
                await conn.execute(
                    """
                    UPDATE service_settings
                    SET api_key_enc = pgp_sym_encrypt($1, $2)
                    WHERE service_name = $3
                    """,
                    api_key,
                    self._passphrase,
                    service_name,
                )
                # Auto-enable when an API key is provided
                if enabled is None:
                    await conn.execute(
                        "UPDATE service_settings SET enabled = TRUE WHERE service_name = $1",
                        service_name,
                    )

            if enabled is not None:
                await conn.execute(
                    "UPDATE service_settings SET enabled = $1 WHERE service_name = $2",
                    enabled,
                    service_name,
                )

        self._log.success(f"Service '{service_name}' settings updated")
        return True

    async def update_verify_status(
        self,
        service_name: str,
        status: str,
    ) -> None:
        """Update the verification status after a health check."""
        async with self._db.acquire() as conn:
            await conn.execute(
                """
                UPDATE service_settings
                SET verify_status = $1, last_verified = NOW()
                WHERE service_name = $2
                """,
                status,
                service_name,
            )


# ---------------------------------------------------------------------------
# Factory function (Rule #1)
# ---------------------------------------------------------------------------
def create_settings_manager(
    db_manager: DBManager,
    log: logging.Logger,
) -> SettingsManager:
    """Create a SettingsManager instance."""
    return SettingsManager(db_manager=db_manager, log=log)


__all__ = ["SettingsManager", "ServiceConfig", "create_settings_manager"]
