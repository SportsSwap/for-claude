"""Every log record is redacted before it reaches a file."""

from __future__ import annotations

import logging
from pathlib import Path

from .redact import RedactionError, redact_text

_HANDLER_MARK = "_tra_handler"


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
        except RedactionError:
            record.msg = "[log message dropped: redaction failed]"
        record.args = None
        return True


def configure_logging(log_path: Path, level: int = logging.INFO) -> None:
    """Send the ``tra`` logger to ``log_path`` through the redacting filter. Safe to call twice."""
    logger = logging.getLogger("tra")
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            logger.removeHandler(handler)
            handler.close()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactingFilter())
    setattr(handler, _HANDLER_MARK, True)
    logger.addHandler(handler)
    logger.setLevel(level)
