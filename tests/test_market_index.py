"""Tests for orbo.index.MarketIndex and index transformers."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from orbo.index.market_index import MarketIndex, index_snapshot, find_index
from orbo.data.transformers import (
    index_snapshot_to_dataframe,
    index_history_to_dataframe,
    index_today_to_dataframe,
    index_companies_to_dataframe,
)
from orbo.exceptions import OrboNotFoundError


# ── Sample fixtures ──────────────────────────────────────────────────────────

SNAPSHOT_RECORDS = [
    {
        "insCode": "32097828799138957",
        "dEven": 0, "hEven": 185917,
        "xDrNivJIdx004": 5187264.87,
        "xPhNivJIdx004": 5187266.57,
        "xPbNivJIdx004": 5127545.25,
        "xVarIdxJRfV": 1.1629,
        "indexChange": 59629.56,
        "lVal30": "شاخص كل",
        "last": False,
    },
    {
        "insCode": "70077233737515808",
        "dEven": 0, "hEven": 185917,
        "xDrNivJIdx004": 77199.45,
        "xPhNivJIdx004": 77199.45,
        "xPbNivJIdx004": 76810.84,
        "xVarIdxJRfV": -1.0298,
        "indexChange": -803.28,
        "lVal30": "53-سيمان",
        "last": False,
    },
]

HISTORY_RECORDS = [
    {"insCode": 70077233737515808, "dEven": 20081205,
     "xNivInuClMresIbs": 183.2, "xNivInuPbMresIbs": 183.2, "xNivInuPhMresIbs": 183.2},
    {"insCode": 70077233737515808, "dEven": 20081206,
     "xNivInuClMresIbs": 182.9, "xNivInuPbMresIbs": 182.9, "xNivInuPhMresIbs": 183.2},
    {"insCode": 70077233737515808, "dEven": 20260701,
     "xNivInuClMresIbs": 77199.4, "xNivInuPbMresIbs": 76810.8, "xNivInuPhMresIbs": 77199.4},
]

TODAY_RECORDS = [
    {"insCode": None, "dEven": 20260701, "hEven": 83000,
     "xDrNivJIdx004": 78002.73, "xPhNivJIdx004": 0.0, "xPbNivJIdx004": 0.0,
     "xVarIdxJRfV": 0.0, "last": False},
    {"insCode": None, "dEven": 20260701, "hEven": 185917,
     "xDrNivJIdx004": 77199.45, "xPhNivJIdx004": 77199.45, "xPbNivJIdx004": 76810.84,
     "xVarIdxJRfV": -1.0298, "last": True},
]

COMPANY_RECORDS = [
    {
        "instrument": {
            "insCode": "35331248532537562",
            "lVal30": "سيمان اردستان",
            "lVal18AFC": "اردستان",
        },
        "pClosing": 30030.0, "pDrCotVal": 30160.0,
        "priceYesterday": 29320.0, "priceChange": 840.0,
        "priceMin": 29350.0, "priceMax": 30190.0,
        "zTotTran": 786.0, "qTotTran5J": 5651925.0, "qTotCap": 169738260590.0,
    },
    {
        "instrument": {
            "insCode": "70883594945615893",
            "lVal30": "سيمان آبيك",
            "lVal18AFC": "سآبيك",
        },
        "pClosing": 59850.0, "pDrCotVal": 59650.0,
        "priceYesterday": 59820.0, "priceChange": -170.0,
        "priceMin": 58200.0, "priceMax": 61000.0,
        "zTotTran": 1060.0, "qTotTran5J": 2162549.0, "qTotCap": 129417790550.0,
    },
]


# ── Transformer: index_snapshot_to_dataframe ─────────────────────────────────

class TestIndexSnapshotTransformer:

    def test_returns_dataframe(self):
        df = index_snapshot_to_dataframe(SNAPSHOT_RECORDS)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_has_required_columns(self):
        df = index_snapshot_to_dataframe(SNAPSHOT_RECORDS)
        for col in ["ins_code", "name", "time", "value", "high", "low",
                    "change", "change_pct"]:
            assert col in df.columns

    def test_time_converted_to_string(self):
        df = index_snapshot_to_dataframe(SNAPSHOT_RECORDS)
        assert df["time"].iloc[0] == "18:59:17"

    def test_change_pct_preserved_as_is(self):
        # xVarIdxJRfV is already in percent — must not be divided by 100
        df  = index_snapshot_to_dataframe(SNAPSHOT_RECORDS)
        row = df[df["name"] == "شاخص كل"].iloc[0]
        assert row["change_pct"] == pytest.approx(1.1629)

    def test_sorted_by_name(self):
        df = index_snapshot_to_dataframe(SNAPSHOT_RECORDS)
        names = df["name"].tolist()
        assert names == sorted(names)

    def test_empty_returns_empty_df(self):
        assert index_snapshot_to_dataframe([]).empty


# ── Transformer: index_history_to_dataframe ──────────────────────────────────

class TestIndexHistoryTransformer:

    def test_returns_dataframe(self):
        df = index_history_to_dataframe(HISTORY_RECORDS)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_has_required_columns(self):
        df = index_history_to_dataframe(HISTORY_RECORDS)
        for col in ["date", "value", "low", "high"]:
            assert col in df.columns

    def test_date_is_jalali_string(self):
        df = index_history_to_dataframe(HISTORY_RECORDS)
        # 20081205 → Jalali
        assert "-" in df["date"].iloc[0]
        parts = df["date"].iloc[0].split("-")
        assert len(parts) == 3

    def test_sorted_ascending_by_date(self):
        df = index_history_to_dataframe(HISTORY_RECORDS)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_closing_value_correct(self):
        df = index_history_to_dataframe(HISTORY_RECORDS)
        # Last record: xNivInuClMresIbs = 77199.4
        assert df.iloc[-1]["value"] == pytest.approx(77199.4)

    def test_empty_returns_empty_df(self):
        assert index_history_to_dataframe([]).empty


# ── Transformer: index_today_to_dataframe ────────────────────────────────────

class TestIndexTodayTransformer:

    def test_returns_dataframe(self):
        df = index_today_to_dataframe(TODAY_RECORDS)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_has_required_columns(self):
        df = index_today_to_dataframe(TODAY_RECORDS)
        for col in ["time", "value", "high", "low", "change_pct"]:
            assert col in df.columns

    def test_sorted_ascending_by_time(self):
        df = index_today_to_dataframe(TODAY_RECORDS)
        times = df["time"].tolist()
        assert times == sorted(times)

    def test_empty_returns_empty_df(self):
        assert index_today_to_dataframe([]).empty


# ── Transformer: index_companies_to_dataframe ────────────────────────────────

class TestIndexCompaniesTransformer:

    def test_returns_dataframe(self):
        df = index_companies_to_dataframe(COMPANY_RECORDS)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_has_required_columns(self):
        df = index_companies_to_dataframe(COMPANY_RECORDS)
        for col in ["ins_code", "symbol", "name", "close", "last_price",
                    "prev_close", "change", "low", "high",
                    "trade_count", "volume", "value"]:
            assert col in df.columns

    def test_extracts_nested_instrument_fields(self):
        df = index_companies_to_dataframe(COMPANY_RECORDS)
        assert "اردستان" in df["symbol"].tolist()
        assert "سيمان اردستان" in df["name"].tolist()

    def test_price_fields_correct(self):
        df  = index_companies_to_dataframe(COMPANY_RECORDS)
        row = df[df["symbol"] == "اردستان"].iloc[0]
        assert row["close"]      == pytest.approx(30030.0)
        assert row["last_price"] == pytest.approx(30160.0)
        assert row["change"]     == pytest.approx(840.0)

    def test_sorted_by_symbol(self):
        df = index_companies_to_dataframe(COMPANY_RECORDS)
        symbols = df["symbol"].tolist()
        assert symbols == sorted(symbols)

    def test_empty_returns_empty_df(self):
        assert index_companies_to_dataframe([]).empty


# ── index_snapshot() function ─────────────────────────────────────────────────

class TestIndexSnapshotFunction:

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_returns_dataframe(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_snapshot.return_value = SNAPSHOT_RECORDS
        MockClient.return_value.__exit__.return_value = False
        df = index_snapshot()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_passes_market_id(self, MockClient):
        mock = MockClient.return_value.__enter__.return_value
        mock.get_snapshot.return_value = SNAPSHOT_RECORDS
        MockClient.return_value.__exit__.return_value = False
        index_snapshot(market_id=1)
        mock.get_snapshot.assert_called_once_with(market_id=1)


# ── find_index() function ─────────────────────────────────────────────────────

class TestFindIndex:

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_finds_by_name_substring(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_snapshot.return_value = SNAPSHOT_RECORDS
        MockClient.return_value.__exit__.return_value = False
        idx = find_index("شاخص كل")
        assert isinstance(idx, MarketIndex)
        assert idx.ins_code == "32097828799138957"
        assert idx.name == "شاخص كل"

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_finds_sector_index(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_snapshot.return_value = SNAPSHOT_RECORDS
        MockClient.return_value.__exit__.return_value = False
        idx = find_index("سيمان")
        assert idx.ins_code == "70077233737515808"

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_not_found_raises(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_snapshot.return_value = SNAPSHOT_RECORDS
        MockClient.return_value.__exit__.return_value = False
        with pytest.raises(OrboNotFoundError):
            find_index("نام_نامعتبر")


# ── MarketIndex class ─────────────────────────────────────────────────────────

class TestMarketIndex:

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_history_returns_dataframe(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_history.return_value = HISTORY_RECORDS
        MockClient.return_value.__exit__.return_value = False
        idx = MarketIndex("70077233737515808")
        df  = idx.history()
        assert isinstance(df, pd.DataFrame)
        assert "date"  in df.columns
        assert "value" in df.columns

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_today_returns_dataframe(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_today.return_value = TODAY_RECORDS
        MockClient.return_value.__exit__.return_value = False
        idx = MarketIndex("70077233737515808")
        df  = idx.today()
        assert isinstance(df, pd.DataFrame)
        assert "time"  in df.columns
        assert "value" in df.columns

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_companies_returns_dataframe(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_companies.return_value = COMPANY_RECORDS
        MockClient.return_value.__exit__.return_value = False
        idx = MarketIndex("70077233737515808")
        df  = idx.companies()
        assert isinstance(df, pd.DataFrame)
        assert "symbol" in df.columns
        assert "close"  in df.columns

    @patch("orbo.index.market_index.TSETMCIndexClient")
    def test_stats_renames_value_to_close(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_history.return_value = HISTORY_RECORDS
        MockClient.return_value.__exit__.return_value = False
        from orbo.engines.daily_stats import DailyStatsResult
        idx    = MarketIndex("70077233737515808")
        result = idx.stats()
        assert isinstance(result, DailyStatsResult)

    def test_repr_contains_inscode(self):
        idx = MarketIndex("70077233737515808", _name="53-سيمان")
        assert "70077233737515808" in repr(idx)
        assert "53-سيمان" in repr(idx)

    def test_properties(self):
        idx = MarketIndex("70077233737515808", _name="53-سيمان")
        assert idx.ins_code == "70077233737515808"
        assert idx.name     == "53-سيمان"
