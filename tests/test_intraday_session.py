"""Tests for orbo.intraday.session.IntradaySession and fetch_intraday_range."""
import pandas as pd
from unittest.mock import patch, MagicMock
from orbo.intraday.session import IntradaySession, fetch_intraday_range
from orbo.exceptions import OrboConnectionError


TRADES_RAW = [
    {"nTran": 1, "hEven": 90001, "qTitTran": 1000, "pTran": 1270.0, "canceled": 0},
]


class TestIntradaySessionLazyLoading:

    @patch("orbo.intraday.session.TSETMCIntradayClient")
    def test_trades_fetched_only_once(self, MockClient):
        client = MockClient.return_value
        client.get_trades.return_value = TRADES_RAW

        session = IntradaySession("123", "20260628")
        _ = session.trades
        _ = session.trades

        client.get_trades.assert_called_once()

    @patch("orbo.intraday.session.TSETMCIntradayClient")
    def test_orderbook_not_fetched_until_accessed(self, MockClient):
        client = MockClient.return_value
        client.get_trades.return_value = TRADES_RAW

        session = IntradaySession("123", "20260628")
        _ = session.trades

        client.get_orderbook.assert_not_called()

    @patch("orbo.intraday.session.TSETMCIntradayClient")
    def test_trades_returns_dataframe(self, MockClient):
        MockClient.return_value.get_trades.return_value = TRADES_RAW
        session = IntradaySession("123", "20260628")
        assert isinstance(session.trades, pd.DataFrame)

    @patch("orbo.intraday.session.TSETMCIntradayClient")
    def test_context_manager_closes_client(self, MockClient):
        client = MockClient.return_value
        client.get_trades.return_value = TRADES_RAW

        with IntradaySession("123", "20260628") as s:
            _ = s.trades

        client.close.assert_called_once()


class _FakeSession:
    """Minimal stand-in for IntradaySession to drive fetch_intraday_range tests."""
    fail_dates_remaining: dict[str, int] = {}

    def __init__(self, inscode, date):
        self.inscode = inscode
        self.date = date
        self.closed = False

    @property
    def trades(self):
        remaining = _FakeSession.fail_dates_remaining.get(self.date, 0)
        if remaining > 0:
            _FakeSession.fail_dates_remaining[self.date] -= 1
            raise OrboConnectionError("simulated failure")
        return pd.DataFrame({"x": [1]})

    def close(self):
        self.closed = True


class TestFetchIntradayRange:

    @patch("orbo.intraday.session.IntradaySession", new=_FakeSession)
    def test_all_succeed_first_round(self):
        _FakeSession.fail_dates_remaining = {}
        sessions, failed = fetch_intraday_range(
            "123", dates=["20260626", "20260627"], fields=["trades"],
            max_retries=2, backoff=0,
        )
        assert failed == []
        assert len(sessions) == 2

    @patch("orbo.intraday.session.IntradaySession", new=_FakeSession)
    def test_retries_only_failed_dates(self):
        _FakeSession.fail_dates_remaining = {"20260627": 1}  # fails once, then succeeds
        sessions, failed = fetch_intraday_range(
            "123", dates=["20260626", "20260627"], fields=["trades"],
            max_retries=2, backoff=0,
        )
        assert failed == []
        assert set(sessions.keys()) == {"20260626", "20260627"}

    @patch("orbo.intraday.session.IntradaySession", new=_FakeSession)
    def test_persistently_failing_date_ends_up_in_failed_list(self):
        _FakeSession.fail_dates_remaining = {"20260627": 99}  # always fails
        sessions, failed = fetch_intraday_range(
            "123", dates=["20260627"], fields=["trades"],
            max_retries=1, backoff=0,
        )
        assert sessions == {}
        assert failed == ["20260627"]
