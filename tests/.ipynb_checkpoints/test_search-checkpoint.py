import pytest
from unittest.mock import patch, MagicMock
from orbo.search.instrument_search import search
from orbo.models.search_results import SearchResult
from orbo.exceptions import OrboConnectionError


FAKE_RESPONSE = {
    "instrumentSearch": [
        {
            "insCode": "35700344742885862",
            "lVal18AFC": "فملی",
            "lVal30": "فولاد مبارکه اصفهان",
            "flow": 1,
            "lastDate": 20240601,
        },
        {
            "insCode": "111111111111",
            "lVal18AFC": "فملی۲",
            "lVal30": "فولاد دوم",
            "flow": 1,
        },
    ]
}


class TestSearch:

    @patch("orbo.search.instrument_search.TSETMCClient")
    def test_returns_list_of_search_results(self, mock_client_class):
        mock_instance = MagicMock()
        mock_instance.search.return_value = FAKE_RESPONSE
        mock_client_class.return_value.__enter__.return_value = mock_instance
        mock_client_class.return_value.__exit__.return_value = False

        results = search("فملی")

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    @patch("orbo.search.instrument_search.TSETMCClient")
    def test_result_fields_are_correct(self, mock_client_class):
        mock_instance = MagicMock()
        mock_instance.search.return_value = FAKE_RESPONSE
        mock_client_class.return_value.__enter__.return_value = mock_instance
        mock_client_class.return_value.__exit__.return_value = False

        results = search("فملی")

        assert results[0].symbol == "فملی"
        assert results[0].ins_code == "35700344742885862"
        assert results[0].name == "فولاد مبارکه اصفهان"

    @patch("orbo.search.instrument_search.TSETMCClient")
    def test_empty_result_returns_empty_list(self, mock_client_class):
        mock_instance = MagicMock()
        mock_instance.search.return_value = {"instrumentSearch": []}
        mock_client_class.return_value.__enter__.return_value = mock_instance
        mock_client_class.return_value.__exit__.return_value = False

        results = search("xxxx_not_found")

        assert results == []

    @patch("orbo.search.instrument_search.TSETMCClient")
    def test_connection_error_propagates(self, mock_client_class):
        mock_instance = MagicMock()
        mock_instance.search.side_effect = OrboConnectionError("Unreachable")
        mock_client_class.return_value.__enter__.return_value = mock_instance
        mock_client_class.return_value.__exit__.return_value = False

        with pytest.raises(OrboConnectionError):
            search("فملی")
