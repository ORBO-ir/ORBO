"""
Tests for orbo.history.history.InstrumentHistory.

All tests are pure unit tests — HTTP calls are mocked.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from orbo.history.history import InstrumentHistory
from orbo.exceptions import OrboConnectionError


# ── Fixtures ────────────────────────────────────────────────────────────────

RAW_DAILY = {
    "closingPriceDaily": [
        {
            "dEven": 20260628, "hEven": 122959,
            "priceFirst": 10220, "priceMax": 10220, "priceMin": 9930,
            "pClosing": 10190, "pDrCotVal": 10210, "priceYesterday": 9930,
            "priceChange": 280, "zTotTran": 52293,
            "qTotTran5J": 3_379_786_204, "qTotCap": 34_437_417_248_060,
        }
    ]
}

RAW_TODAY = {
    "closingPriceInfo": {
        "dEven": 20260629, "hEven": 122948,
        "priceFirst": 10470, "priceMax": 10490, "priceMin": 10300,
        "pClosing": 10480, "pDrCotVal": 10490, "priceYesterday": 10190,
        "priceChange": 0, "zTotTran": 21086,
        "qTotTran5J": 1_335_987_211, "qTotCap": 14_001_471_796_770,
        "instrumentState": None, "instrument": None,
    }
}

PRICE_ADJUST = [
    {"dEven": 20230101, "pClosing": 9000.0, "pClosingNotAdjusted": 10000.0}
]

SHARE_CHANGE = [
    {"dEven": 20220101, "numberOfShareOld": 1_000_000.0, "numberOfShareNew": 2_000_000.0}
]

STATE_RECORDS = [
    {"dEven": 20260519, "hEven": 101112, "cEtaval": "A ", "cEtavalTitle": "مجاز"},
]


# ── fetch() ─────────────────────────────────────────────────────────────────

class TestFetch:

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_returns_dataframe(self, MockClient):
        MockClient.return_value.get_daily_history.return_value = RAW_DAILY
        df = InstrumentHistory("123").fetch()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_has_jalali_date_column(self, MockClient):
        MockClient.return_value.get_daily_history.return_value = RAW_DAILY
        df = InstrumentHistory("123").fetch()
        assert "date" in df.columns
        assert df.iloc[0]["date"] == "1405-04-07"

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_raw_true_keeps_original_columns(self, MockClient):
        MockClient.return_value.get_daily_history.return_value = RAW_DAILY
        df = InstrumentHistory("123").fetch(raw=True)
        assert "dEven"    in df.columns
        assert "pClosing" in df.columns

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_empty_response_returns_empty_df(self, MockClient):
        MockClient.return_value.get_daily_history.return_value = {"closingPriceDaily": []}
        df = InstrumentHistory("123").fetch()
        assert df.empty

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_connection_error_propagates(self, MockClient):
        MockClient.return_value.get_daily_history.side_effect = OrboConnectionError("timeout")
        with pytest.raises(OrboConnectionError):
            InstrumentHistory("123").fetch()


# ── fetch(adjust=True) ──────────────────────────────────────────────────────

class TestFetchAdjusted:

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_adjust_true_returns_dataframe(self, MockClient):
        client = MockClient.return_value
        client.get_daily_history.return_value  = RAW_DAILY
        client.get_price_adjusts.return_value  = []
        client.get_share_changes.return_value  = []

        df = InstrumentHistory("123").fetch(adjust=True)
        assert isinstance(df, pd.DataFrame)

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_adjust_applies_price_factor(self, MockClient):
        # factor = 9000/10000 = 0.9
        # price before event (20260628 > 20230101) → no factor → close stays 10190
        # actually 20260628 > 20230101 so no future events → factor = 1.0
        client = MockClient.return_value
        client.get_daily_history.return_value  = RAW_DAILY
        client.get_price_adjusts.return_value  = PRICE_ADJUST  # event on 20230101
        client.get_share_changes.return_value  = []

        df = InstrumentHistory("123").fetch(adjust=True)
        # The data is from 20260628, event is 20230101 — price is AFTER event
        # so factor = 1.0 (no future adjustments)
        assert df.iloc[0]["close"] == pytest.approx(10190.0)

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_adjust_makes_three_api_calls(self, MockClient):
        client = MockClient.return_value
        client.get_daily_history.return_value  = RAW_DAILY
        client.get_price_adjusts.return_value  = []
        client.get_share_changes.return_value  = []

        InstrumentHistory("123").fetch(adjust=True)

        client.get_daily_history.assert_called_once()
        client.get_price_adjusts.assert_called_once()
        client.get_share_changes.assert_called_once()

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_no_adjust_makes_one_api_call(self, MockClient):
        client = MockClient.return_value
        client.get_daily_history.return_value = RAW_DAILY

        InstrumentHistory("123").fetch(adjust=False)

        client.get_daily_history.assert_called_once()
        client.get_price_adjusts.assert_not_called()
        client.get_share_changes.assert_not_called()


# ── today() ─────────────────────────────────────────────────────────────────

class TestToday:

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_returns_single_row_dataframe(self, MockClient):
        MockClient.return_value.get_today.return_value = RAW_TODAY
        df = InstrumentHistory("123").today()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_has_same_columns_as_fetch(self, MockClient):
        client = MockClient.return_value
        client.get_today.return_value         = RAW_TODAY
        client.get_daily_history.return_value = RAW_DAILY
        client.get_price_adjusts.return_value = []
        client.get_share_changes.return_value = []

        df_hist  = InstrumentHistory("123").fetch()
        df_today = InstrumentHistory("123").today()

        assert set(df_today.columns) == set(df_hist.columns)


# ── state() ─────────────────────────────────────────────────────────────────

class TestState:

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_returns_dataframe(self, MockClient):
        MockClient.return_value.get_instrument_state.return_value = STATE_RECORDS
        df = InstrumentHistory("123").state()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_has_state_columns(self, MockClient):
        MockClient.return_value.get_instrument_state.return_value = STATE_RECORDS
        df = InstrumentHistory("123").state()
        for col in ["date", "time", "state_code", "state"]:
            assert col in df.columns


# ── context manager ─────────────────────────────────────────────────────────

class TestContextManager:

    @patch("orbo.history.history.TSETMCHistoryClient")
    def test_close_called_on_exit(self, MockClient):
        client = MockClient.return_value
        client.get_daily_history.return_value = RAW_DAILY

        with InstrumentHistory("123") as h:
            h.fetch()

        client.close.assert_called_once()
