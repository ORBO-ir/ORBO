"""
HTTP client for TSETMC option chain endpoints.

The option market watch returns a full snapshot of all listed
option contracts (call + put pairs) for every tradable underlying.
"""
from __future__ import annotations

import logging

import httpx

from orbo.constants import Endpoints, DEFAULT_TIMEOUT, DEFAULT_HEADERS, LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError
from orbo.clients.retry import with_retry

logger = logging.getLogger(LOGGER_NAME)

# Market IDs
MARKET_ALL  = 0   # بورس + فرابورس
MARKET_TSE  = 1   # بورس
MARKET_OTC  = 2   # فرابورس


class TSETMCOptionClient:
    """
    HTTP client for TSETMC option chain data.

    The endpoint returns a complete snapshot of all active option
    contracts. The site refreshes this every ~3 seconds during trading.
    A full re-fetch on every refresh is correct and efficient because
    option chains are small (typically 15–40 strike rows per underlying).

    Examples
    --------
        with TSETMCOptionClient() as client:
            records = client.get_chain()           # all markets
            records = client.get_chain(market_id=1) # TSE only
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
            raise OrboConnectionError("TSETMC is unreachable.") from exc
        except httpx.HTTPStatusError as exc:
            raise OrboAPIError(f"HTTP error {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise OrboConnectionError("Request failed.") from exc
        except ValueError as exc:
            raise OrboAPIError(f"Malformed JSON: {exc}") from exc

    def get_chain(self, market_id: int = MARKET_ALL) -> list[dict]:
        """
        Fetch the full option market watch snapshot.

        Parameters
        ----------
        market_id : int
            0 = all markets (default), 1 = TSE (بورس), 2 = OTC (فرابورس)

        Returns
        -------
        list[dict]
            One record per call/put pair (one strike of one underlying).
            Each record contains fields for both the call (_C suffix) and
            the put (_P suffix) alongside shared fields (strike, dte, etc.).
        """
        url  = Endpoints.OPTION_CHAIN.format(market_id=market_id)
        data = self._get_json(url)
        records = data.get("instrumentOptMarketWatch", [])
        if not records and "instrumentOptMarketWatch" not in data:
            raise OrboAPIError(
                f"Expected key 'instrumentOptMarketWatch'. Got: {list(data.keys())}"
            )
        return records

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TSETMCOptionClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
