"""Tests for the intraday transformer functions in orbo.data.transformers."""
import pytest
import pandas as pd
from orbo.data.transformers import (
    trade_history_to_dataframe,
    orderbook_to_dataframe,
    price_tape_to_dataframe,
    shareholders_to_dataframe,
    client_type_to_dataframe,
)


TRADES_OUT_OF_ORDER = [
    {"nTran": 3, "hEven": 90015, "qTitTran": 500,  "pTran": 1280.0, "canceled": 0},
    {"nTran": 1, "hEven": 90001, "qTitTran": 1000, "pTran": 1270.0, "canceled": 0},
    {"nTran": 2, "hEven": 90010, "qTitTran": 800,  "pTran": 1275.0, "canceled": 0},
]


class TestTradeHistoryToDataframe:

    def test_sorts_by_trade_no_regardless_of_input_order(self):
        df = trade_history_to_dataframe(TRADES_OUT_OF_ORDER, date="20260628")
        assert df["trade_no"].tolist() == [1, 2, 3]

    def test_has_expected_columns(self):
        df = trade_history_to_dataframe(TRADES_OUT_OF_ORDER, date="20260628")
        for col in ["date", "time", "trade_no", "price", "volume", "canceled"]:
            assert col in df.columns

    def test_injects_jalali_date(self):
        df = trade_history_to_dataframe(TRADES_OUT_OF_ORDER, date="20260628")
        assert (df["date"] == "1405-04-07").all()

    def test_empty_records_returns_empty_df(self):
        assert trade_history_to_dataframe([], date="20260628").empty


ORDERBOOK_RECORDS = [
    {"refID": 200, "hEven": 90100, "number": 1, "pMeDem": 10410.0, "qTitMeDem": 1000,
     "zOrdMeDem": 3, "pMeOf": 10470.0, "qTitMeOf": 500, "zOrdMeOf": 2},
    {"refID": 100, "hEven": 90050, "number": 1, "pMeDem": 10400.0, "qTitMeDem": 900,
     "zOrdMeDem": 2, "pMeOf": 0.0, "qTitMeOf": 0, "zOrdMeOf": 0},
]


class TestOrderbookToDataframe:

    def test_sorts_by_ref_id(self):
        df = orderbook_to_dataframe(ORDERBOOK_RECORDS, date="20260628")
        assert df["ref_id"].tolist() == [100, 200]

    def test_has_expected_columns(self):
        df = orderbook_to_dataframe(ORDERBOOK_RECORDS, date="20260628")
        expected = ["date", "time", "ref_id", "level",
                    "bid_price", "bid_qty", "bid_orders",
                    "ask_price", "ask_qty", "ask_orders"]
        assert list(df.columns) == expected

    def test_empty_ask_stays_zero_not_nan(self):
        df = orderbook_to_dataframe(ORDERBOOK_RECORDS, date="20260628")
        row = df[df["ref_id"] == 100].iloc[0]
        assert row["ask_price"] == 0.0

    def test_empty_records_returns_empty_df(self):
        assert orderbook_to_dataframe([], date="20260628").empty


PRICE_TAPE_RECORDS = [
    {"hEven": 122959, "pClosing": 10190, "pDrCotVal": 10210,
     "zTotTran": 52293, "qTotTran5J": 3379786204, "qTotCap": 34437417248060},
    {"hEven": 90100, "pClosing": 10000, "pDrCotVal": 10050,
     "zTotTran": 100, "qTotTran5J": 50000, "qTotCap": 500000000},
]


class TestPriceTapeToDataframe:

    def test_sorts_by_time_ascending(self):
        df = price_tape_to_dataframe(PRICE_TAPE_RECORDS, date="20260628")
        assert df["time"].tolist() == ["09:01:00", "12:29:59"]

    def test_has_expected_columns(self):
        df = price_tape_to_dataframe(PRICE_TAPE_RECORDS, date="20260628")
        for col in ["date", "time", "close", "last_price", "trade_count", "volume", "value"]:
            assert col in df.columns

    def test_empty_records_returns_empty_df(self):
        assert price_tape_to_dataframe([], date="20260628").empty


SHAREHOLDER_RECORDS = [
    {"shareHolderName": "Bank A", "cIsin": "IRO1XXX", "dEven": 20260628,
     "numberOfShares": 1000, "perOfShares": 1.0, "change": 1, "changeAmount": 0},
    {"shareHolderName": "Fund B", "cIsin": "IRO1XXX", "dEven": 20260628,
     "numberOfShares": 5000, "perOfShares": 5.0, "change": 1, "changeAmount": 0},
]


class TestShareholdersToDataframe:

    def test_sorted_by_shares_descending(self):
        df = shareholders_to_dataframe(SHAREHOLDER_RECORDS)
        assert df.iloc[0]["shareholder"] == "Fund B"

    def test_has_jalali_date(self):
        df = shareholders_to_dataframe(SHAREHOLDER_RECORDS)
        assert (df["date"] == "1405-04-07").all()

    def test_empty_records_returns_empty_df(self):
        assert shareholders_to_dataframe([]).empty


CLIENT_TYPE_RECORD = {
    "buy_I_Volume": 2_000_000, "sell_I_Volume": 1_500_000,
    "buy_I_Value": 20_000_000_000, "sell_I_Value": 14_000_000_000,
    "buy_N_Volume": 800_000, "sell_N_Volume": 1_300_000,
    "buy_N_Value": 9_000_000_000, "sell_N_Value": 13_500_000_000,
    "buy_I_Count": 1000, "sell_I_Count": 900,
    "buy_N_Count": 10, "sell_N_Count": 15,
}


class TestClientTypeToDataframe:

    def test_returns_single_row(self):
        df = client_type_to_dataframe(CLIENT_TYPE_RECORD, date="20260628")
        assert len(df) == 1

    def test_net_real_volume_calculated(self):
        df = client_type_to_dataframe(CLIENT_TYPE_RECORD, date="20260628")
        assert df.iloc[0]["net_real_volume"] == 500_000

    def test_net_real_value_calculated(self):
        df = client_type_to_dataframe(CLIENT_TYPE_RECORD, date="20260628")
        assert df.iloc[0]["net_real_value"] == 6_000_000_000

    def test_empty_record_returns_empty_df(self):
        assert client_type_to_dataframe({}, date="20260628").empty
