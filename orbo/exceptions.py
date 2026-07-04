class OrboError(Exception):
    """Base exception for ORBO project."""


class OrboConnectionError(OrboError):
    """Network / connection related errors."""


class OrboAPIError(OrboError):
    """Server or API errors (5xx, unknown HTTP issues)."""


class OrboNotFoundError(OrboError):
    """Resource not found (404)."""
