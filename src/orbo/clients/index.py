"""
HTTP client for TSETMC market index endpoints.

Covers the selected-indices snapshot, historical daily values,
intraday tick-by-tick values, and constituent company lists.
"""
from __future__ import annotations

import logging

import httpx

from orbo.constants import Endpoints, DEFAULT_TIMEOUT, DEFAULT_HEADERS, LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError
from orbo.clients.retry import with_retry

logger = logging.getLogger(LOGGER_NAME)

# market_id values
MARKET_ALL = 0   # TSE + OTC combined
MARKET_TSE = 1   # بورس اوراق بهادار
MARKET_OTC = 2   # فرابورس ایران


class TSETMCIndexClient:
    """
    HTTP client for TSETMC market index data.

    Examples
    --------
        with TSETMCIndexClient() as client:
            # All active indices
            records = client.get_snapshot()

            # Historical daily values for a specific index
            df = client.get_history("32097828799138957")

            # Today's intraday values
            df = client.get_today("32097828799138957")

            # Companies in an index
            df = client.get_companies("32097828799138957")
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
            status = exc.response.status_code
            if status == 404:
                raise OrboNotFoundError(url) from exc
            raise OrboAPIError(f"HTTP error {status}.") from exc
        except httpx.RequestError as exc:
            raise OrboConnectionError("Request failed.") from exc
        except ValueError as exc:
            raise OrboAPIError(f"Malformed JSON: {exc}") from exc

    def get_snapshot(self, market_id: int = MARKET_ALL) -> list[dict]:
        """
        Fetch the current snapshot of all selected market indices.

        Parameters
        ----------
        market_id : int
            0 = all (default), 1 = TSE (بورس), 2 = OTC (فرابورس)

        Returns
        -------
        list[dict]
            One record per index. Each record contains the current value,
            high, low, absolute change, percentage change, and name.
        """
        url  = Endpoints.INDEX_SNAPSHOT.format(market_id=market_id)
        data = self._get_json(url)
        return data.get("indexB1", [])

    def get_history(self, ins_code: str) -> list[dict]:
        """
        Fetch the complete historical daily values for one index.

        Data starts from the index's inception date.

        Parameters
        ----------
        ins_code : str
            Index instrument code (use get_snapshot() or find_index() to discover).

        Returns
        -------
        list[dict]
            One record per trading day. Fields: dEven (Gregorian date),
            xNivInuClMresIbs (closing value), xNivInuPbMresIbs (low),
            xNivInuPhMresIbs (high).
        """
        url  = Endpoints.INDEX_HISTORY.format(ins_code=ins_code)
        data = self._get_json(url)
        return data.get("indexB2", [])

    def get_today(self, ins_code: str) -> list[dict]:
        """
        Fetch the intraday time series of an index for the current trading day.

        Records are published every 1500 seconds (25 minutes) during the session.
        Each record shows the index value and running high/low at that moment.

        Parameters
        ----------
        ins_code : str
            Index instrument code.

        Returns
        -------
        list[dict]
            Time series for today. Sorted ascending by hEven.
        """
        url  = Endpoints.INDEX_TODAY.format(ins_code=ins_code)
        data = self._get_json(url)
        return data.get("indexB1", [])

    def get_companies(self, ins_code: str) -> list[dict]:
        """
        Fetch the constituent companies of a market index with live prices.

        Parameters
        ----------
        ins_code : str
            Index instrument code.

        Returns
        -------
        list[dict]
            One record per constituent company. Each record contains the
            nested instrument identity plus live price fields.
        """
        url  = Endpoints.INDEX_COMPANIES.format(ins_code=ins_code)
        data = self._get_json(url)
        return data.get("indexCompany", [])

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TSETMCIndexClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
