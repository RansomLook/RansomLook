"""Centralized logging configuration for RansomLook.

Log level is resolved in this order:
  1. Environment variable ``RANSOMLOOK_LOG_LEVEL`` (DEBUG, INFO, WARNING, ERROR)
  2. ``loglevel`` key in ``config/generic.json``
  3. Default: INFO

Usage:
    from ransomlook.default.logging import get_logger
    logger = get_logger('scrape')
    logger.info('Starting scrape cycle')
"""

import logging
import os
from pathlib import Path

from .config import get_config, get_homedir

_INITIALIZED = False

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_level() -> int:
    # 1. Environment variable
    env = os.environ.get("RANSOMLOOK_LOG_LEVEL", "").upper()
    if env in _LEVEL_MAP:
        return _LEVEL_MAP[env]
    # 2. Config file
    try:
        cfg = get_config("generic", "loglevel", quiet=True)
        if cfg and str(cfg).upper() in _LEVEL_MAP:
            return _LEVEL_MAP[str(cfg).upper()]
    except Exception:
        pass
    # 3. Default
    return logging.INFO


def _ensure_log_dir() -> Path:
    log_dir = get_homedir() / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


class _LevelFilter(logging.Filter):
    """Only accept records at exactly the given level."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self._level


def setup_logging(level: int | None = None) -> None:
    """Initialize root logging: console + one rotating file per level."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    if level is None:
        level = _resolve_level()

    log_dir = _ensure_log_dir()

    fmt = "%(asctime)s %(name)-20s %(levelname)-8s %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        return

    # One file per level (only levels >= configured level)
    for lvl_name, lvl_value in _LEVEL_MAP.items():
        if lvl_value < level:
            continue
        log_file = log_dir / f"{lvl_name.lower()}.log"
        handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        handler.setLevel(lvl_value)
        handler.addFilter(_LevelFilter(lvl_value))
        root.addHandler(handler)

    # Console handler (all levels >= configured level)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, initializing the logging system if needed."""
    setup_logging()
    return logging.getLogger(f"ransomlook.{name}")
