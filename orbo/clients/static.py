import logging
import httpx

from orbo.constants import (
    BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_HEADERS,
    LOGGER_NAME,
    MARKETMAP_ALL,
)


from orbo.exceptions import OrboConnectionError, OrboAPIError, OrboNotFoundError

logger = logging.getLogger(LOGGER_NAME)



class StaticDataClient:
    def __init__(self):
        self.client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            headers=DEFAULT_HEADERS,
        )

    def _get(self, url: str):
        logger.info("GET %s", url)

        try:
            r = self.client.get(url)
            r.raise_for_status()
            return r

        except httpx.TimeoutException as exc:
            raise OrboConnectionError("Request timed out.") from exc

        except httpx.ConnectError as exc:
            raise OrboConnectionError("TSETMC is unreachable.") from exc

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise OrboNotFoundError(url) from exc
            raise OrboAPIError(f"HTTP error {status}") from exc

        except httpx.RequestError as exc:
            raise OrboConnectionError("Request failed.") from exc

    def get_static_data(self):
        r = self._get(f"{BASE_URL}/StaticData/GetStaticData")
        return r.json()

    def get_server_time(self):
        r = self._get(f"{BASE_URL}/StaticData/GetTime")
        return r.text.strip()

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get_marketmap(
        self,
        market: str = MARKETMAP_ALL,
        size: int = 1499,
        sector: int = 0,
        type_selected: int = 1,
        h_even: int = 0,
    ):

        url = (
            "/ClosingPrice/GetMarketMap"
            f"?market={market}"
            f"&size={size}"
            f"&sector={sector}"
            f"&typeSelected={type_selected}"
            f"&hEven={h_even}"
        )

        r = self._get(f"{BASE_URL}{url}")

        return r.json()    
