"""Jarvis Logging Subsystem with Automatic Secret Redaction.

Ensures that API keys, bearer tokens, passwords, and private tokens are redacted
from all log records before output.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional


# Regex patterns matching common secret formats
SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_\-]{20,})", re.IGNORECASE),
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?)([^'\"\s\n]{8,})(['\"]?)", re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """Redact sensitive credentials from a text string."""
    if not isinstance(text, str):
        return text

    redacted = text
    for pattern in SECRET_PATTERNS:
        if "Bearer" in pattern.pattern:
            redacted = pattern.sub(r"\1[REDACTED_BEARER]", redacted)
        elif "sk-" in pattern.pattern:
            redacted = pattern.sub(r"[REDACTED_KEY]", redacted)
        elif "AIza" in pattern.pattern:
            redacted = pattern.sub(r"[REDACTED_GEMINI_KEY]", redacted)
        else:
            redacted = pattern.sub(r"\1[REDACTED]\3", redacted)
    return redacted


class SecretRedactingFormatter(logging.Formatter):
    """Logging formatter that intercepts and redacts sensitive information."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_secrets(original)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_to_file: bool = True
) -> logging.Logger:
    """Configure structured logging with secret redaction."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger = logging.getLogger("jarvis")
    logger.setLevel(numeric_level)
    logger.propagate = False

    # Avoid duplicate handlers if reconfigured
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = SecretRedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if requested and directory provided)
    if log_to_file and log_dir:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_path = log_dir / "jarvis.log"
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as exc:
            # Fall back gracefully to console logging if file logging is restricted
            pass

    return logger


# Default logger instance
logger = logging.getLogger("jarvis")
