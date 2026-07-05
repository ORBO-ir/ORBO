"""
DailyStatsEngine — return series and distributional statistics
for daily OHLCV data produced by InstrumentHistory.fetch().

Computes
--------
- Simple returns, log returns, cumulative returns
- Period returns: weekly (5-trading-day), monthly, yearly
- Descriptive statistics: mean, median, mode, variance, std, min, max, range
- Distribution analysis: skewness, kurtosis, tail classification
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from orbo.engines.base import BaseEngine


@dataclass
class DailyStatsResult:
    """
    All computed statistics for a daily close price series.

    Attributes
    ----------
    daily_simple : pd.Series
        Day-over-day simple returns: (P_t − P_{t-1}) / P_{t-1}.
        First element is NaN (no prior price).

    daily_log : pd.Series
        Day-over-day log returns: ln(P_t / P_{t-1}).
        First element is NaN.

    cumulative : pd.Series
        Compounded total return since the first day:
        (1 + r_1)(1 + r_2)... − 1.

    weekly : pd.DataFrame
        Columns: period_start, period_end, return, return_pct.
        Grouped into consecutive 5-trading-day windows.

    monthly : pd.DataFrame
        Columns: period (Jalali YYYY-MM), return, return_pct.
        Compounded daily returns within each Jalali calendar month.

    yearly : pd.DataFrame
        Columns: period (Jalali YYYY), return, return_pct.
        Compounded daily returns within each Jalali calendar year.

    descriptive : pd.Series
        Computed on daily_simple returns:
        count, mean, median, mode, variance, std, minimum, maximum, range.

    distribution : pd.Series
        skewness, kurtosis_excess, tail_type, pct_beyond_2sigma,
        pct_beyond_3sigma, is_fat_tail.
    """
    daily_simple: pd.Series
    daily_log:    pd.Series
    cumulative:   pd.Series
    weekly:       pd.DataFrame
    monthly:      pd.DataFrame
    yearly:       pd.DataFrame
    descriptive:  pd.Series
    distribution: pd.Series

    @property
    def nav_index(self) -> pd.Series:
        """
        NAV-style index starting at 100 on the first day.

        nav[t] = 100 × (1 + cumulative_return[t])

        Useful for comparing multiple instruments on the same scale,
        regardless of their absolute price level.
        """
        return 100.0 * (1.0 + self.cumulative)
    
    def summary(self) -> pd.Series:
        """All descriptive + distribution stats combined in one Series."""
        return pd.concat([self.descriptive, self.distribution])


class DailyStatsEngine(BaseEngine):
    """
    Compute return series and distributional statistics from a daily
    OHLCV DataFrame produced by InstrumentHistory.fetch().

    Examples
    --------
    Via Instrument (recommended)::

        stock = orbo.Instrument("شپنا")
        res   = stock.stats(adjust=True)

        res.descriptive                 # mean, std, min, max, …
        res.distribution                # skewness, kurtosis, tail type
        res.cumulative.iloc[-1]         # total return from first day
        res.monthly[["period","return_pct"]]   # monthly return table

    Direct usage::

        h   = InstrumentHistory("7745894403636165")
        df  = h.fetch(adjust=True)
        res = DailyStatsEngine().compute(df)
    """

    def apply(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        BaseEngine interface — enriches the input DataFrame with
        return_simple, return_log, and return_cum columns.
        """
        result = self.compute(data)
        df = data.copy()
        df["return_simple"] = result.daily_simple.values
        df["return_log"]    = result.daily_log.values
        df["return_cum"]    = result.cumulative.values
        return df

    def compute(self, df: pd.DataFrame) -> DailyStatsResult:
        """
        Compute all statistics.

        Parameters
        ----------
        df : pd.DataFrame
            Output of InstrumentHistory.fetch(). Must contain columns
            "date" (Jalali YYYY-MM-DD string) and "close" (float).

        Returns
        -------
        DailyStatsResult

        Raises
        ------
        ValueError
            If df is empty or missing the "close" column.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")
        if "close" not in df.columns:
            raise ValueError(
                "Input DataFrame must have a 'close' column. "
                "Make sure raw=False (the default) in history()."
            )

        # Ensure ascending date order and float dtype
        work = df.sort_values("date").reset_index(drop=True)
        close = work["close"].astype(float)

        # ── Return series ────────────────────────────────────────────────
        simple     = close.pct_change()
        log_ret    = np.log(close / close.shift(1))
        cumulative = (1 + simple).cumprod() - 1

        # ── Period returns ───────────────────────────────────────────────
        work["_simple"] = simple.values
        work["_year"]   = work["date"].str[:4]
        work["_month"]  = work["date"].str[:7]   # Jalali YYYY-MM

        weekly  = self._weekly_returns(work["close"].values, work["date"].values)
        monthly = self._period_returns(work, "_month", "month")
        yearly  = self._period_returns(work, "_year",  "year")

        # ── Descriptive + distribution stats ─────────────────────────────
        descriptive  = self._descriptive(simple)
        distribution = self._distribution(simple)

        return DailyStatsResult(
            daily_simple = simple,
            daily_log    = log_ret,
            cumulative   = cumulative,
            weekly       = weekly,
            monthly      = monthly,
            yearly       = yearly,
            descriptive  = descriptive,
            distribution = distribution,
        )

    # ── Private helpers ─────────────────────────────────────────────────────

    def _weekly_returns(
        self,
        closes: "np.ndarray",
        dates:  "np.ndarray",
    ) -> pd.DataFrame:
        """
        Group closes into consecutive 5-trading-day windows.

        TSETMC trades Sun–Thu, so a "week" is not always 5 calendar days.
        We use consecutive 5-trade windows as the standard approximation.
        """
        rows = []
        n = len(closes)
        for start in range(0, n, 5):
            end = min(start + 5, n)
            window = closes[start:end]
            if len(window) < 2:
                continue
            ret = float(window[-1] / window[0]) - 1.0
            rows.append({
                "period_start": dates[start],
                "period_end":   dates[end - 1],
                "return":       round(ret, 6),
                "return_pct":   round(ret * 100, 4),
            })
        return pd.DataFrame(rows)

    def _period_returns(
        self,
        df:        pd.DataFrame,
        group_col: str,
        label:     str,
    ) -> pd.DataFrame:
        """
        Compound daily simple returns within each period group.

        A period's return = ∏(1 + daily_return) − 1.
        """
        result = (
            df.groupby(group_col)["_simple"]
            .apply(lambda x: float((1.0 + x).prod()) - 1.0)
            .reset_index()
        )
        result.columns = ["period", "return"]
        result["return_pct"] = (result["return"] * 100).round(4)
        return result

    def _descriptive(self, series: pd.Series) -> pd.Series:
        """
        Standard descriptive statistics on daily simple returns.

        Note on mode: for continuous return series, the statistical mode
        is computed on values rounded to 4 decimal places — the most
        frequently occurring return bucket in the sample.
        """
        s = series.dropna()

        mode_vals = (s.round(4)).mode()
        mode_val  = float(mode_vals.iloc[0]) if len(mode_vals) > 0 else float("nan")

        return pd.Series({
            "count":    int(len(s)),
            "mean":     float(s.mean()),
            "median":   float(s.median()),
            "mode":     mode_val,
            "variance": float(s.var(ddof=1)),
            "std":      float(s.std(ddof=1)),
            "minimum":  float(s.min()),
            "maximum":  float(s.max()),
            "range":    float(s.max() - s.min()),
        }, name="descriptive_stats")

    def _distribution(self, series: pd.Series) -> pd.Series:
        """
        Characterize the shape and tail behavior of the return distribution.

        Tail classification
        -------------------
        kurtosis_excess > 1.0  → leptokurtic (fat tails)
        kurtosis_excess < -1.0 → platykurtic (thin tails)
        otherwise              → mesokurtic (near-normal tails)

        Fat-tail test: compare observed frequency beyond ±2σ and ±3σ
        to theoretical normal values (4.55% and 0.27% respectively).
        """
        s    = series.dropna()
        skew = float(s.skew())
        kurt = float(s.kurt())   # excess kurtosis, normal = 0

        std  = float(s.std())
        mean = float(s.mean())

        pct_2sigma = float(((s < mean - 2 * std) | (s > mean + 2 * std)).mean())
        pct_3sigma = float(((s < mean - 3 * std) | (s > mean + 3 * std)).mean())

        is_fat = (pct_2sigma > 0.0455) or (pct_3sigma > 0.0027)

        if kurt > 1.0:
            tail_type = "fat_tail"
        elif kurt < -1.0:
            tail_type = "thin_tail"
        else:
            tail_type = "normal_tail"

        if skew > 0.5:
            skew_direction = "right_skewed"
        elif skew < -0.5:
            skew_direction = "left_skewed"
        else:
            skew_direction = "symmetric"

        return pd.Series({
            "skewness":          skew,
            "skew_direction":    skew_direction,
            "kurtosis_excess":   kurt,
            "tail_type":         tail_type,
            "pct_beyond_2sigma": round(pct_2sigma * 100, 2),
            "pct_beyond_3sigma": round(pct_3sigma * 100, 2),
            "is_fat_tail":       is_fat,
        }, name="distribution_stats")
