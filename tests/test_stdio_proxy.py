"""SOTA §2.3 stdio probe helpers."""

from unittest.mock import MagicMock, patch

from aiwatcher_mcp.server import _http_daemon_reachable, _resolve_http_proxy_mcp_url


def test_resolve_http_proxy_mcp_url_default():
    url = _resolve_http_proxy_mcp_url()
    assert url.endswith("/mcp")
    assert "10946" in url


def test_http_daemon_reachable_true_on_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    with patch("httpx.post", return_value=mock_response):
        assert _http_daemon_reachable("http://127.0.0.1:10946/mcp") is True


def test_http_daemon_reachable_false_on_error():
    with patch("httpx.post", side_effect=OSError("connection refused")):
        assert _http_daemon_reachable("http://127.0.0.1:10946/mcp") is False
