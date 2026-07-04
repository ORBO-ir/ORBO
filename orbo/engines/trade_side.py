"""
TradeSideEngine — classify each trade tick as aggressive buy or sell.

Two classification methods are used in priority order:

Quote Rule (primary, requires order-book data):
    The aggressor is the side that crossed the spread:
        trade.price >= best_ask  →  aggressive buyer  (lifted the ask)
        trade.price <= best_bid  →  aggressive seller (hit the bid)

Tick Rule (fallback, trades-only):
    Direction inferred from price movement vs previous trade:
        price > prev_price  →  uptick  →  aggressive buyer
        price < prev_price  →  downtick →  aggressive seller
        price == prev_price →  carry forward the previous side

When both methods are used together, quote-rule classifications seed the
tick-carry logic so that a confirmed direction propagates correctly through
flat-price runs between classified trades.

References
----------
Lee, C. M. C., & Ready, M. J. (1991). Inferring trade direction from
    intraday data. Journal of Finance, 46(2), 733–746.
    DOI: 10.1111/j.1540-6261.1991.tb02683.x
"""
from __future__ import annotations

import pandas as pd

from orbo.engines.base import BaseEngine

# Side labels
_BUY     = "buy"
_SELL    = "sell"
_UNKNOWN = "unknown"

# Method labels
_QUOTE        = "quote"
_TICK         = "tick"
_TICK_CARRY   = "tick_carry"
_METH_UNKNOWN = "unknown"


def _time_str_to_int(time_str: str) -> int:
    """
    Convert a HH:MM:SS string to a HHMMSS integer for numeric ordering.

    Example
    -------
    >>> _time_str_to_int("09:01:30")
    90130
    """
    return int(time_str.replace(":", ""))


def _tick_rule(prices: list[float]) -> tuple[list[str], list[str]]:
    """
    Apply the Tick Rule to a chronological sequence of trade prices.

    Parameters
    ----------
    prices : list[float]
        Trade prices in ascending trade_no order.

    Returns
    -------
    (sides, methods) : parallel lists of length len(prices).
        The first element is always ("unknown", "unknown") because
        no prior price exists to compare against.
    """
    n = len(prices)
    sides   = [_UNKNOWN]    * n
    methods = [_METH_UNKNOWN] * n
    last_side = _UNKNOWN

    for i in range(1, n):
        curr = prices[i]
        prev = prices[i - 1]

        if curr > prev:
            sides[i]   = _BUY
            methods[i] = _TICK
            last_side  = _BUY

        elif curr < prev:
            sides[i]   = _SELL
            methods[i] = _TICK
            last_side  = _SELL

        else:
            # Same price — carry forward the last known direction
            if last_side != _UNKNOWN:
                sides[i]   = last_side
                methods[i] = _TICK_CARRY
            # else stays "unknown"

    return sides, methods


class TradeSideEngine(BaseEngine):
    """
    Classify intraday trade ticks as aggressive buy or aggressive sell.

    Examples
    --------
    Tick Rule only (no order book available)::

        engine = TradeSideEngine()
        classified = engine.classify(session.trades)

    Quote Rule + Tick Rule (recommended)::

        engine = TradeSideEngine()
        classified = engine.classify(session.trades, session.orderbook)

    The returned DataFrame is the trades DataFrame with two new columns:

    ``side``   — "buy" | "sell" | "unknown"
    ``method`` — "quote" | "tick" | "tick_carry" | "unknown"
    """

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        BaseEngine interface — classify trades without order-book data.

        For Quote Rule + Tick Rule classification, call classify() directly
        and pass the order-book DataFrame.
        """
        return self.classify(data, orderbook=None)

    def classify(
        self,
        trades:   pd.DataFrame,
        orderbook: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Classify each trade row as aggressive buy or aggressive sell.

        Parameters
        ----------
        trades : pd.DataFrame
            Output of trade_history_to_dataframe(). Required columns:
            trade_no, time, price.
        orderbook : pd.DataFrame | None
            Output of orderbook_to_dataframe(). When supplied, the Quote
            Rule is used as the primary classifier and Tick Rule is the
            fallback. When None, only the Tick Rule is applied.

        Returns
        -------
        pd.DataFrame
            Input trades with two additional columns:

            side   : "buy" | "sell" | "unknown"
            method : "quote" | "tick" | "tick_carry" | "unknown"

            Sorted ascending by trade_no.
        """
        if trades.empty:
            return trades.assign(
                side=pd.Series(dtype=str),
                method=pd.Series(dtype=str),
            )

        df = trades.sort_values("trade_no").reset_index(drop=True).copy()

        if orderbook is not None and not orderbook.empty:
            return self._classify_with_book(df, orderbook)

        return self._classify_tick_only(df)

    # ── Tick Rule only ──────────────────────────────────────────────────────

    def _classify_tick_only(self, df: pd.DataFrame) -> pd.DataFrame:
        sides, methods = _tick_rule(df["price"].tolist())
        df["side"]   = sides
        df["method"] = methods
        return df

    # ── Quote Rule + Tick Rule fallback ─────────────────────────────────────

    def _classify_with_book(
        self,
        df:        pd.DataFrame,
        orderbook: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Step 1: Match each trade to the most recent Level-1 (best bid/ask)
                order-book update at or before the trade's timestamp.
        Step 2: Apply Quote Rule to classify what it can.
        Step 3: Fill remaining ambiguous trades using the Tick Rule,
                seeded by Quote Rule results so that confirmed directions
                propagate correctly through flat-price runs.
        """

        # ── Step 1: order-book state lookup ──────────────────────────────
        ob1 = orderbook[orderbook["level"] == 1][
            ["time", "bid_price", "ask_price"]
        ].copy()

        if ob1.empty:
            return self._classify_tick_only(df)

        ob1["_t"] = ob1["time"].apply(_time_str_to_int)
        ob1 = ob1.sort_values("_t").reset_index(drop=True)

        df["_t"] = df["time"].apply(_time_str_to_int)

        # merge_asof: for each trade, pick the most recent ob event ≤ trade time
        merged = pd.merge_asof(
            df.sort_values("_t"),
            ob1[["_t", "bid_price", "ask_price"]].rename(
                columns={"bid_price": "_bid", "ask_price": "_ask"}
            ),
            on="_t",
            direction="backward",
        )
        merged = merged.sort_values("trade_no").reset_index(drop=True)

        # ── Step 2: Quote Rule ────────────────────────────────────────────
        price  = merged["price"]
        ob_bid = merged["_bid"].fillna(0)
        ob_ask = merged["_ask"].fillna(0)

        buy_q  = (ob_ask > 0) & (price >= ob_ask)
        sell_q = (ob_bid > 0) & (price <= ob_bid)

        merged["side"]   = _UNKNOWN
        merged["method"] = _METH_UNKNOWN
        merged.loc[buy_q,  "side"]   = _BUY
        merged.loc[buy_q,  "method"] = _QUOTE
        merged.loc[sell_q, "side"]   = _SELL
        merged.loc[sell_q, "method"] = _QUOTE

        # ── Step 3: Tick Rule for ambiguous trades ────────────────────────
        ambig   = ~(buy_q | sell_q)
        prices  = merged["price"].tolist()
        sides   = merged["side"].tolist()
        methods = merged["method"].tolist()
        is_ambig = ambig.tolist()

        last_side = _UNKNOWN

        for i in range(len(prices)):
            if not is_ambig[i]:
                # Quote Rule classified this row — update carry reference
                last_side = sides[i]
                continue

            if i == 0:
                continue  # first trade, no prior price — stays unknown

            curr = prices[i]
            prev = prices[i - 1]

            if curr > prev:
                sides[i]  = _BUY
                methods[i] = _TICK
                last_side  = _BUY

            elif curr < prev:
                sides[i]  = _SELL
                methods[i] = _TICK
                last_side  = _SELL

            else:
                # Same price: carry forward last confirmed direction
                if last_side != _UNKNOWN:
                    sides[i]  = last_side
                    methods[i] = _TICK_CARRY
                # else stays "unknown"

        merged["side"]   = sides
        merged["method"] = methods

        return merged.drop(columns=["_t", "_bid", "_ask"])
