"""
Unified logging configuration for the tweet scraper project.
Provides a single configure_logging() entry point used by both main.py and scheduler.py.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def configure_logging(
    log_dir: Path,
    level: str = "INFO",
    retention_days: int = 7,
    enable_console: bool = True,
) -> logging.Logger:
    """
    Configure root logger with file (daily rotation) and optional console output.

    Args:
        log_dir: Directory for log files (created if missing).
        level: Logging level (DEBUG/INFO/WARNING/ERROR).
        retention_days: Number of rotated log files to retain.
        enable_console: Also emit logs to stdout.

    Returns:
        The configured root logger.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scraper.log"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers when imported multiple times
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    return root
