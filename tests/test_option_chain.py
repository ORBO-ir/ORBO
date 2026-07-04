"""Tests for orbo.option_chain.OptionChain and option transformer."""
import pandas as pd
import pytest

from pandas.api.types import is_string_dtype
from unittest.mock import patch, MagicMock

from orbo.option_chain import OptionChain
from orbo.data.transformers import option_chain_to_dataframe


# ── Sample data (3 strikes, 1 underlying, 1 expiry) ─────────────────────────

FAKE_RECORDS = [
    {
        "insCode_C": "111", "insCode_P": "222",
        "lVal18AFC_C": "ضهرم4023", "lVal18AFC_P": "طهرم4023",
        "contractSize": 1000, "uaInsCode": "999",
        "lval30_UA": "اهرم",
        "pClosing_UA": 46440, "pDrCotVal_UA": 47027, "priceYesterday_UA": 45219,
        "beginDate": "20260221", "endDate": "20260722",
        "strikePrice": 20000, "remainedDay": 19,
        "pClosing_C": 27004, "pDrCo/tVal_C": 27200,
        "zTotTran_C": 143,   "qTotTran5J_C": 4042,
        "qTotCap_C": 109152048000, "notionalValue_C": 187710480000, "oP_C": 108082,
        "pMeDem_C": 22,    "qTitMeDem_C": 22,
        "pMeOf_C": 27400,  "qTitMeOf_C": 4,
        "pClosing_P": 37,   "pDrCotVal_P": 43,
        "zTotTran_P": 27,   "qTotTran5J_P": 4085,
        "qTotCap_P": 152446000, "notionalValue_P": 189707400000, "oP_P": 94072,
        "pMeDem_P": 50,    "qTitMeDem_P": 2488,
        "pMeOf_P": 80,     "qTitMeOf_P": 1000,
        "yesterdayOP_C": 108082, "yesterdayOP_P": 94072,
    },
    {
        "insCode_C": "333", "insCode_P": "444",
        "lVal18AFC_C": "ضهرم4029", "lVal18AFC_P": "طهرم4029",
        "contractSize": 1000, "uaInsCode": "999",
        "lval30_UA": "اهرم",
        "pClosing_UA": 46440, "pDrCotVal_UA": 47027, "priceYesterday_UA": 45219,
        "beginDate": "20260221", "endDate": "20260722",
        "strikePrice": 34000, "remainedDay": 19,
        "pClosing_C": 13019, "pDrCotVal_C": 13181,
        "zTotTran_C": 449, "qTotTran5J_C": 10005,
        "qTotCap_C": 130251287000, "notionalValue_C": 461026536000, "oP_C": 184589,
        "pMeDem_C": 13181, "qTitMeDem_C": 23,
        "pMeOf_C": 13300,  "qTitMeOf_C": 5,
        "pClosing_P": 84,  "pDrCotVal_P": 91,
        "zTotTran_P": 43,  "qTotTran5J_P": 3279,
        "qTotCap_P": 276441000, "notionalValue_P": 152266923000, "oP_P": 340702,
        "pMeDem_P": 90,    "qTitMeDem_P": 4503,
        "pMeOf_P": 100,    "qTitMeOf_P": 23,
        "yesterdayOP_C": 184589, "yesterdayOP_P": 340702,
    },
]


# ── Transformer tests ────────────────────────────────────────────────────────

class TestOptionChainTransformer:

    def test_returns_dataframe(self):
        df = option_chain_to_dataframe(FAKE_RECORDS)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_has_core_columns(self):
        df = option_chain_to_dataframe(FAKE_RECORDS)
        for col in ["underlying_symbol", "strike", "dte",
                    "call_symbol", "call_close", "call_bid", "call_ask",
                    "put_symbol",  "put_close",  "put_bid",  "put_ask",
                    "call_moneyness", "put_moneyness",
                    "expiry_jalali"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_sorted_by_strike_ascending(self):
        df = option_chain_to_dataframe(FAKE_RECORDS)
        strikes = df["strike"].tolist()
        assert strikes == sorted(strikes)

    def test_call_moneyness_itm_when_underlying_above_strike(self):
        # underlying=46440, strike=20000 → call is ITM
        df  = option_chain_to_dataframe(FAKE_RECORDS)
        row = df[df["strike"] == 20000].iloc[0]
        assert row["call_moneyness"] == "ITM"

    def test_put_moneyness_otm_when_underlying_above_strike(self):
        # underlying=46440, strike=20000 → put is OTM
        df  = option_chain_to_dataframe(FAKE_RECORDS)
        row = df[df["strike"] == 20000].iloc[0]
        assert row["put_moneyness"] == "OTM"

    def test_call_moneyness_otm_when_strike_above_underlying(self):
        # underlying=46440, strike=34000 still ITM, try a hypothetical high strike
        # With our data: strike=34000 < underlying=46440 → still ITM
        df  = option_chain_to_dataframe(FAKE_RECORDS)
        row = df[df["strike"] == 34000].iloc[0]
        assert row["call_moneyness"] == "ITM"

    def test_jalali_expiry_is_string(self):
        df = option_chain_to_dataframe(FAKE_RECORDS)

        assert is_string_dtype(df["expiry_jalali"])

        jalali = df["expiry_jalali"].iloc[0]
        parts = jalali.split("-")
        assert len(parts) == 3

    def test_empty_records_returns_empty_df(self):
        df = option_chain_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ── OptionChain class tests ──────────────────────────────────────────────────

class TestOptionChain:

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_fetch_returns_option_chain(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        assert isinstance(chain, OptionChain)

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_chain_property_returns_dataframe(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        df = chain.chain
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_underlyings_returns_list(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        assert isinstance(chain.underlyings, list)
        assert "اهرم" in chain.underlyings

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_filter_by_underlying(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        df = chain.filter("اهرم")
        assert not df.empty
        assert (df["underlying_symbol"] == "اهرم").all()

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_filter_unknown_underlying_returns_empty(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        df = chain.filter("نمادنادرست")
        assert df.empty

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_expiries_returns_sorted_list(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain   = OptionChain.fetch()
        expiries = chain.expiries("اهرم")
        assert isinstance(expiries, list)
        assert len(expiries) >= 1
        assert expiries == sorted(expiries)

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_for_expiry_returns_correct_strikes(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain   = OptionChain.fetch()
        expiries = chain.expiries("اهرم")
        df      = chain.for_expiry("اهرم", expiries[0])

        assert not df.empty
        assert (df["underlying_symbol"] == "اهرم").all()
        # Sorted by strike ascending
        assert df["strike"].tolist() == sorted(df["strike"].tolist())

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_refresh_updates_data(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        initial_len = len(chain)
        result = chain.refresh()

        assert result is chain           # returns self
        assert len(chain) == initial_len # same data (same mock)

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_summary_has_expected_columns(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain   = OptionChain.fetch()
        summary = chain.summary()
        for col in ["underlying_symbol", "expiry_jalali", "n_strikes"]:
            assert col in summary.columns

    @patch("orbo.option_chain.option_chain.TSETMCOptionClient")
    def test_repr_shows_info(self, MockClient):
        MockClient.return_value.__enter__.return_value.get_chain.return_value = FAKE_RECORDS
        MockClient.return_value.__exit__.return_value = False

        chain = OptionChain.fetch()
        r = repr(chain)
        assert "OptionChain" in r
