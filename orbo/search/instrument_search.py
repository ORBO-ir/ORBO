from __future__ import annotations

import logging

from orbo.clients.tsetmc import TSETMCClient
from orbo.constants import LOGGER_NAME
from orbo.models.search_results import SearchResult

logger = logging.getLogger(LOGGER_NAME)


def search(query: str) -> list[SearchResult]:
    """
    Search instruments by name or symbol.

    Parameters
    ----------
    query:
        Search text.

    Returns
    -------
    list[SearchResult]

    Examples
    --------
    >>> results = search("فملی")
    >>> results[0].symbol
    'فملی'
    >>> results[0].ins_code
    '35700344742885862'
    """

    logger.info("search() called with query=%s", query)

    with TSETMCClient() as client:
        raw = client.search(query)

    items = raw.get("instrumentSearch", [])

    return [SearchResult.model_validate(item) for item in items]
