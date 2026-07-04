"""Tests for orbo.instrument.Instrument and LiveSnapshot."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from orbo.instrument import Instrument, LiveSnapshot
from orbo.exceptions import OrboNotFoundError


FAKE_SEARCH_RESULT = MagicMock()
FAKE_SEARCH_RESULT.ins_code = "7745894403636165"
FAKE_SEARCH_RESULT.symbol   = "شپنا"
FAKE_SEARCH_RESULT.name     = "پالایش نفت اصفهان"

FAKE_DAILY_DF = pd.DataFrame([{
    "date": "1405-04-07", "time": "12:29:59",
    "open": 10220.0, "high": 10220.0, "low": 9930.0,
    "close": 10190.0, "last_price": 10210.0, "prev_close": 9930.0,
    "close_change": 260.0, "close_pct": 2.62,
    "last_change": 280.0, "last_pct": 2.82,
    "trade_count": 52293, "volume": 3_379_786_204, "value": 34_437_417_248_060,
}])

FAKE_REGISTRY = MagicMock()
FAKE_REGISTRY_RECORD = MagicMock()
FAKE_REGISTRY_RECORD.ins_code = 7745894403636165
FAKE_REGISTRY_RECORD.symbol   = "شپنا"
FAKE_REGISTRY_RECORD.name     = "پالایش نفت اصفهان"


class TestInstrumentResolution:

    @patch("orbo.instrument.registry")
    def test_resolve_by_long_numeric_string_skips_registry(self, mock_reg):
        """18-digit inscode should bypass registry entirely."""
        inst = Instrument("7745894403636165")
        assert inst.inscode == "7745894403636165"
        mock_reg.lookup.assert_not_called()

    @patch("orbo.instrument.registry")
    def test_resolve_by_symbol_via_registry(self, mock_reg):
        mock_reg.lookup.return_value = FAKE_REGISTRY_RECORD
        inst = Instrument("شپنا")
        assert inst.inscode == "7745894403636165"
        assert inst.symbol  == "شپنا"

    @patch("orbo.instrument.registry")
    @patch("orbo.instrument.search")
    def test_resolve_via_search_when_registry_misses(self, mock_search, mock_reg):
        mock_reg.lookup.return_value = None
        mock_search.return_value = [FAKE_SEARCH_RESULT]
        inst = Instrument("شپنا")
        assert inst.inscode == "7745894403636165"
        mock_search.assert_called_once_with("شپنا")

    @patch("orbo.instrument.registry")
    @patch("orbo.instrument.search")
    def test_not_found_raises(self, mock_search, mock_reg):
        mock_reg.lookup.return_value = None
        mock_search.return_value = []
        with pytest.raises(OrboNotFoundError):
            Instrument("نمادنامعتبر")

    @patch("orbo.instrument.registry")
    @patch("orbo.instrument.search")
    def test_registry_file_not_found_falls_back_to_search(self, mock_search, mock_reg):
        mock_reg.lookup.side_effect = FileNotFoundError("no registry file")
        mock_search.return_value = [FAKE_SEARCH_RESULT]
        inst = Instrument("شپنا")
        assert inst.inscode == "7745894403636165"

    def test_repr_contains_inscode(self):
        with patch("orbo.instrument.registry") as mock_reg:
            mock_reg.lookup.return_value = FAKE_REGISTRY_RECORD
            inst = Instrument("شپنا")
        assert "7745894403636165" in repr(inst)


class TestInstrumentMethods:

    def _make_instrument(self):
        with patch("orbo.instrument.registry") as mock_reg:
            mock_reg.lookup.return_value = FAKE_REGISTRY_RECORD
            return Instrument("شپنا")

    @patch("orbo.instrument.InstrumentHistory")
    def test_history_returns_dataframe(self, MockHistory):
        MockHistory.return_value.fetch.return_value = FAKE_DAILY_DF
        inst = self._make_instrument()
        df = inst.history()
        assert isinstance(df, pd.DataFrame)
        MockHistory.assert_called_once_with("7745894403636165")

    @patch("orbo.instrument.InstrumentHistory")
    def test_history_passes_adjust_flag(self, MockHistory):
        MockHistory.return_value.fetch.return_value = FAKE_DAILY_DF
        inst = self._make_instrument()
        inst.history(count=30, adjust=True)
        MockHistory.return_value.fetch.assert_called_once_with(
            count=30, adjust=True, raw=False
        )

    @patch("orbo.instrument.InstrumentHistory")
    def test_today_calls_today_method(self, MockHistory):
        MockHistory.return_value.today.return_value = FAKE_DAILY_DF.iloc[[0]]
        inst = self._make_instrument()
        df = inst.today()
        assert len(df) == 1
        MockHistory.return_value.today.assert_called_once()

    @patch("orbo.instrument.IntradaySession")
    def test_intraday_returns_session_object(self, MockSession):
        inst = self._make_instrument()
        session = inst.intraday("20260628")
        MockSession.assert_called_once_with("7745894403636165", "20260628")

    @patch("orbo.instrument.DailyStatsEngine")
    @patch("orbo.instrument.InstrumentHistory")
    def test_stats_uses_history_and_engine(self, MockHistory, MockEngine):
        MockHistory.return_value.fetch.return_value = FAKE_DAILY_DF
        mock_result = MagicMock()
        MockEngine.return_value.compute.return_value = mock_result

        inst = self._make_instrument()
        result = inst.stats()

        MockHistory.return_value.fetch.assert_called_once()
        MockEngine.return_value.compute.assert_called_once_with(FAKE_DAILY_DF)
        assert result is mock_result


class TestLiveSnapshot:

    FAKE_PRICE = {"closingPriceInfo": {
        "dEven": 20260629, "hEven": 122948,
        "priceFirst": 10470.0, "priceMax": 10490.0, "priceMin": 10300.0,
        "pClosing": 10480.0, "pDrCotVal": 10490.0, "priceYesterday": 10190.0,
        "priceChange": 0.0, "zTotTran": 21086.0,
        "qTotTran5J": 1_335_987_211.0, "qTotCap": 14_001_471_796_770.0,
        "instrumentState": None, "instrument": None,
    }}

    FAKE_TRADES = [
        {"nTran": 1, "hEven": 90001, "qTitTran": 1000, "pTran": 5080.0, "canceled": 0}
    ]

    FAKE_ORDERBOOK = [
        {"number": 1, "qTitMeDem": 6512884, "zOrdMeDem": 52,
         "pMeDem": 5090.0, "pMeOf": 5130.0, "zOrdMeOf": 2, "qTitMeOf": 22620,
         "title": None, "insCode": None},
    ]

    FAKE_CLIENT_TYPE = {
        "buy_I_Volume": 38711174.0, "buy_N_Volume": 2706467.0,
        "buy_CountI": 230, "buy_CountN": 4,
        "sell_I_Volume": 31270171.0, "sell_N_Volume": 10147470.0,
        "sell_CountI": 265, "sell_CountN": 3,
    }

    def _make_snapshot(self):
        return LiveSnapshot(
            _price_raw       = self.FAKE_PRICE,
            _trades_raw      = self.FAKE_TRADES,
            _orderbook_raw   = self.FAKE_ORDERBOOK,
            _client_type_raw = self.FAKE_CLIENT_TYPE,
            _inscode         = "51017863148152520",
        )

    def test_price_returns_dataframe(self):
        snap = self._make_snapshot()
        df = snap.price
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert "close" in df.columns

    def test_trades_returns_dataframe(self):
        snap = self._make_snapshot()
        df = snap.trades
        assert isinstance(df, pd.DataFrame)
        assert "trade_no" in df.columns

    def test_orderbook_returns_dataframe(self):
        snap = self._make_snapshot()
        df = snap.orderbook
        assert isinstance(df, pd.DataFrame)
        assert "bid_price" in df.columns
        assert "ask_price" in df.columns

    def test_client_type_returns_dataframe(self):
        snap = self._make_snapshot()
        df = snap.client_type
        assert isinstance(df, pd.DataFrame)
        assert "net_real_volume" in df.columns

    def test_net_real_volume_in_client_type(self):
        snap = self._make_snapshot()
        df = snap.client_type
        expected = 38711174 - 31270171
        assert df.iloc[0]["net_real_volume"] == pytest.approx(expected)
