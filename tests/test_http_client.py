import pytest
import httpx
from unittest.mock import MagicMock, patch
from orbo.clients.tsetmc import HTTPClient
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError


class TestHTTPClient:

    @patch("orbo.clients.tsetmc.httpx.Client")
    def test_timeout_raises_connection_error(self, mock_httpx):
        mock_httpx.return_value.get.side_effect = httpx.TimeoutException("timeout")

        client = HTTPClient(base_url="https://example.com", headers={})

        with pytest.raises(OrboConnectionError, match="timed out"):
            client.get("/test")

    @patch("orbo.clients.tsetmc.httpx.Client")
    def test_connect_error_raises_connection_error(self, mock_httpx):
        mock_httpx.return_value.get.side_effect = httpx.ConnectError("refused")

        client = HTTPClient(base_url="https://example.com", headers={})

        with pytest.raises(OrboConnectionError, match="unreachable"):
            client.get("/test")

    @patch("orbo.clients.tsetmc.httpx.Client")
    def test_404_raises_not_found_error(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_httpx.return_value.get.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )

        client = HTTPClient(base_url="https://example.com", headers={})

        with pytest.raises(OrboNotFoundError):
            client.get("/missing")

    @patch("orbo.clients.tsetmc.httpx.Client")
    def test_500_raises_api_error(self, mock_httpx):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_httpx.return_value.get.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        client = HTTPClient(base_url="https://example.com", headers={})

        with pytest.raises(OrboAPIError, match="server error"):
            client.get("/error")
