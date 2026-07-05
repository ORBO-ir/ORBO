import logging
from orbo.constants import LOGGER_NAME


def setup_logging(level: int = logging.WARNING) -> None:
    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    logger.addHandler(handler)
    logger.setLevel(level)
