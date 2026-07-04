"""Tests for orbo.clients.retry.with_retry."""
import pytest
from unittest.mock import MagicMock
from orbo.clients.retry import with_retry
from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError


class TestWithRetry:

    def test_succeeds_first_try_calls_once(self):
        mock_fn = MagicMock(return_value="ok")
        wrapped = with_retry(retries=3, backoff=0)(mock_fn)
        assert wrapped() == "ok"
        assert mock_fn.call_count == 1

    def test_succeeds_after_two_failures(self):
        mock_fn = MagicMock(side_effect=[
            OrboConnectionError("timeout"),
            OrboConnectionError("timeout"),
            "ok",
        ])
        wrapped = with_retry(retries=3, backoff=0)(mock_fn)
        assert wrapped() == "ok"
        assert mock_fn.call_count == 3

    def test_raises_after_exhausting_retries(self):
        mock_fn = MagicMock(side_effect=OrboAPIError("server error"))
        wrapped = with_retry(retries=3, backoff=0)(mock_fn)
        with pytest.raises(OrboAPIError):
            wrapped()
        assert mock_fn.call_count == 3

    def test_does_not_retry_not_found(self):
        mock_fn = MagicMock(side_effect=OrboNotFoundError("missing"))
        wrapped = with_retry(retries=3, backoff=0)(mock_fn)
        with pytest.raises(OrboNotFoundError):
            wrapped()
        assert mock_fn.call_count == 1

    def test_does_not_retry_unrelated_exceptions(self):
        mock_fn = MagicMock(side_effect=ValueError("unrelated"))
        wrapped = with_retry(retries=3, backoff=0)(mock_fn)
        with pytest.raises(ValueError):
            wrapped()
        assert mock_fn.call_count == 1
