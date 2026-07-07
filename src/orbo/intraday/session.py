"""
IntradaySession — all tick-level data for one instrument on one trading day.
"""
from __future__ import annotations

import logging
import time

import jdatetime
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


def _to_gregorian(date: str) -> str:
    """
    Normalize any supported date format to Gregorian YYYYMMDD string.

    Accepted formats
    ----------------
    "20260701"    Gregorian YYYYMMDD  → returned as-is
    "1405-04-10"  Jalali YYYY-MM-DD  → converted to Gregorian
    "14050410"    Jalali YYYYMMDD     → converted to Gregorian

    This means the natural workflow works without manual conversion:

        d = stock.history(count=1).iloc[0]["date"]  # "1405-04-10"
        session = stock.intraday(d)                 # just works

    Raises
    ------
    ValueError
        If the format is not recognized or the date is invalid.
    """
    date = str(date).strip().replace("/", "-")

    # ── Gregorian YYYYMMDD: 8 digits, year > 1500 ──────────────────────────
    if date.isdigit() and len(date) == 8 and int(date[:4]) > 1500:
        return date

    # ── Jalali YYYY-MM-DD with dashes ──────────────────────────────────────
    if "-" in date:
        parts = date.split("-")
        if len(parts) != 3:
            raise ValueError(
                f"Unrecognized date: {date!r}. "
                "Use Jalali 'YYYY-MM-DD' (e.g. '1405-04-10') "
                "or Gregorian 'YYYYMMDD' (e.g. '20260701')."
            )
        try:
            jdate = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            return jdate.togregorian().strftime("%Y%m%d")
        except Exception as exc:
            raise ValueError(f"Invalid Jalali date {date!r}: {exc}") from exc

    # ── Jalali YYYYMMDD without dashes: 8 digits, year < 1500 ──────────────
    if date.isdigit() and len(date) == 8 and int(date[:4]) < 1500:
        try:
            jdate = jdatetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
            return jdate.togregorian().strftime("%Y%m%d")
        except Exception as exc:
            raise ValueError(f"Invalid Jalali date {date!r}: {exc}") from exc

    raise ValueError(
        f"Unrecognized date format: {date!r}. "
        "Use Jalali 'YYYY-MM-DD' (e.g. '1405-04-10') "
        "or Gregorian 'YYYYMMDD' (e.g. '20260701')."
    )


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
        Trading date in **either** format:

        - Jalali  ``YYYY-MM-DD`` — e.g. ``"1405-04-10"``
        - Gregorian ``YYYYMMDD`` — e.g. ``"20260701"``

        Both are equivalent. The Jalali format is convenient because it
        matches what ``history()`` returns in its ``date`` column.

    Examples
    --------
    Natural workflow — no manual date conversion needed::

        stock = orbo.Instrument("شپنا")
        d     = stock.history(count=1).iloc[0]["date"]  # "1405-04-10"
        session = stock.intraday(d)                      # just works
        df = session.trades

    Explicit Gregorian date::

        session = orbo.IntradaySession("7745894403636165", "20260701")

    Context manager (auto-closes HTTP connection)::

        with stock.intraday("1405-04-10") as s:
            df = s.trades
    """

    def __init__(self, inscode: str | int, date: str) -> None:
        self.inscode      = str(inscode)
        self.date_jalali  = str(date)                  # original — for display
        self.date         = _to_gregorian(str(date))   # Gregorian YYYYMMDD — for API
        self._client      = TSETMCIntradayClient()

        self._trades:       pd.DataFrame | None = None
        self._orderbook:    pd.DataFrame | None = None
        self._price_tape:   pd.DataFrame | None = None
        self._shareholders: pd.DataFrame | None = None
        self._client_type:  pd.DataFrame | None = None

    @property
    def trades(self) -> pd.DataFrame:
        """Tick-by-tick trade history, sorted chronologically."""
        if self._trades is None:
            records      = self._client.get_trades(self.inscode, self.date)
            self._trades = trade_history_to_dataframe(records, self.date)
        return self._trades

    @property
    def orderbook(self) -> pd.DataFrame:
        """Order-book (best-limits) incremental update tape."""
        if self._orderbook is None:
            records         = self._client.get_orderbook(self.inscode, self.date)
            self._orderbook = orderbook_to_dataframe(records, self.date)
        return self._orderbook

    @property
    def price_tape(self) -> pd.DataFrame:
        """Intraday tape of the official closing price and last trade price."""
        if self._price_tape is None:
            records          = self._client.get_price_tape(self.inscode, self.date)
            self._price_tape = price_tape_to_dataframe(records, self.date)
        return self._price_tape

    @property
    def shareholders(self) -> pd.DataFrame:
        """Major shareholders as of this date."""
        if self._shareholders is None:
            records             = self._client.get_shareholders(self.inscode, self.date)
            self._shareholders  = shareholders_to_dataframe(records)
        return self._shareholders

    @property
    def client_type(self) -> pd.DataFrame:
        """Real (حقیقی) vs legal (حقوقی) buy/sell breakdown for this date."""
        if self._client_type is None:
            record             = self._client.get_client_type(self.inscode, self.date)
            self._client_type  = client_type_to_dataframe(record, self.date)
        return self._client_type

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "IntradaySession":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"IntradaySession("
            f"inscode={self.inscode!r}, "
            f"date={self.date_jalali!r} → {self.date!r})"
        )


def fetch_intraday_range(
    inscode:     str | int,
    dates:       list[str],
    fields:      list[str] | None = None,
    max_retries: int  = 2,
    backoff:     float = 2.0,
) -> tuple[dict[str, IntradaySession], list[str]]:
    """
    Fetch IntradaySession objects for multiple dates with per-date retry.

    Parameters
    ----------
    inscode : str | int
        18-digit TSETMC instrument code.
    dates : list[str]
        Trading dates in **either** Jalali ``YYYY-MM-DD`` or Gregorian
        ``YYYYMMDD`` format. Mixed formats in the same list are fine.
    fields : list[str] | None
        Properties to eagerly fetch per date. Default: ``["trades"]``.
    max_retries : int
        Additional outer retry rounds for failed dates.
    backoff : float
        Seconds between outer retry rounds (multiplied by round number).

    Returns
    -------
    (sessions, failed_dates)
        sessions     : dict mapping each succeeded date to its IntradaySession.
                       Keys use the original date string you passed in.
        failed_dates : dates that still failed after all retry rounds.

    Example
    -------
        sessions, failed = fetch_intraday_range(
            "7745894403636165",
            dates  = ["1405-04-08", "1405-04-09", "1405-04-10"],  # Jalali ok
            fields = ["trades", "orderbook"],
        )
    """
    fields   = fields or ["trades"]
    sessions: dict[str, IntradaySession] = {}
    pending  = list(dates)

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
