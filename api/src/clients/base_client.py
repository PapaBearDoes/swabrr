"""
============================================================================
Swabbarr — Media Library Pruning Engine
============================================================================

Base HTTP client with shared retry, timeout, and error handling logic.
All service-specific clients inherit from this class.

----------------------------------------------------------------------------
FILE VERSION: v1.0.1
LAST MODIFIED: 2026-04-02
COMPONENT: swabbarr-api
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/PapaBearDoes/swabbarr
============================================================================
"""

import asyncio
import logging
import os

import httpx


class BaseClient:
    """Shared async HTTP client with retry and resilience."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        log: logging.Logger,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._log = log
        self._timeout = timeout or float(
            os.environ.get("SWABBARR_HTTP_TIMEOUT", "30")
        )
        self._max_retries = max_retries or int(
            os.environ.get("SWABBARR_HTTP_RETRIES", "3")
        )
        self._client: httpx.AsyncClient | None = None

    @property
    def service_name(self) -> str:
        """Override in subclasses to identify the service."""
        return "base"

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-create the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict | list | None:
        """Make an HTTP request with retry and error handling.

        Returns parsed JSON on success, None on failure.
        Never raises — logs errors and returns None for graceful degradation.
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.request(
                    method=method,
                    url=path,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                self._log.warning(
                    f"{self.service_name}: Timeout on {path} "
                    f"(attempt {attempt}/{self._max_retries})"
                )

            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                if status >= 500:
                    self._log.warning(
                        f"{self.service_name}: Server error {status} on {path} "
                        f"(attempt {attempt}/{self._max_retries})"
                    )
                else:
                    # 4xx errors are not retryable
                    # 404s are expected (e.g. TMDB ID no longer exists)
                    log_fn = self._log.debug if status == 404 else self._log.error
                    log_fn(
                        f"{self.service_name}: Client error {status} on {path}: "
                        f"{e.response.text[:200]}"
                    )
                    return None

            except httpx.RequestError as e:
                last_error = e
                self._log.warning(
                    f"{self.service_name}: Connection error on {path} "
                    f"(attempt {attempt}/{self._max_retries}): {e}"
                )

            # Exponential backoff before retry
            if attempt < self._max_retries:
                delay = 2 ** (attempt - 1)
                await asyncio.sleep(delay)

        # All retries exhausted
        self._log.error(
            f"{self.service_name}: All {self._max_retries} attempts failed "
            f"for {path}: {last_error}"
        )
        return None

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict | list | None:
        """Convenience wrapper for GET requests."""
        return await self._request("GET", path, params=params, headers=headers)

    async def health_check(self) -> bool:
        """Verify the service is reachable. Override for custom checks."""
        try:
            client = await self._get_client()
            response = await client.get("/")
            return response.status_code < 500
        except Exception as e:
            self._log.warning(
                f"{self.service_name}: Health check failed: {e}"
            )
            return False

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


__all__ = ["BaseClient"]
