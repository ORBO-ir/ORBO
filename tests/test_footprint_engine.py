"""Tests for orbo.engines.footprint.FootprintEngine."""

import pandas as pd
import pytest

from orbo.engines.footprint import FootprintEngine, FootprintResult


CLASSIFIED_COLUMNS = [
    "trade_no",
    "time",
    "price",
    "volume",
    "side",
    "canceled",
]


def _make_classified(rows: list[dict]) -> pd.DataFrame:
    """
    Build classified trades DataFrame.

    Even when rows is empty, preserve the expected schema so that the
    DataFrame matches the output contract of TradeSideEngine.classify().
    """
    return pd.DataFrame(rows, columns=CLASSIFIED_COLUMNS)


SIMPLE_TRADES = [
    {"trade_no": 1, "time": "09:01:00", "price": 100.0, "volume": 1000, "side": "buy",     "canceled": 0},
    {"trade_no": 2, "time": "09:02:00", "price": 100.0, "volume": 500,  "side": "sell",    "canceled": 0},
    {"trade_no": 3, "time": "09:03:00", "price": 101.0, "volume": 2000, "side": "buy",     "canceled": 0},
    {"trade_no": 4, "time": "09:04:00", "price": 101.0, "volume": 200,  "side": "sell",    "canceled": 0},
    {"trade_no": 5, "time": "09:05:00", "price": 102.0, "volume": 300,  "side": "sell",    "canceled": 0},
    {"trade_no": 6, "time": "09:06:00", "price": 102.0, "volume": 100,  "side": "unknown", "canceled": 0},
]


class TestFootprintEngineBasic:

    def test_returns_footprint_result(self):
        df = _make_classified(SIMPLE_TRADES)
        result = FootprintEngine().build(df)
        assert isinstance(result, FootprintResult)

    def test_bars_has_expected_columns(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        for col in [
            "price",
            "buy_volume",
            "sell_volume",
            "unknown_volume",
            "total_volume",
            "delta",
            "buy_pct",
            "is_poc",
            "imbalance",
        ]:
            assert col in bars.columns

    def test_bars_sorted_descending_by_price(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        prices = bars["price"].tolist()
        assert prices == sorted(prices, reverse=True)

    def test_buy_sell_volumes_correct(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        row = bars[bars["price"] == 100.0].iloc[0]

        assert row["buy_volume"] == 1000
        assert row["sell_volume"] == 500

    def test_delta_is_buy_minus_sell(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        row = bars[bars["price"] == 100.0].iloc[0]

        assert row["delta"] == row["buy_volume"] - row["sell_volume"]

    def test_unknown_volume_captured(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        row = bars[bars["price"] == 102.0].iloc[0]

        assert row["unknown_volume"] == 100

    def test_total_volume_is_sum_of_all(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        for _, row in bars.iterrows():
            assert (
                row["total_volume"]
                == row["buy_volume"]
                + row["sell_volume"]
                + row["unknown_volume"]
            )

    def test_exactly_one_poc(self):
        df = _make_classified(SIMPLE_TRADES)
        bars = FootprintEngine().build(df).bars

        assert bars["is_poc"].sum() == 1

    def test_poc_is_highest_volume_price(self):
        df = _make_classified(SIMPLE_TRADES)
        result = FootprintEngine().build(df)

        bars = result.bars
        max_vol_price = float(bars.loc[bars["total_volume"].idxmax(), "price"])

        assert result.poc_price == max_vol_price


class TestFootprintSessionTotals:

    def test_total_buy_correct(self):
        result = FootprintEngine().build(_make_classified(SIMPLE_TRADES))
        assert result.total_buy == 3000

    def test_total_sell_correct(self):
        result = FootprintEngine().build(_make_classified(SIMPLE_TRADES))
        assert result.total_sell == 1000

    def test_total_delta_correct(self):
        result = FootprintEngine().build(_make_classified(SIMPLE_TRADES))
        assert result.total_delta == result.total_buy - result.total_sell

    def test_buy_pct_between_0_and_100(self):
        result = FootprintEngine().build(_make_classified(SIMPLE_TRADES))
        assert 0 <= result.buy_pct <= 100

    def test_classified_pct_between_0_and_100(self):
        result = FootprintEngine().build(_make_classified(SIMPLE_TRADES))
        assert 0 <= result.classified_pct <= 100

    def test_summary_has_expected_keys(self):
        summary = FootprintEngine().build(_make_classified(SIMPLE_TRADES)).summary()

        for key in [
            "poc_price",
            "total_buy",
            "total_sell",
            "total_delta",
            "buy_pct",
        ]:
            assert key in summary.index


class TestFootprintImbalance:

    def test_demand_imbalance_when_buy_dominates(self):
        trades = [
            {"trade_no": 1, "price": 100.0, "volume": 9000, "side": "buy", "canceled": 0},
            {"trade_no": 2, "price": 100.0, "volume": 1000, "side": "sell", "canceled": 0},
        ]

        bars = FootprintEngine(3.0).build(_make_classified(trades)).bars

        assert bars.iloc[0]["imbalance"] == "demand"

    def test_supply_imbalance_when_sell_dominates(self):
        trades = [
            {"trade_no": 1, "price": 100.0, "volume": 1000, "side": "buy", "canceled": 0},
            {"trade_no": 2, "price": 100.0, "volume": 9000, "side": "sell", "canceled": 0},
        ]

        bars = FootprintEngine(3.0).build(_make_classified(trades)).bars

        assert bars.iloc[0]["imbalance"] == "supply"

    def test_balanced_when_volumes_similar(self):
        trades = [
            {"trade_no": 1, "price": 100.0, "volume": 1000, "side": "buy", "canceled": 0},
            {"trade_no": 2, "price": 100.0, "volume": 1000, "side": "sell", "canceled": 0},
        ]

        bars = FootprintEngine(3.0).build(_make_classified(trades)).bars

        assert bars.iloc[0]["imbalance"] == "balanced"

    def test_insufficient_when_volume_too_small(self):
        trades = [
            {"trade_no": 1, "price": 100.0, "volume": 3, "side": "buy", "canceled": 0},
            {"trade_no": 2, "price": 100.0, "volume": 1, "side": "sell", "canceled": 0},
        ]

        bars = FootprintEngine(3.0).build(_make_classified(trades)).bars

        assert bars.iloc[0]["imbalance"] == "insufficient"


class TestFootprintEdgeCases:

    def test_empty_df_returns_empty_result(self):
        df = _make_classified([])

        result = FootprintEngine().build(df)

        assert result.bars.empty
        assert result.total_buy == 0
        assert result.total_sell == 0
        assert result.total_delta == 0

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"price": [100.0], "volume": [1000]})

        with pytest.raises(ValueError, match="Missing columns"):
            FootprintEngine().build(df)

    def test_price_step_rounds_prices(self):
        trades = [
            {"trade_no": 1, "price": 100.2, "volume": 500, "side": "buy", "canceled": 0},
            {"trade_no": 2, "price": 100.7, "volume": 500, "side": "sell", "canceled": 0},
        ]

        bars = FootprintEngine().build(
            _make_classified(trades),
            price_step=1.0,
        ).bars

        assert len(bars) <= 2

    def test_apply_returns_bars_dataframe(self):
        bars = FootprintEngine().apply(_make_classified(SIMPLE_TRADES))

        assert isinstance(bars, pd.DataFrame)
        assert "buy_volume" in bars.columns
