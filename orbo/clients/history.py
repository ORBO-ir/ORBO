"""
HTTP client for TSETMC historical and daily price endpoints.
"""
from __future__ import annotations

import logging

import httpx

from orbo.constants import Endpoints, DEFAULT_TIMEOUT, DEFAULT_HEADERS, LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError
from orbo.clients.retry import with_retry

logger = logging.getLogger(LOGGER_NAME)


class TSETMCHistoryClient:
    """
    Thin HTTP wrapper for TSETMC price and corporate-action endpoints.

    All methods return raw parsed JSON dicts. Transformation to
    DataFrames happens in orbo.data.transformers.
    """

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers=DEFAULT_HEADERS,
        )

    @with_retry(retries=3, backoff=1.0)
    def _get_json(self, url: str) -> dict:
        """
        Send a GET request and return the parsed JSON body.

        Retries automatically (3 attempts, exponential backoff) on
        connection issues, server errors, and malformed JSON bodies.

        Raises
        ------
        OrboConnectionError
            On timeout, DNS failure, or unreachable host.
        OrboNotFoundError
            On HTTP 404 (not retried).
        OrboAPIError
            On any other HTTP error status or malformed JSON.
        """
        logger.info("GET %s", url)

        try:
            r = self._client.get(url)
            r.raise_for_status()
            return r.json()

        except httpx.TimeoutException as exc:
            raise OrboConnectionError("Request timed out.") from exc

        except httpx.ConnectError as exc:
            raise OrboConnectionError(
                "TSETMC is unreachable. Check VPN or internet connection."
            ) from exc

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise OrboNotFoundError(url) from exc
            if status >= 500:
                raise OrboAPIError("TSETMC server error.") from exc
            raise OrboAPIError(f"HTTP error {status}.") from exc

        except httpx.RequestError as exc:
            raise OrboConnectionError("Request failed.") from exc

        except ValueError as exc:
            # TSETMC occasionally returns HTTP 200 with a truncated/corrupt body
            raise OrboAPIError(f"Malformed JSON from {url}: {exc}") from exc

    # ── Daily endpoints ─────────────────────────────────────────────────────

    def get_daily_history(self, inscode: str, count: int = 0) -> dict:
        """Fetch historical OHLCV data. count=0 returns full history."""
        url = Endpoints.DAILY_HISTORY.format(inscode=inscode, count=count)
        return self._get_json(url)

    def get_today(self, inscode: str) -> dict:
        """Fetch live price data for the current trading session."""
        url = Endpoints.TODAY_PRICE.format(inscode=inscode)
        return self._get_json(url)

    # ── Corporate action endpoints ──────────────────────────────────────────

    def get_price_adjusts(self, inscode: str) -> list[dict]:
        """Fetch dividend and rights-issue adjustment events."""
        url = Endpoints.PRICE_ADJUST.format(inscode=inscode)
        data = self._get_json(url)
        return data.get("priceAdjust", [])

    def get_share_changes(self, inscode: str) -> list[dict]:
        """Fetch capital increase (share split / bonus share) events."""
        url = Endpoints.SHARE_CHANGE.format(inscode=inscode)
        data = self._get_json(url)
        return data.get("instrumentShareChange", [])

    # ── Instrument state ────────────────────────────────────────────────────

    def get_instrument_state(self, inscode: str) -> list[dict]:
        """Fetch the trading-status change history (allowed, halted, reserved)."""
        url = Endpoints.INSTRUMENT_STATE.format(inscode=inscode)
        data = self._get_json(url)
        return data.get("instrumentState", [])

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "TSETMCHistoryClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
