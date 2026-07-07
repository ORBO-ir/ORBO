from __future__ import annotations

import logging

from orbo.clients.tsetmc import TSETMCClient
from orbo.constants import LOGGER_NAME
from orbo.models.search_results import SearchResult

logger = logging.getLogger(LOGGER_NAME)


class SearchResultList(list):
    """
    A list of SearchResult objects that displays with index numbers.

    Indexing works normally: results[0], results[5], etc.
    The repr shows indices so you can immediately pick by number.
    """

    def __repr__(self) -> str:
        if not self:
            return "SearchResultList([])"
        lines = [f"  [{i:>2}]  {r.symbol:<16} {r.name}" for i, r in enumerate(self)]
        return "[\n" + "\n".join(lines) + "\n]"


def search(query: str) -> SearchResultList:
    """
    Search instruments by name or symbol.

    Parameters
    ----------
    query : str
        Search text (Persian symbol or company name).

    Returns
    -------
    SearchResultList
        A list of SearchResult objects. Supports normal indexing:
        results[0], results[5], etc.

    Examples
    --------
    >>> results = search("فولاد")
    >>> results          # shows indexed list
    >>> results[0]       # first match
    >>> results[0].ins_code
    """
    logger.info("search() called with query=%r", query)

    with TSETMCClient() as client:
        raw = client.search(query)

    items = raw.get("instrumentSearch", [])
    return SearchResultList(
        SearchResult.model_validate(item) for item in items
    )
