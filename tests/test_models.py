import pytest
from orbo.models.search_results import SearchResult
from orbo.models.identity import InstrumentIdentity


class TestSearchResult:

    RAW = {
        "insCode": "35700344742885862",
        "lVal18AFC": "فملی",
        "lVal30": "فولاد مبارکه اصفهان",
        "flow": 1,
        "lastDate": 20240601,
        "extraField": "should be ignored",
    }

    def test_fields_parse_correctly(self):
        result = SearchResult.model_validate(self.RAW)
        assert result.ins_code == "35700344742885862"
        assert result.symbol == "فملی"
        assert result.name == "فولاد مبارکه اصفهان"

    def test_optional_fields(self):
        result = SearchResult.model_validate(self.RAW)
        assert result.flow == 1
        assert result.last_date == 20240601

    def test_extra_fields_are_ignored(self):
        result = SearchResult.model_validate(self.RAW)
        assert not hasattr(result, "extraField")

    def test_missing_optional_fields_are_none(self):
        minimal = {
            "insCode": "123",
            "lVal18AFC": "test",
            "lVal30": "test name",
        }
        result = SearchResult.model_validate(minimal)
        assert result.flow is None
        assert result.last_date is None

    def test_repr_contains_symbol_and_name(self):
        result = SearchResult.model_validate(self.RAW)
        assert "فملی" in repr(result)
        assert "فولاد مبارکه اصفهان" in repr(result)


class TestInstrumentIdentity:

    RAW = {
        "insCode": "35700344742885862",
        "lVal18AFC": "فملی",
        "lVal30": "فولاد مبارکه اصفهان",
        "lVal30En": "Foolad Mobarakeh",
        "cIsin": "IRO1FOLD0001",
        "flow": 1,
        "cgrValCot": "N1",
    }

    def test_fields_parse_correctly(self):
        identity = InstrumentIdentity.model_validate(self.RAW)
        assert identity.ins_code == "35700344742885862"
        assert identity.symbol == "فملی"
        assert identity.isin == "IRO1FOLD0001"
        assert identity.name_en == "Foolad Mobarakeh"
        assert identity.sector == "N1"

    def test_missing_optional_fields_are_none(self):
        minimal = {
            "insCode": "123",
            "lVal18AFC": "test",
            "lVal30": "test name",
        }
        identity = InstrumentIdentity.model_validate(minimal)
        assert identity.isin is None
        assert identity.name_en is None

    def test_repr_contains_symbol_and_isin(self):
        identity = InstrumentIdentity.model_validate(self.RAW)
        assert "فملی" in repr(identity)
        assert "IRO1FOLD0001" in repr(identity)
