
import logging
import sys
from typing import Optional


def setup_logger(
    name: str,
    level: int = logging.INFO,
    format_str: Optional[str] = None,
) -> logging.Logger:
    if format_str is None:
        format_str = "%(levelname)-8s | %(name)s | %(message)s"

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(format_str)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False

    return logger


# Global Cognex logger for CLI/server output
COGNEX_LOGGER = setup_logger(
    "cognex",
    level=logging.INFO,
    format_str="%(message)s",  # Clean format for CLI
)

# Test logger with more detail
TEST_LOGGER = setup_logger(
    "cognex.tests",
    level=logging.INFO,
    format_str="  %(levelname)-4s | %(message)s",
)
