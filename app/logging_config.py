"""
VERONIKA AI Desktop - Logging Configuration
Sets up structured logging for the application.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.config import LOG_DIR


def setup_logging(level: str = "INFO"):
    """Configure application-wide logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Format
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # File handler (rotating, max 5MB x 3 files)
    log_file = LOG_DIR / "veronika.log"
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)
    except OSError as e:
        root_logger.warning("Could not create log file: %s", e)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    logging.info("Logging initialized at level %s", level)
