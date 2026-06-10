"""
CE-Harness Observability Module
=================================
Structured logging with JSON/text output and env-controlled levels.

v1.1 — Replaces scattered print() with proper structured logging.
"""

import logging
import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter.

    Output: {"ts": "...", "level": "INFO", "module": "state", "msg": "...", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "ctxh_extra"):
            log_entry.update(record.ctxh_extra)
        return json.dumps(log_entry, sort_keys=True)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter with color support."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def __init__(self, color: bool = True):
        super().__init__()
        self.color = color and hasattr(os, "isatty") and os.isatty(2)

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        level = record.levelname
        if self.color:
            color = self.COLORS.get(level, "")
            level_str = f"{color}{level:<8}{self.RESET}"
        else:
            level_str = f"{level:<8}"
        extra = ""
        if hasattr(record, "ctxh_extra"):
            extra = " " + json.dumps(record.ctxh_extra)
        return f"{ts} {level_str} [{record.module}] {record.getMessage()}{extra}"


_configured_loggers: set = set()


def get_logger(name: str = "ctxh",
               level: Optional[str] = None) -> logging.Logger:
    """Get a configured logger for CE-Harness.

    Level controlled by CTXH_LOG_LEVEL env var (default: WARNING).
    Format controlled by CTXH_LOG_FORMAT env var ('json' or 'text', default: 'json').
    """
    logger = logging.getLogger(name)
    if name in _configured_loggers:
        return logger

    log_level = level or os.environ.get("CTXH_LOG_LEVEL", "WARNING")
    log_format = os.environ.get("CTXH_LOG_FORMAT", "json")

    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, log_level.upper(), logging.WARNING))
    _configured_loggers.add(name)
    return logger


def log_event(logger: logging.Logger, level: str, msg: str,
              **kwargs: Any) -> None:
    """Log an event with extra structured fields."""
    record = logger.makeRecord(
        name=logger.name,
        level=getattr(logging, level.upper(), logging.INFO),
        fn="", lno=0, msg=msg, args=(), exc_info=None,
    )
    record.ctxh_extra = kwargs  # type: ignore
    logger.handle(record)
