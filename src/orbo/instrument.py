"""High-level Instrument API — single entry point for all data."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from orbo.constants import LOGGER_NAME
from orbo.exceptions import OrboNotFoundError
from orbo.registry import registry
from orbo.search.instrument_search import search
from orbo.history.history import InstrumentHistory
from orbo.intraday.session import IntradaySession
from orbo.engines.daily_stats import DailyStatsEngine

logger = logging.getLogger(LOGGER_NAME)


@dataclass
class LiveSnapshot:
    """Point-in-time snapshot of all live market data for one instrument."""
    _price_raw:       dict
    _trades_raw:      list[dict]
    _orderbook_raw:   list[dict]
    _client_type_raw: dict
    _inscode:         str

    @property
    def price(self) -> pd.DataFrame:
        from orbo.data.transformers import today_price_to_dataframe
        return today_price_to_dataframe(self._price_raw)

    @property
    def trades(self) -> pd.DataFrame:
        import datetime
        from orbo.data.transformers import trade_history_to_dataframe
        today_int = int(datetime.date.today().strftime("%Y%m%d"))
        return trade_history_to_dataframe(self._trades_raw, date=str(today_int))

    @property
    def orderbook(self) -> pd.DataFrame:
        from orbo.data.transformers import live_orderbook_to_dataframe
        return live_orderbook_to_dataframe(self._orderbook_raw)

    @property
    def client_type(self) -> pd.DataFrame:
        from orbo.data.transformers import live_client_type_to_dataframe
        return live_client_type_to_dataframe(self._client_type_raw)

    def __repr__(self) -> str:
        info = self.price
        if info.empty:
            return f"LiveSnapshot(inscode={self._inscode!r})"
        row = info.iloc[0]
        return (
            f"LiveSnapshot(inscode={self._inscode!r}, "
            f"close={row.get('close')}, "
            f"last={row.get('last_price')}, "
            f"time={row.get('time')})"
        )


class Instrument:
    """
    High-level access to all data for a single TSETMC instrument.

    Examples
    --------
        stock = orbo.Instrument("شپنا")
        df    = stock.history(adjust=True)
        stats = stock.stats()
        snap  = stock.live()
    """

    def _resolve(self, key: str | int) -> None:
        """Resolve symbol / name / inscode to a canonical inscode."""
        key_str = str(key).strip()

        # Already an inscode (long numeric string)
        if key_str.isdigit() and len(key_str) >= 12:
            self._inscode = key_str
            return

        # Try local registry (fast, no network)
        try:
            rec = registry.lookup(key_str)
            if rec is not None:
                self._inscode = str(rec.ins_code)
                self._symbol  = rec.symbol
                self._name    = rec.name
                return
        except FileNotFoundError:
            logger.debug("Registry file not found — falling back to search API")
        except Exception as exc:
            # RegistryNotInitializedError or any other registry failure
            # → silently fall back to search so Instrument() still works
            logger.debug("Registry lookup failed (%s) — falling back to search", exc)

        # Fall back to TSETMC search API
        results = search(key_str)
        if not results:
            raise OrboNotFoundError(
                f"Instrument '{key_str}' not found via search.\n"
                "Tip: run orbo.bootstrap() to build the local registry for faster lookups."
            )
        best          = results[0]
        self._inscode = best.ins_code
        self._symbol  = best.symbol
        self._name    = best.name


    @property
    def inscode(self) -> str:
        return self._inscode

    @property
    def symbol(self) -> str | None:
        return self._symbol

    @property
    def name(self) -> str | None:
        return self._name

    def history(self, count: int = 0, adjust: bool = False, raw: bool = False) -> pd.DataFrame:
        """Fetch historical daily OHLCV data."""
        return InstrumentHistory(self._inscode).fetch(count=count, adjust=adjust, raw=raw)

    def today(self) -> pd.DataFrame:
        """Fetch live price data for the current trading session."""
        return InstrumentHistory(self._inscode).today()

    def state(self) -> pd.DataFrame:
        """Fetch the full trading-status change log."""
        return InstrumentHistory(self._inscode).state()

    def intraday(self, date: str) -> IntradaySession:
        """Return an IntradaySession for a specific trading day (YYYYMMDD)."""
        return IntradaySession(self._inscode, date)

    def stats(self, count: int = 0, adjust: bool = False) -> "DailyStatsResult":
        """Compute return series and distributional statistics."""
        df = self.history(count=count, adjust=adjust)
        return DailyStatsEngine().compute(df)

    def live(self) -> LiveSnapshot:
        """Fetch a live snapshot: price, trades, orderbook, client type."""
        from orbo.clients.live import TSETMCLiveClient
        with TSETMCLiveClient() as client:
            return LiveSnapshot(
                _price_raw       = client.get_live_price(self._inscode),
                _trades_raw      = client.get_live_trades(self._inscode),
                _orderbook_raw   = client.get_live_orderbook(self._inscode),
                _client_type_raw = client.get_live_client_type(self._inscode),
                _inscode         = self._inscode,
            )

    def __repr__(self) -> str:
        return (
            f"Instrument("
            f"inscode={self._inscode!r}, "
            f"symbol={self._symbol!r}, "
            f"name={self._name!r})"
        )
