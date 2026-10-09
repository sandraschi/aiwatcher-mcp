import pytest

from aiwatcher_mcp._version import __version__
from aiwatcher_mcp.server import mcp


@pytest.mark.asyncio
async def test_server_initialization():
    """Test that the MCP server initializes correctly."""
    assert mcp.name == "aiwatcher-mcp"
    assert mcp.version == __version__

    # Verify tools are registered via list_tools
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "poll_feeds" in tool_names
    assert "get_top_items" in tool_names
    assert "generate_digest" in tool_names


@pytest.mark.asyncio
async def test_new_tools_registered():
    tools = await mcp.list_tools()
    names = [t.name for t in tools]
    for expected in ("hn_top", "hn_search", "hn_distill_thread", "get_digest"):
        assert expected in names


@pytest.mark.asyncio
async def test_dangerous_tools_need_confirm(fresh_db):
    from aiwatcher_mcp.server import expire_old_items, import_opml, send_digest_now

    class _Ctx:
        async def info(self, *a, **k):
            return None

    ctx = _Ctx()
    no_mail = await send_digest_now(ctx)
    assert no_mail["sent"] is False and no_mail["needs_confirm"] is True
    no_expire = await expire_old_items(ctx)
    assert no_expire["deleted"] == 0 and no_expire["needs_confirm"] is True
    no_opml = await import_opml(ctx, "<opml><body></body></opml>")
    assert no_opml["imported"] == 0 and no_opml["needs_confirm"] is True


@pytest.mark.asyncio
async def test_server_resources():
    """Test that resources are correctly registered."""
    resources = await mcp.list_resources()
    resource_uris = [str(r.uri) for r in resources]
    assert "aiwatcher://feeds/list" in resource_uris
    assert "aiwatcher://stats" in resource_uris
