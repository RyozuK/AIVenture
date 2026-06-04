"""Structured logging setup for AIVenture."""

from __future__ import annotations

import logging
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: LogLevel = "INFO", verbose: bool = False) -> logging.Logger:
    """Configure the root ``aiventure`` logger and return it.

    Parameters
    ----------
    level :
        Minimum severity to emit.
    verbose :
        If *True*, use ``DEBUG`` regardless of *level* (convenience flag).
    """
    if verbose:
        level = "DEBUG"

    logger = logging.getLogger("aiventure")
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(getattr(logging, level.upper()))
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(handler)

    # Silence overly-chatty third-party loggers
    for noisy in ("httpx", "openai", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logger