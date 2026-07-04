"""
Tests for orbo.data.transformers.

All tests are pure unit tests — no network calls, no file I/O.
"""
import pytest
import pandas as pd
from orbo.data.transformers import (
    _int_to_jalali,
    _int_to_time,
    closing_price_to_dataframe,
    today_price_to_dataframe,
    instrument_state_to_dataframe,
)


# ── Sample fixtures ─────────────────────────────────────────────────────────

ONE_DAY = {
    "dEven":          20260628,
    "hEven":          122959,
    "priceFirst":     10220,
    "priceMax":       10220,
    "priceMin":       9930,
    "pClosing":       10190,
    "pDrCotVal":      10210,
    "priceYesterday": 9930,
    "priceChange":    280,
    "zTotTran":       52293,
    "qTotTran5J":     3_379_786_204,
    "qTotCap":        34_437_417_248_060,
}

TWO_DAYS = [
    {**ONE_DAY, "dEven": 20260628, "hEven": 122959},
    {**ONE_DAY, "dEven": 20260623, "hEven": 122938,
     "pClosing": 9650, "pDrCotVal": 9650, "priceYesterday": 9370,
     "priceMax": 9650, "priceMin": 9650, "priceFirst": 9650},
]

TODAY_PAYLOAD = {
    "closingPriceInfo": {
        "dEven":          20260629,
        "hEven":          122948,
        "priceFirst":     10470,
        "priceMax":       10490,
        "priceMin":       10300,
        "pClosing":       10480,
        "pDrCotVal":      10490,
        "priceYesterday": 10190,
        "priceChange":    0,        # 0 during live session
        "zTotTran":       21086,
        "qTotTran5J":     1_335_987_211,
        "qTotCap":        14_001_471_796_770,
        "instrumentState": None,    # nested object — should be ignored
        "instrument":      None,
    }
}

STATE_PAYLOAD = {
    "instrumentState": [
        {"dEven": 20260519, "hEven": 101112, "cEtaval": "A ", "cEtavalTitle": "مجاز"},
        {"dEven": 20260519, "hEven": 100904, "cEtaval": "I ", "cEtavalTitle": "ممنوع"},
        {"dEven": 20260228, "hEven": 123641, "cEtaval": "IS", "cEtavalTitle": "ممنوع-متوقف"},
    ]
}


# ── _int_to_jalali ──────────────────────────────────────────────────────────

class TestIntToJalali:

    def test_known_date(self):
        assert _int_to_jalali(20260628) == "1405-04-07"

    def test_returns_string(self):
        assert isinstance(_int_to_jalali(20260101), str)

    def test_format_is_yyyy_mm_dd(self):
        result = _int_to_jalali(20260628)
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2


# ── _int_to_time ────────────────────────────────────────────────────────────

class TestIntToTime:

    def test_known_time(self):
        assert _int_to_time(122959) == "12:29:59"

    def test_midnight(self):
        assert _int_to_time(0) == "00:00:00"

    def test_single_digit_hour(self):
        assert _int_to_time(90530) == "09:05:30"

    def test_format_hh_mm_ss(self):
        result = _int_to_time(122959)
        parts = result.split(":")
        assert len(parts) == 3
        assert all(len(p) == 2 for p in parts)


# ── closing_price_to_dataframe ──────────────────────────────────────────────

class TestClosingPriceToDataframe:

    def test_returns_dataframe(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_has_core_columns(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        for col in ["date", "time", "open", "high", "low", "close", "volume"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_jalali_date(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["date"] == "1405-04-07"

    def test_time_conversion(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["time"] == "12:29:59"

    def test_close_change_calculated(self):
        # close=10190, prev_close=9930 → close_change=260
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["close_change"] == 260

    def test_close_pct_calculated(self):
        # 260 / 9930 * 100 ≈ 2.62%
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["close_pct"] == pytest.approx(2.62, abs=0.01)

    def test_last_change_calculated(self):
        # last_price=10210, prev_close=9930 → last_change=280
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["last_change"] == 280

    def test_last_pct_calculated(self):
        # 280 / 9930 * 100 ≈ 2.82%
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]})
        assert df.iloc[0]["last_pct"] == pytest.approx(2.82, abs=0.01)

    def test_sorted_ascending(self):
        df = closing_price_to_dataframe({"closingPriceDaily": TWO_DAYS})
        assert df.iloc[0]["date"] < df.iloc[1]["date"]

    def test_empty_payload_returns_empty_df(self):
        df = closing_price_to_dataframe({"closingPriceDaily": []})
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_raw_keeps_original_columns(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]}, raw=True)
        assert "dEven"    in df.columns
        assert "pClosing" in df.columns
        assert "date"     not in df.columns

    def test_raw_does_not_compute_derived_columns(self):
        df = closing_price_to_dataframe({"closingPriceDaily": [ONE_DAY]}, raw=True)
        assert "close_change" not in df.columns
        assert "close_pct"    not in df.columns


# ── today_price_to_dataframe ────────────────────────────────────────────────

class TestTodayPriceToDataframe:

    def test_returns_single_row(self):
        df = today_price_to_dataframe(TODAY_PAYLOAD)
        assert len(df) == 1

    def test_has_same_schema_as_daily(self):
        df = today_price_to_dataframe(TODAY_PAYLOAD)
        for col in ["date", "time", "open", "high", "low", "close"]:
            assert col in df.columns

    def test_computes_change_even_when_api_returns_zero(self):
        # API sends priceChange=0 during live sessions, but we calculate
        # last_change = last_price - prev_close = 10490 - 10190 = 300
        df = today_price_to_dataframe(TODAY_PAYLOAD)
        assert df.iloc[0]["last_change"] == 300

    def test_empty_payload_returns_empty_df(self):
        df = today_price_to_dataframe({})
        assert df.empty


# ── instrument_state_to_dataframe ───────────────────────────────────────────

class TestInstrumentStateToDataframe:

    def test_returns_dataframe(self):
        df = instrument_state_to_dataframe(STATE_PAYLOAD)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_has_expected_columns(self):
        df = instrument_state_to_dataframe(STATE_PAYLOAD)
        for col in ["date", "time", "state_code", "state"]:
            assert col in df.columns

    def test_sorted_ascending(self):
        df = instrument_state_to_dataframe(STATE_PAYLOAD)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_empty_payload(self):
        df = instrument_state_to_dataframe({"instrumentState": []})
        assert df.empty
