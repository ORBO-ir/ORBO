"""Tests for orbo.engines.intra_stats.IntraStatsEngine."""
import math
import pandas as pd
import pytest
from orbo.engines.intra_stats import IntraStatsEngine, IntraStatsResult


def _make_trades(prices: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    if volumes is None:
        volumes = [1000] * len(prices)
    return pd.DataFrame({
        "trade_no": range(1, len(prices) + 1),
        "price":    [float(p) for p in prices],
        "volume":   volumes,
        "side":     ["buy"] * len(prices),
        "canceled": [0] * len(prices),
    })


class TestIntraStatsEngineValidation:

    def test_missing_price_column_raises(self):
        df = pd.DataFrame({"volume": [100]})
        with pytest.raises(ValueError, match="price"):
            IntraStatsEngine().compute(df)

    def test_single_trade_raises(self):
        df = _make_trades([100.0], [500])
        with pytest.raises(ValueError, match="2 trades"):
            IntraStatsEngine().compute(df)


class TestVWAP:

    def test_equal_volumes_vwap_is_price_mean(self):
        df     = _make_trades([100.0, 200.0], [1000, 1000])
        result = IntraStatsEngine().compute(df)
        assert result.vwap == pytest.approx(150.0)

    def test_volume_weighted_vwap(self):
        # price=100 × vol=3000, price=200 × vol=1000 → vwap = 125
        df     = _make_trades([100.0, 200.0], [3000, 1000])
        result = IntraStatsEngine().compute(df)
        assert result.vwap == pytest.approx(125.0)


class TestSessionReturn:

    def test_positive_session_return(self):
        df     = _make_trades([100.0, 110.0, 120.0])
        result = IntraStatsEngine().compute(df)
        assert result.session_return == pytest.approx(0.20)

    def test_negative_session_return(self):
        df     = _make_trades([120.0, 110.0, 100.0])
        result = IntraStatsEngine().compute(df)
        assert result.session_return == pytest.approx(-1/6, rel=1e-3)

    def test_flat_session_return_is_zero(self):
        df     = _make_trades([100.0, 100.0, 100.0])
        result = IntraStatsEngine().compute(df)
        assert result.session_return == pytest.approx(0.0)


class TestPriceRange:

    def test_price_range_correct(self):
        df     = _make_trades([95.0, 100.0, 110.0, 90.0, 105.0])
        result = IntraStatsEngine().compute(df)
        assert result.price_range == pytest.approx(20.0)


class TestTickCount:

    def test_tick_count_equals_trade_count(self):
        prices = [100.0, 101.0, 102.0, 103.0]
        df     = _make_trades(prices)
        result = IntraStatsEngine().compute(df)
        assert result.tick_count == 4


class TestTickReturns:

    def test_first_tick_return_is_nan(self):
        df     = _make_trades([100.0, 110.0, 120.0])
        result = IntraStatsEngine().compute(df)
        assert math.isnan(result.tick_returns.iloc[0])

    def test_tick_return_values(self):
        df     = _make_trades([100.0, 110.0])
        result = IntraStatsEngine().compute(df)
        assert result.tick_returns.iloc[1] == pytest.approx(0.10)


class TestDistribution:

    def test_has_required_fields(self):
        df     = _make_trades([100, 102, 101, 103, 100, 104, 99, 105])
        result = IntraStatsEngine().compute(df)
        for field in ["skewness","kurtosis_excess","tail_type","is_fat_tail"]:
            assert field in result.distribution.index

    def test_tail_type_is_valid(self):
        df     = _make_trades([100, 102, 101, 103, 100, 104])
        result = IntraStatsEngine().compute(df)
        assert result.distribution["tail_type"] in {"fat_tail","thin_tail","normal_tail"}


class TestApplyInterface:

    def test_apply_adds_tick_return_column(self):
        df     = _make_trades([100.0, 105.0, 102.0])
        result = IntraStatsEngine().apply(df)
        assert "tick_return"    in result.columns
        assert "vwap_deviation" in result.columns

    def test_apply_preserves_original_columns(self):
        df     = _make_trades([100.0, 105.0, 102.0])
        result = IntraStatsEngine().apply(df)
        for col in df.columns:
            assert col in result.columns


class TestSummary:

    def test_summary_has_key_fields(self):
        df      = _make_trades([100, 102, 101, 103])
        result  = IntraStatsEngine().compute(df)
        summary = result.summary()
        for key in ["vwap","session_return","price_range","tick_count","total_volume"]:
            assert key in summary.index
