from __future__ import annotations

import logging
from urllib.parse import quote
from typing import Any, Dict, Optional

import httpx

from orbo.constants import (
    BASE_URL,
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT,
    LOGGER_NAME,
)

from orbo.exceptions import (
    OrboConnectionError,
    OrboAPIError,
    OrboNotFoundError,
)

logger = logging.getLogger(LOGGER_NAME)


# =========================================================
# HTTP CORE LAYER
# =========================================================

class HTTPClient:
    """
    Low-level HTTP wrapper.
    Responsible ONLY for transport layer.
    """

    def __init__(
        self,
        base_url: str,
        headers: dict,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    def get(self, endpoint: str) -> Dict[str, Any]:
        try:
            response = self._client.get(endpoint)
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException as exc:
            logger.error("Timeout on %s", endpoint)
            raise OrboConnectionError("Request timed out.") from exc


        except httpx.ConnectError as exc:
            logger.error("Connection error on %s", endpoint)
            raise OrboConnectionError(
                "TSETMC is unreachable. "
                "Check VPN, proxy, DNS, or internet connection."
            ) from exc


        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            logger.error("HTTP %s on %s", status, endpoint)
        
            if status == 404:
                raise OrboNotFoundError(endpoint) from exc
        
            if status >= 500:
                raise OrboAPIError("TSETMC server error.") from exc

            raise OrboAPIError(f"HTTP error {status}") from exc


        except httpx.RequestError as exc:
            logger.error("Request error on %s", endpoint)
            raise OrboConnectionError("Request failed.") from exc

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# =========================================================
# DOMAIN CLIENT (TSETMC)
# =========================================================

class TSETMCClient:
    """
    Scalable TSETMC API client.

    This layer:
    - defines endpoints
    - handles input validation
    - delegates HTTP to HTTPClient
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: Optional[HTTPClient] = None,
    ):
        self.http = http_client or HTTPClient(
            base_url=BASE_URL,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )

        logger.debug("TSETMCClient initialized")

    # -----------------------------------------------------
    # CORE INTERNAL REQUEST METHOD
    # -----------------------------------------------------

    def _get(self, endpoint: str) -> Dict[str, Any]:
        logger.info("GET %s", endpoint)
        return self.http.get(endpoint)

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    def search(self, query: str) -> Dict[str, Any]:
        query = query.strip()

        if not query:
            raise ValueError("query cannot be empty")

        endpoint = f"/Instrument/GetInstrumentSearch/{quote(query)}"

        logger.info("search query=%s", query)

        return self._get(endpoint)

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    def get_identity(self, ins_code: str) -> Dict[str, Any]:
        ins_code = str(ins_code).strip()

        if not ins_code:
            raise ValueError("ins_code cannot be empty")

        endpoint = f"/Instrument/GetInstrumentIdentity/{ins_code}"

        logger.info("identity ins_code=%s", ins_code)

        return self._get(endpoint)

    # -----------------------------------------------------
    # FUTURE EXTENSION POINTS (IMPORTANT)
    # -----------------------------------------------------

    def get_price(self, ins_code: str):
        """
        Placeholder for future extension.
        """
        raise NotImplementedError

    def get_history(self, ins_code: str):
        """
        Placeholder for historical data module.
        """
        raise NotImplementedError

    # -----------------------------------------------------
    # CLEANUP
    # -----------------------------------------------------

    def close(self):
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

