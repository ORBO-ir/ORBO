"""
HTTP client for TSETMC intraday (tick-level, single-day) endpoints.

Covers trades, the order-book update tape, the intraday price tape,
major shareholders, and the real/legal client-type breakdown.
"""
from __future__ import annotations

import logging

import httpx

from orbo.constants import Endpoints, DEFAULT_TIMEOUT, DEFAULT_HEADERS, LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError
from orbo.clients.retry import with_retry

logger = logging.getLogger(LOGGER_NAME)


class TSETMCIntradayClient:
    """
    Thin HTTP wrapper for TSETMC intraday endpoints.

    All methods return raw parsed JSON. Transformation to DataFrames
    happens in orbo.data.transformers.
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

        Intraday endpoints fail intermittently more often than daily
        endpoints under repeated batch requests — retries automatically
        on connection issues, server errors, and malformed JSON.
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
            raise OrboAPIError(f"Malformed JSON from {url}: {exc}") from exc

    def _require_key(self, payload: dict, key: str, url: str):
        """Validate the expected top-level key exists; raise OrboAPIError if not."""
        if key not in payload:
            raise OrboAPIError(
                f"Expected key '{key}' missing in response from {url}. "
                f"Got keys: {list(payload.keys())}"
            )
        return payload[key]

    # ── Trades ───────────────────────────────────────────────────────────────

    def get_trades(
        self,
        inscode: str,
        date: str,
        combine_same_price: bool = False,
    ) -> list[dict]:
        """
        Fetch tick-by-tick trade history for one trading day.

        Parameters
        ----------
        inscode : 18-digit TSETMC instrument code.
        date : Gregorian date as YYYYMMDD string.
        combine_same_price : trailing boolean in the TSETMC URL. Observed
            behavior: False (default) returns more granular, unmerged
            prints — preferred for tick-level work such as footprint or
            aggressor-side analysis. Exact official semantics are
            undocumented; verify empirically if it matters for your use case.

        Returns
        -------
        list[dict]
            Raw trade records. NOT guaranteed to be chronologically ordered —
            trade_history_to_dataframe() sorts by nTran explicitly.
        """
        flag = "true" if combine_same_price else "false"
        url = Endpoints.TRADES.format(inscode=inscode, date=date, combine_same_price=flag)
        payload = self._get_json(url)
        return self._require_key(payload, "tradeHistory", url)

    # ── Order book ───────────────────────────────────────────────────────────

    def get_orderbook(self, inscode: str, date: str) -> list[dict]:
        """
        Fetch the incremental order-book (best-limits) update stream.

        Note
        ----
        This is an incremental UPDATE stream, not a sequence of full
        5-level snapshots — most rows touch a single depth level only.
        Full point-in-time book reconstruction is left to a future engine.
        """
        url = Endpoints.ORDERBOOK.format(inscode=inscode, date=date)
        payload = self._get_json(url)
        return self._require_key(payload, "bestLimitsHistory", url)

    # ── Price tape ───────────────────────────────────────────────────────────

    def get_price_tape(self, inscode: str, date: str) -> list[dict]:
        """
        Fetch the intraday tape of TSETMC's continuously-recalculated
        official closing price alongside the last-trade price.
        """
        url = Endpoints.PRICE_TAPE.format(inscode=inscode, date=date)
        payload = self._get_json(url)
        return self._require_key(payload, "closingPriceHistory", url)

    # ── Shareholders ─────────────────────────────────────────────────────────

    def get_shareholders(self, inscode: str, date: str) -> list[dict]:
        """Fetch the major-shareholders list as of a given date."""
        url = Endpoints.SHAREHOLDERS.format(inscode=inscode, date=date)
        payload = self._get_json(url)
        return self._require_key(payload, "shareShareholder", url)

    # ── Client type (real / legal buy-sell flow) ────────────────────────────

    def get_client_type(self, inscode: str, date: str) -> dict:
        """
        Fetch the real (حقیقی) vs legal (حقوقی) buy/sell breakdown for one day.

        Note
        ----
        TSETMC only retains this for the most recent trading day, despite
        the "History" suffix in the endpoint name.
        """
        url = Endpoints.CLIENT_TYPE.format(inscode=inscode, date=date)
        payload = self._get_json(url)
        return self._require_key(payload, "clientType", url)

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "TSETMCIntradayClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
