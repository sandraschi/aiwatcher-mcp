import logging
from collections import deque
from datetime import datetime
from typing import Any

# Circular buffer for the last 500 log entries
log_buffer = deque(maxlen=500)


class UIHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "name": record.name,
                "message": msg,
                "exc_info": self.formatException(record.exc_info) if record.exc_info else None,  # pyright: ignore[reportAttributeAccessIssue]  # logging.Handler.formatException
            }
            log_buffer.append(log_entry)
        except Exception:
            self.handleError(record)


def get_logs() -> list[dict[str, Any]]:
    return list(log_buffer)


def setup_ui_logging(level: int = logging.INFO) -> None:
    handler = UIHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(level)

    # Attach to root logger
    logging.getLogger().addHandler(handler)
