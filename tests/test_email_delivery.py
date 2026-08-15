"""Tests for email_delivery.py — mocked email-mcp and SMTP."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
async def test_send_digest_disabled(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("EMAIL_ENABLED", "false")
    cfg_mod._settings = None

    from aiwatcher_mcp.email_delivery import send_digest

    ok = await send_digest({"subject": "Hi", "html_body": "<p>x</p>", "text_body": "x"})
    assert ok is False


@pytest.mark.asyncio
async def test_send_digest_via_email_mcp(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_MCP_URL", "http://email.test")
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@example.com")
    cfg_mod._settings = None

    with respx.mock(assert_all_called=False) as mock:
        mock.post("http://email.test/api/send").mock(return_value=Response(200, json={"ok": True}))
        from aiwatcher_mcp.email_delivery import send_digest

        ok = await send_digest(
            {"subject": "Digest", "html_body": "<p>Hi</p>", "text_body": "Hi", "item_count": 1}
        )

    assert ok is True


@pytest.mark.asyncio
async def test_send_digest_smtp_fallback(monkeypatch):
    import aiwatcher_mcp.config as cfg_mod

    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_MCP_URL", "")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("EMAIL_RECIPIENTS", "a@example.com")
    cfg_mod._settings = None

    with patch(
        "aiwatcher_mcp.email_delivery._send_via_smtp",
        new_callable=AsyncMock,
        return_value=True,
    ):
        from aiwatcher_mcp.email_delivery import send_digest

        ok = await send_digest({"subject": "Digest", "html_body": "<p>Hi</p>", "text_body": "Hi"})

    assert ok is True
