"""
FootprintEngine — aggregate classified intraday trades into
per-price-level footprint bars.

Input:  output of TradeSideEngine.classify() — trades DataFrame
        with columns: price, volume, side.
Output: FootprintResult containing per-price bars with buy/sell volume,
        delta, POC, and imbalance flags.

This is the pure computation layer. Visualization (Plotly charts) is a
separate concern and will live in orbo.charts in the future.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from orbo.engines.base import BaseEngine

_BUY     = "buy"
_SELL    = "sell"
_UNKNOWN = "unknown"


@dataclass
class FootprintResult:
    """
    Order-flow footprint for one trading session or time window.

    Attributes
    ----------
    bars : pd.DataFrame
        One row per unique price level. Columns:

        price          — the price level
        buy_volume     — sum of volume where side == "buy"
        sell_volume    — sum of volume where side == "sell"
        unknown_volume — volume that could not be classified
        total_volume   — buy + sell + unknown
        delta          — buy_volume − sell_volume
        buy_pct        — buy / (buy + sell) × 100  (ignores unknown)
        is_poc         — True for the price with highest total_volume
        imbalance      — "demand" | "supply" | "balanced" | "insufficient"

        Sorted descending by price (highest price at top, matching
        the standard footprint chart orientation).

    poc_price : float
        Point of Control — the price level with the highest total volume.
        Represents where the most activity occurred.

    total_buy : int
        Total classified buy volume across all price levels.

    total_sell : int
        Total classified sell volume across all price levels.

    total_delta : int
        total_buy − total_sell. Positive = net buying pressure for the session.

    buy_pct : float
        Classified buy volume as a percentage of all classified volume (0–100).

    classified_pct : float
        Percentage of total volume that was classified (not "unknown").
        Low values indicate TradeSideEngine had difficulty classifying —
        check if order-book data was supplied.
    """
    bars:           pd.DataFrame
    poc_price:      float
    total_buy:      int
    total_sell:     int
    total_delta:    int
    buy_pct:        float
    classified_pct: float

    def summary(self) -> pd.Series:
        """Key session metrics as a single Series."""
        return pd.Series({
            "poc_price":      self.poc_price,
            "total_buy":      self.total_buy,
            "total_sell":     self.total_sell,
            "total_delta":    self.total_delta,
            "buy_pct":        round(self.buy_pct, 2),
            "classified_pct": round(self.classified_pct, 2),
            "n_levels":       len(self.bars),
        })


class FootprintEngine(BaseEngine):
    """
    Build footprint bars from TradeSideEngine output.

    The footprint chart is an order-flow tool that shows, at each price
    level, how much volume was executed by aggressive buyers vs sellers.
    Large deltas or imbalances at specific prices often mark support,
    resistance, or absorption zones.

    Parameters
    ----------
    imbalance_ratio : float
        Threshold for flagging a price level as imbalanced.
        Default 3.0: flags when one side has ≥ 3× the volume of the other.
        This matches the common convention in Sierra Chart and Bookmap.

    Examples
    --------
    Via IntradaySession + TradeSideEngine::

        session = orbo.Instrument("شپنا").intraday("20260628")

        # Step 1: classify aggressor side
        classified = TradeSideEngine().classify(session.trades, session.orderbook)

        # Step 2: build footprint
        result = FootprintEngine().build(classified)

        result.summary()         # session summary
        result.bars              # per-price detail
        result.poc_price         # Point of Control
        result.total_delta       # net buying/selling pressure

    One-liner::

        result = FootprintEngine().build(
            TradeSideEngine().classify(session.trades, session.orderbook)
        )
    """

    def __init__(self, imbalance_ratio: float = 3.0) -> None:
        self.imbalance_ratio = imbalance_ratio

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        BaseEngine interface — returns the bars DataFrame from build().
        For the full FootprintResult, call build() directly.
        """
        return self.build(data).bars

    def build(
        self,
        classified_trades: pd.DataFrame,
        *,
        price_step: float | None = None,
    ) -> FootprintResult:
        """
        Aggregate classified trades into per-price footprint bars.

        Parameters
        ----------
        classified_trades : pd.DataFrame
            Output of TradeSideEngine.classify(). Required columns:
            price, volume, side.
        price_step : float | None
            Round all prices to the nearest multiple of price_step before
            aggregating. Useful when prices have sub-tick noise. None
            (default) keeps exact prices.

        Returns
        -------
        FootprintResult

        Raises
        ------
        ValueError
            If required columns are missing or the DataFrame is empty.
        """
        required = {"price", "volume", "side"}
        missing  = required - set(classified_trades.columns)
        if missing:
            raise ValueError(
                f"Missing columns: {missing}. "
                "Input must be the output of TradeSideEngine.classify()."
            )
        if classified_trades.empty:
            return self._empty_result()

        df = classified_trades.copy()

        # ── Optional price rounding ───────────────────────────────────────
        if price_step is not None and price_step > 0:
            df["price"] = (df["price"] / price_step).round() * price_step

        # ── Aggregate per price level ─────────────────────────────────────
        buy_vol  = (
            df[df["side"] == _BUY]
            .groupby("price")["volume"].sum()
            .rename("buy_volume")
        )
        sell_vol = (
            df[df["side"] == _SELL]
            .groupby("price")["volume"].sum()
            .rename("sell_volume")
        )
        unk_vol  = (
            df[df["side"] == _UNKNOWN]
            .groupby("price")["volume"].sum()
            .rename("unknown_volume")
        )
        total_vol = (
            df.groupby("price")["volume"].sum()
            .rename("total_volume")
        )

        bars = (
            pd.concat([buy_vol, sell_vol, unk_vol, total_vol], axis=1)
            .fillna(0)
            .astype({"buy_volume": int, "sell_volume": int,
                     "unknown_volume": int, "total_volume": int})
            .reset_index()
        )

        # ── Derived columns ───────────────────────────────────────────────
        bars["delta"] = bars["buy_volume"] - bars["sell_volume"]

        classified_sum = bars["buy_volume"] + bars["sell_volume"]
        bars["buy_pct"] = np.where(
            classified_sum > 0,
            bars["buy_volume"] / classified_sum * 100,
            50.0,
        ).round(2)

        poc_idx         = bars["total_volume"].idxmax()
        poc_price       = float(bars.loc[poc_idx, "price"])
        bars["is_poc"]  = bars.index == poc_idx

        bars["imbalance"] = bars.apply(
            self._classify_imbalance, axis=1
        )

        # Sort descending by price (highest at top = standard chart orientation)
        bars = bars.sort_values("price", ascending=False).reset_index(drop=True)

        # ── Session totals ────────────────────────────────────────────────
        total_buy  = int(bars["buy_volume"].sum())
        total_sell = int(bars["sell_volume"].sum())
        classified  = total_buy + total_sell
        total_all   = int(bars["total_volume"].sum())

        buy_pct        = (total_buy / classified * 100) if classified > 0 else 50.0
        classified_pct = (classified / total_all * 100) if total_all > 0 else 0.0

        return FootprintResult(
            bars           = bars,
            poc_price      = poc_price,
            total_buy      = total_buy,
            total_sell     = total_sell,
            total_delta    = total_buy - total_sell,
            buy_pct        = round(buy_pct, 2),
            classified_pct = round(classified_pct, 2),
        )

    def _classify_imbalance(self, row: pd.Series) -> str:
        """
        Classify the volume imbalance at a single price level.

        Returns
        -------
        "demand"       — buy_vol >= ratio × sell_vol (aggressive buying)
        "supply"       — sell_vol >= ratio × buy_vol (aggressive selling)
        "balanced"     — neither side dominates
        "insufficient" — too little classified volume to judge (< 10 contracts)
        """
        buy  = row["buy_volume"]
        sell = row["sell_volume"]
        tot  = buy + sell

        if tot < 10:
            return "insufficient"
        if sell == 0 and buy > 0:
            return "demand"
        if buy == 0 and sell > 0:
            return "supply"
        if buy >= self.imbalance_ratio * sell:
            return "demand"
        if sell >= self.imbalance_ratio * buy:
            return "supply"
        return "balanced"

    def _empty_result(self) -> FootprintResult:
        cols = ["price","buy_volume","sell_volume","unknown_volume",
                "total_volume","delta","buy_pct","is_poc","imbalance"]
        return FootprintResult(
            bars           = pd.DataFrame(columns=cols),
            poc_price      = float("nan"),
            total_buy      = 0,
            total_sell     = 0,
            total_delta    = 0,
            buy_pct        = 50.0,
            classified_pct = 0.0,
        )
