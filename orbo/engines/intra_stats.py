"""
IntraStatsEngine — compute statistics on intraday tick/trade data.

Works on the output of trade_history_to_dataframe() or
TradeSideEngine.classify().

For daily statistics, use DailyStatsEngine instead.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from orbo.engines.base import BaseEngine


@dataclass
class IntraStatsResult:
    """
    Intraday statistics for one trading session.

    Attributes
    ----------
    vwap : float
        Volume Weighted Average Price — the fairest representation of
        the day's price, used for execution benchmarking.
        VWAP = Σ(price × volume) / Σ(volume)

    session_return : float
        Simple return from first trade to last trade:
        (last_price − first_price) / first_price.

    price_range : float
        Intraday range: max_price − min_price.

    tick_count : int
        Total number of executed trades.

    total_volume : int
        Total shares/units traded.

    price_stats : pd.Series
        Descriptive statistics on trade prices:
        mean, median, std, min, max, range.

    volume_stats : pd.Series
        Descriptive statistics on per-trade volume:
        mean, median, std, min, max, total.

    tick_returns : pd.Series
        Trade-by-trade simple returns:
        (price[i] − price[i-1]) / price[i-1].
        First element is NaN.

    distribution : pd.Series
        Distribution shape of tick returns:
        skewness, kurtosis_excess, tail_type, is_fat_tail.
    """
    vwap:           float
    session_return: float
    price_range:    float
    tick_count:     int
    total_volume:   int
    price_stats:    pd.Series
    volume_stats:   pd.Series
    tick_returns:   pd.Series
    distribution:   pd.Series

    def summary(self) -> pd.Series:
        """Key session metrics as a single Series."""
        return pd.Series({
            "vwap":           round(self.vwap, 2),
            "session_return": round(self.session_return * 100, 4),
            "price_range":    self.price_range,
            "tick_count":     self.tick_count,
            "total_volume":   self.total_volume,
        })


class IntraStatsEngine(BaseEngine):
    """
    Compute statistics on intraday trade-tick data.

    Works on any trade DataFrame that has 'price' and 'volume' columns.
    Compatible with:
    - trade_history_to_dataframe() output
    - TradeSideEngine.classify() output
    - LiveSnapshot.trades

    Examples
    --------
    Historical session::

        session = orbo.Instrument("شپنا").intraday("20260628")
        result  = IntraStatsEngine().compute(session.trades)

        result.vwap            # Volume Weighted Average Price
        result.session_return  # first-to-last price return
        result.distribution    # skewness, kurtosis, tail type
        result.summary()       # key metrics in one Series

    Live session::

        snap   = orbo.Instrument("شپنا").live()
        result = IntraStatsEngine().compute(snap.trades)

    With classified trades::

        classified = TradeSideEngine().classify(session.trades)
        result     = IntraStatsEngine().compute(classified)
    """

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        BaseEngine interface — returns input DataFrame enriched with
        tick_return and vwap_deviation columns.
        """
        result = self.compute(data)
        df = data.copy()
        df["tick_return"]    = result.tick_returns.values
        df["vwap_deviation"] = (df["price"] - result.vwap) / result.vwap * 100
        return df

    def compute(self, trades: pd.DataFrame) -> IntraStatsResult:
        """
        Compute all intraday statistics.

        Parameters
        ----------
        trades : pd.DataFrame
            Must contain columns "price" (float) and "volume" (int/float).
            If a "trade_no" column exists, the DataFrame is sorted by it
            to ensure chronological order.

        Returns
        -------
        IntraStatsResult

        Raises
        ------
        ValueError
            If required columns are missing or fewer than 2 trades exist.
        """
        missing = {"price", "volume"} - set(trades.columns)
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}. "
                "Input must have 'price' and 'volume' columns."
            )
        if len(trades) < 2:
            raise ValueError("At least 2 trades are required to compute statistics.")

        # Ensure chronological order
        df = trades.copy()
        if "trade_no" in df.columns:
            df = df.sort_values("trade_no").reset_index(drop=True)

        price  = df["price"].astype(float)
        volume = df["volume"].astype(float)

        # ── Core metrics ──────────────────────────────────────────────────
        vwap = float((price * volume).sum() / volume.sum())

        session_return = float((price.iloc[-1] - price.iloc[0]) / price.iloc[0])
        price_range    = float(price.max() - price.min())
        tick_count     = len(df)
        total_volume   = int(volume.sum())

        # ── Descriptive stats ─────────────────────────────────────────────
        price_stats = pd.Series({
            "mean":   float(price.mean()),
            "median": float(price.median()),
            "std":    float(price.std(ddof=1)),
            "min":    float(price.min()),
            "max":    float(price.max()),
            "range":  float(price.max() - price.min()),
        }, name="price_stats")

        volume_stats = pd.Series({
            "mean":   float(volume.mean()),
            "median": float(volume.median()),
            "std":    float(volume.std(ddof=1)),
            "min":    float(volume.min()),
            "max":    float(volume.max()),
            "total":  float(volume.sum()),
        }, name="volume_stats")

        # ── Tick returns ──────────────────────────────────────────────────
        tick_returns = price.pct_change()

        # ── Distribution ──────────────────────────────────────────────────
        distribution = self._distribution(tick_returns)

        return IntraStatsResult(
            vwap           = vwap,
            session_return = session_return,
            price_range    = price_range,
            tick_count     = tick_count,
            total_volume   = total_volume,
            price_stats    = price_stats,
            volume_stats   = volume_stats,
            tick_returns   = tick_returns,
            distribution   = distribution,
        )

    def _distribution(self, tick_returns: pd.Series) -> pd.Series:
        s    = tick_returns.dropna()
        skew = float(s.skew())
        kurt = float(s.kurt())

        std  = float(s.std())
        mean = float(s.mean())
        pct_2sigma = float(((s < mean - 2*std) | (s > mean + 2*std)).mean())
        pct_3sigma = float(((s < mean - 3*std) | (s > mean + 3*std)).mean())

        if kurt > 1.0:
            tail_type = "fat_tail"
        elif kurt < -1.0:
            tail_type = "thin_tail"
        else:
            tail_type = "normal_tail"

        if skew > 0.5:
            skew_dir = "right_skewed"
        elif skew < -0.5:
            skew_dir = "left_skewed"
        else:
            skew_dir = "symmetric"

        return pd.Series({
            "skewness":          skew,
            "skew_direction":    skew_dir,
            "kurtosis_excess":   kurt,
            "tail_type":         tail_type,
            "pct_beyond_2sigma": round(pct_2sigma * 100, 2),
            "pct_beyond_3sigma": round(pct_3sigma * 100, 2),
            "is_fat_tail":       (pct_2sigma > 0.0455) or (pct_3sigma > 0.0027),
        }, name="distribution_stats")
