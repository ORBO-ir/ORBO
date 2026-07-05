"""
IntradaySession — everything ORBO can fetch for one instrument on one
trading day, bundled behind lazy properties with built-in retry.
"""
from __future__ import annotations

import logging
import time

import pandas as pd

from orbo.clients.intraday import TSETMCIntradayClient
from orbo.constants import LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError
from orbo.data.transformers import (
    trade_history_to_dataframe,
    orderbook_to_dataframe,
    price_tape_to_dataframe,
    shareholders_to_dataframe,
    client_type_to_dataframe,
)

logger = logging.getLogger(LOGGER_NAME)


class IntradaySession:
    """
    All intraday data for a single (instrument, date) pair.

    Each data source is fetched lazily — only on first access — and
    cached on the instance. A property is never fetched twice.

    Parameters
    ----------
    inscode : str | int
        18-digit TSETMC instrument code.
    date : str
        Gregorian date as YYYYMMDD (e.g. "20260628").

    Examples
    --------
        session = IntradaySession("7745894403636165", "20260628")
        df_trades = session.trades        # fetched here
        df_trades_again = session.trades  # cached, no new request

    Context manager (auto-closes HTTP connection)::

        with IntradaySession(inscode, date) as s:
            df = s.trades
    """

    def __init__(self, inscode: str | int, date: str) -> None:
        self.inscode = str(inscode)
        self.date    = str(date)
        self._client = TSETMCIntradayClient()

        self._trades:       pd.DataFrame | None = None
        self._orderbook:    pd.DataFrame | None = None
        self._price_tape:   pd.DataFrame | None = None
        self._shareholders: pd.DataFrame | None = None
        self._client_type:  pd.DataFrame | None = None

    @property
    def trades(self) -> pd.DataFrame:
        """Tick-by-tick trade history, sorted chronologically."""
        if self._trades is None:
            records = self._client.get_trades(self.inscode, self.date)
            self._trades = trade_history_to_dataframe(records, self.date)
        return self._trades

    @property
    def orderbook(self) -> pd.DataFrame:
        """Order-book (best-limits) incremental update tape."""
        if self._orderbook is None:
            records = self._client.get_orderbook(self.inscode, self.date)
            self._orderbook = orderbook_to_dataframe(records, self.date)
        return self._orderbook

    @property
    def price_tape(self) -> pd.DataFrame:
        """Intraday tape of the official closing price and last trade price."""
        if self._price_tape is None:
            records = self._client.get_price_tape(self.inscode, self.date)
            self._price_tape = price_tape_to_dataframe(records, self.date)
        return self._price_tape

    @property
    def shareholders(self) -> pd.DataFrame:
        """Major shareholders as of this date."""
        if self._shareholders is None:
            records = self._client.get_shareholders(self.inscode, self.date)
            self._shareholders = shareholders_to_dataframe(records)
        return self._shareholders

    @property
    def client_type(self) -> pd.DataFrame:
        """Real (حقیقی) vs legal (حقوقی) buy/sell breakdown for this date."""
        if self._client_type is None:
            record = self._client.get_client_type(self.inscode, self.date)
            self._client_type = client_type_to_dataframe(record, self.date)
        return self._client_type

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "IntradaySession":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"IntradaySession(inscode={self.inscode!r}, date={self.date!r})"


def fetch_intraday_range(
    inscode: str | int,
    dates: list[str],
    fields: list[str] | None = None,
    max_retries: int = 2,
    backoff: float = 2.0,
) -> tuple[dict[str, IntradaySession], list[str]]:
    """
    Fetch IntradaySession objects for multiple dates, retrying only the
    dates that fail — not the whole batch.

    Each underlying HTTP call already retries internally (see
    orbo.clients.retry). This function adds an outer retry pass: if a
    date still fails after the inner retries, it is queued for another
    full attempt in the next round, giving TSETMC a longer cool-down
    before that specific date is tried again.

    Parameters
    ----------
    inscode : instrument code.
    dates : list of Gregorian YYYYMMDD date strings.
    fields : which properties to eagerly fetch and validate per date.
        Default: ["trades"]. Any of "trades", "orderbook", "price_tape",
        "shareholders", "client_type".
    max_retries : number of additional outer retry rounds for failed dates.
    backoff : seconds to wait before each outer retry round, multiplied
        by the round number.

    Returns
    -------
    (sessions, failed_dates)
        sessions : dict mapping each succeeded date to its IntradaySession.
        failed_dates : dates that still failed after all retry rounds.

    Example
    -------
        sessions, failed = fetch_intraday_range(
            "7745894403636165",
            dates=["20260622", "20260623", "20260624"],
            fields=["trades", "orderbook"],
        )
        if failed:
            print("Could not fetch:", failed)
    """
    fields = fields or ["trades"]
    sessions: dict[str, IntradaySession] = {}
    pending = list(dates)

    for round_num in range(max_retries + 1):
        if not pending:
            break

        still_failed: list[str] = []
        for date in pending:
            session = IntradaySession(inscode, date)
            try:
                for field in fields:
                    getattr(session, field)
                sessions[date] = session
            except (OrboConnectionError, OrboAPIError) as exc:
                logger.warning(
                    "date=%s failed on round %d/%d: %s",
                    date, round_num + 1, max_retries + 1, exc,
                )
                session.close()
                still_failed.append(date)

        pending = still_failed
        if pending and round_num < max_retries:
            time.sleep(backoff * (round_num + 1))

    if pending:
        logger.warning("%d date(s) failed after all retries: %s", len(pending), pending)

    return sessions, pending
