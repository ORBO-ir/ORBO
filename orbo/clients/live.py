"""
HTTP client for TSETMC live / real-time endpoints.

These endpoints return the current session state without a date parameter.
They are polled repeatedly (typically every 1–3 seconds) to get live data.
"""
from __future__ import annotations

import logging

import httpx

from orbo.constants import Endpoints, DEFAULT_TIMEOUT, DEFAULT_HEADERS, LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError
from orbo.clients.retry import with_retry

logger = logging.getLogger(LOGGER_NAME)


class TSETMCLiveClient:
    """
    Thin HTTP wrapper for TSETMC live (no-date) endpoints.

    All methods return raw parsed JSON. Transformation to DataFrames
    is done in orbo.data.transformers or on the LiveSnapshot object.

    Note
    ----
    TSETMC has no WebSocket feed. Live data is obtained by polling these
    REST endpoints. The site polls GetClosingPriceInfo every ~1 second.
    Consecutive calls to this client will reflect the latest server state.

    Examples
    --------
        with TSETMCLiveClient() as client:
            price  = client.get_live_price("51017863148152520")
            trades = client.get_live_trades("51017863148152520")
            book   = client.get_live_orderbook("51017863148152520")
    """

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers=DEFAULT_HEADERS,
        )

    @with_retry(retries=3, backoff=1.0)
    def _get_json(self, url: str) -> dict:
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
            raise OrboAPIError(f"Malformed JSON from {url}: {exc}") from exc

    @with_retry(retries=3, backoff=1.0)
    def _get_text(self, url: str) -> str:
        logger.info("GET %s", url)
        try:
            r = self._client.get(url)
            r.raise_for_status()
            return r.text.strip()
        except httpx.RequestError as exc:
            raise OrboConnectionError("Request failed.") from exc

    # ── Live price ───────────────────────────────────────────────────────────

    def get_live_price(self, inscode: str) -> dict:
        """
        Fetch the live price snapshot for the current trading session.

        Returns the same structure as GetClosingPriceInfo — the same
        endpoint used by today() in InstrumentHistory. Call repeatedly
        to get updated prices during a live session.
        """
        url = Endpoints.TODAY_PRICE.format(inscode=inscode)
        return self._get_json(url)

    # ── Live trades ──────────────────────────────────────────────────────────

    def get_live_trades(self, inscode: str) -> list[dict]:
        """
        Fetch all trades executed so far in the current session.

        Unlike GetTradeHistory (which requires a date), this endpoint
        always returns today's trades. Key in response: "trade".

        Note: insCode and dEven are null/0 — the caller must inject them.
        """
        url = Endpoints.LIVE_TRADES.format(inscode=inscode)
        data = self._get_json(url)
        if "trade" not in data:
            raise OrboAPIError(
                f"Expected key 'trade' missing. Got: {list(data.keys())}"
            )
        return data["trade"]

    # ── Live order book ──────────────────────────────────────────────────────

    def get_live_orderbook(self, inscode: str) -> list[dict]:
        """
        Fetch the current 5-level order book as a full snapshot.

        Unlike the historical BestLimitsHistory endpoint (which is an
        incremental update stream), this always returns all 5 levels
        as the current complete state. Key in response: "bestLimits".
        """
        url = Endpoints.LIVE_ORDERBOOK.format(inscode=inscode)
        data = self._get_json(url)
        if "bestLimits" not in data:
            raise OrboAPIError(
                f"Expected key 'bestLimits' missing. Got: {list(data.keys())}"
            )
        return data["bestLimits"]

    # ── Live client type ─────────────────────────────────────────────────────

    def get_live_client_type(self, inscode: str) -> dict:
        """
        Fetch the real (حقیقی) vs legal (حقوقی) buy/sell breakdown
        for the current session so far.

        Note: This endpoint has a slightly different field structure
        from GetClientTypeHistory — it uses CountI/CountN naming and
        omits per-side Value fields.
        """
        url = Endpoints.LIVE_CLIENT_TYPE.format(inscode=inscode)
        data = self._get_json(url)
        if "clientType" not in data:
            raise OrboAPIError(
                f"Expected key 'clientType' missing. Got: {list(data.keys())}"
            )
        return data["clientType"]

    # ── Instrument info ──────────────────────────────────────────────────────

    def get_instrument_info(self, inscode: str) -> dict:
        """
        Fetch instrument metadata: EPS, sector, min/max week/year,
        current price limit (static threshold), average volume, etc.

        This data changes infrequently — typically once per trading day.
        """
        url = Endpoints.INSTRUMENT_INFO.format(inscode=inscode)
        data = self._get_json(url)
        if "instrumentInfo" not in data:
            raise OrboAPIError(
                f"Expected key 'instrumentInfo' missing. Got: {list(data.keys())}"
            )
        return data["instrumentInfo"]

    # ── Exchange messages ─────────────────────────────────────────────────────

    def get_messages(self, inscode: str) -> list[dict]:
        """
        Fetch exchange announcements and supervisor messages for an instrument.

        Covers events such as trading halts, re-openings, capital actions,
        and regulatory notices.
        """
        url = Endpoints.INSTRUMENT_MESSAGES.format(inscode=inscode)
        data = self._get_json(url)
        return data.get("msg", [])

    # ── Server time ──────────────────────────────────────────────────────────

    def get_server_time(self) -> str:
        """
        Fetch the TSETMC server's current date/time.

        Returns a plain text string in the format "MM/DD/YYYY HH:MM:SS"
        (Gregorian calendar, Tehran time).
        """
        return self._get_text(Endpoints.SERVER_TIME)

    # ── Market overview ──────────────────────────────────────────────────────

    def get_market_overview(self, market_id: int = 1) -> dict:
        """
        Fetch market-wide summary statistics.

        Parameters
        ----------
        market_id : 1 = TSE (بورس), 2 = OTC (فرابورس)
        """
        url = Endpoints.MARKET_OVERVIEW.format(market_id=market_id)
        data = self._get_json(url)
        return data.get("marketOverview", {})

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "TSETMCLiveClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
