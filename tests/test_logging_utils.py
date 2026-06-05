"""Tests for logging_utils.py — UIHandler ring buffer."""

from __future__ import annotations

import logging

from aiwatcher_mcp.logging_utils import UIHandler, get_logs, log_buffer


def test_ui_handler_appends_to_buffer():
    log_buffer.clear()
    handler = UIHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello fleet",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    logs = get_logs()
    assert len(logs) >= 1
    assert logs[-1]["message"] == "hello fleet"
    assert logs[-1]["level"] == "INFO"
