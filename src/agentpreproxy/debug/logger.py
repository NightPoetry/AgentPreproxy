from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


_FORMAT = "[%(asctime)s] [%(name)s] [%(levelname)s] [%(request_id)s] %(message)s"
_initialized = False


def setup_logging(level: str = "INFO") -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger("agentpreproxy")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    root.propagate = False


def get_logger(module: str) -> logging.Logger:
    return logging.getLogger(f"agentpreproxy.{module}")
