class OrboError(Exception):
    """Base exception for all ORBO errors."""


class OrboConnectionError(OrboError):
    """Network / connection related errors."""


class OrboAPIError(OrboError):
    """Server or API errors (5xx, unknown HTTP issues)."""


class OrboNotFoundError(OrboError):
    """Resource not found (404 or empty search result)."""


class RegistryNotInitializedError(OrboError):
    """
    Registry parquet file does not exist.

    Fix: run orbo.bootstrap() once to build the registry from TSETMC data.

        import orbo
        orbo.bootstrap()
    """
