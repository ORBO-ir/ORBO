"""
Shared retry decorator for transient HTTP/API failures.

Retries on OrboConnectionError and OrboAPIError (network issues, 5xx,
malformed JSON bodies). Does NOT retry OrboNotFoundError — a missing
instrument or date will not start existing on the next attempt.
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, TypeVar

from orbo.constants import LOGGER_NAME
from orbo.exceptions import OrboConnectionError, OrboAPIError

logger = logging.getLogger(LOGGER_NAME)

T = TypeVar("T")

_RETRYABLE = (OrboConnectionError, OrboAPIError)


def with_retry(retries: int = 3, backoff: float = 1.0) -> Callable:
    """
    Decorator: retry a function on transient failures with exponential backoff.

    Parameters
    ----------
    retries : int
        Total number of attempts (not additional retries). Default 3.
    backoff : float
        Base wait time in seconds, doubling each attempt (1s, 2s, 4s, ...).

    Example
    -------
        @with_retry(retries=3, backoff=1.0)
        def fetch():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None

            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except _RETRYABLE as exc:
                    last_exc = exc
                    logger.warning(
                        "%s failed (attempt %d/%d): %s",
                        getattr(func, "__name__", repr(func)), attempt + 1, retries, exc,
                        )
                    if attempt < retries - 1:
                        time.sleep(backoff * (2 ** attempt))

            assert last_exc is not None
            raise last_exc

        return wrapper
    return decorator
