"""Tests for orbo.engines.daily_stats.DailyStatsEngine."""
import math
import numpy as np
import pandas as pd
import pytest
from orbo.engines.daily_stats import DailyStatsEngine, DailyStatsResult


def _make_df(closes: list[float], start_jalali: str = "1400-01-01") -> pd.DataFrame:
    """Build a minimal daily DataFrame with Jalali dates."""
    rows = []
    year, month, day = map(int, start_jalali.split("-"))
    for i, close in enumerate(closes):
        day_num = day + i
        rows.append({
            "date": f"{year}-{month:02d}-{day_num:02d}",
            "open": close,
            "high": close,
            "low":  close,
            "close": float(close),
            "prev_close": float(closes[i-1]) if i > 0 else close,
            "volume": 1_000_000,
        })
    return pd.DataFrame(rows)


class TestDailyStatsEngineValidation:

    def test_empty_df_raises(self):
        with pytest.raises(ValueError, match="empty"):
            DailyStatsEngine().compute(pd.DataFrame())

    def test_missing_close_column_raises(self):
        df = pd.DataFrame({"date": ["1400-01-01"], "price": [100.0]})
        with pytest.raises(ValueError, match="close"):
            DailyStatsEngine().compute(df)


class TestReturnSeries:

    def test_first_simple_return_is_nan(self):
        df = _make_df([100, 110, 121])
        res = DailyStatsEngine().compute(df)
        assert math.isnan(res.daily_simple.iloc[0])

    def test_simple_return_correct(self):
        df = _make_df([100, 110])
        res = DailyStatsEngine().compute(df)
        assert res.daily_simple.iloc[1] == pytest.approx(0.10)

    def test_log_return_correct(self):
        df = _make_df([100, 110])
        res = DailyStatsEngine().compute(df)
        expected = math.log(110 / 100)
        assert res.daily_log.iloc[1] == pytest.approx(expected)

    def test_cumulative_return_at_end(self):
        # 10% then 10% = 21% total
        df = _make_df([100, 110, 121])
        res = DailyStatsEngine().compute(df)
        assert res.cumulative.iloc[-1] == pytest.approx(0.21)

    def test_cumulative_starts_near_zero(self):
        df = _make_df([100, 105, 110])
        res = DailyStatsEngine().compute(df)
        assert math.isnan(res.cumulative.iloc[0]) or abs(res.cumulative.iloc[0]) < 1.0

    def test_negative_return(self):
        df = _make_df([100, 90])
        res = DailyStatsEngine().compute(df)
        assert res.daily_simple.iloc[1] == pytest.approx(-0.10)


class TestPeriodReturns:

    def test_monthly_has_period_column(self):
        closes = [100 + i for i in range(30)]
        df = _make_df(closes)
        res = DailyStatsEngine().compute(df)
        assert "period" in res.monthly.columns
        assert "return_pct" in res.monthly.columns

    def test_yearly_has_period_column(self):
        closes = [100 + i for i in range(20)]
        df = _make_df(closes)
        res = DailyStatsEngine().compute(df)
        assert "period" in res.yearly.columns

    def test_weekly_has_period_start_and_end(self):
        closes = [100 + i for i in range(15)]
        df = _make_df(closes)
        res = DailyStatsEngine().compute(df)
        assert "period_start" in res.weekly.columns
        assert "period_end"   in res.weekly.columns

    def test_weekly_groups_5_trading_days(self):
        closes = list(range(100, 111))  # 11 days
        df = _make_df(closes)
        res = DailyStatsEngine().compute(df)
        # [0:5]=5 days ✓, [5:10]=5 days ✓, [10:11]=1 day → skipped (needs ≥2)
        assert len(res.weekly) == 2

class TestDescriptiveStats:

    def test_has_required_fields(self):
        df = _make_df([100, 110, 105, 115, 108])
        res = DailyStatsEngine().compute(df)
        for field in ["count","mean","median","mode","variance","std","minimum","maximum","range"]:
            assert field in res.descriptive.index

    def test_count_excludes_nan(self):
        df = _make_df([100, 110, 121])
        res = DailyStatsEngine().compute(df)
        # 3 closes → 2 returns (first is NaN)
        assert res.descriptive["count"] == 2

    def test_mean_correct(self):
        # returns: NaN, 0.10, 0.10
        df = _make_df([100, 110, 121])
        res = DailyStatsEngine().compute(df)
        assert res.descriptive["mean"] == pytest.approx(0.10, rel=1e-3)

    def test_range_is_max_minus_min(self):
        df = _make_df([100, 110, 90, 120, 80])
        res = DailyStatsEngine().compute(df)
        assert res.descriptive["range"] == pytest.approx(
            res.descriptive["maximum"] - res.descriptive["minimum"]
        )

    def test_std_positive(self):
        df = _make_df([100, 110, 95, 105, 108])
        res = DailyStatsEngine().compute(df)
        assert res.descriptive["std"] > 0


class TestDistributionStats:

    def test_has_required_fields(self):
        df = _make_df([100, 110, 105, 115, 108])
        res = DailyStatsEngine().compute(df)
        for field in ["skewness","kurtosis_excess","tail_type",
                      "pct_beyond_2sigma","pct_beyond_3sigma","is_fat_tail"]:
            assert field in res.distribution.index

    def test_symmetric_data_has_low_skew(self):
        # Symmetric returns around 0
        closes = [100]
        for _ in range(50):
            closes.append(closes[-1] * 1.01)
            closes.append(closes[-1] * 0.99)  # approx symmetric
        df = _make_df(closes[:50])
        res = DailyStatsEngine().compute(df)
        assert abs(res.distribution["skewness"]) < 2.0

    def test_tail_type_values_are_valid(self):
        df = _make_df([100, 110, 105, 115, 108, 112, 95, 120, 88, 125])
        res = DailyStatsEngine().compute(df)
        assert res.distribution["tail_type"] in {"fat_tail", "thin_tail", "normal_tail"}

    def test_pct_beyond_2sigma_between_0_and_100(self):
        df = _make_df([100, 110, 105, 115, 108, 112, 95, 120])
        res = DailyStatsEngine().compute(df)
        pct = res.distribution["pct_beyond_2sigma"]
        assert 0.0 <= pct <= 100.0

    def test_is_fat_tail_is_bool(self):
        df = _make_df([100, 110, 105, 115, 108])
        res = DailyStatsEngine().compute(df)
        assert isinstance(res.distribution["is_fat_tail"], (bool, np.bool_))


class TestApplyInterface:

    def test_apply_adds_return_columns(self):
        df = _make_df([100, 110, 105, 115])
        result_df = DailyStatsEngine().apply(df)
        assert "return_simple" in result_df.columns
        assert "return_log"    in result_df.columns
        assert "return_cum"    in result_df.columns

    def test_apply_preserves_original_columns(self):
        df = _make_df([100, 110, 115])
        result_df = DailyStatsEngine().apply(df)
        for col in df.columns:
            assert col in result_df.columns

    def test_summary_combines_descriptive_and_distribution(self):
        df = _make_df([100, 110, 105, 115, 108])
        res = DailyStatsEngine().compute(df)
        summary = res.summary()
        assert "mean" in summary.index
        assert "skewness" in summary.index
