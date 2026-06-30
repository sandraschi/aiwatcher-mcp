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
async def test_server_resources():
    """Test that resources are correctly registered."""
    resources = await mcp.list_resources()
    resource_uris = [str(r.uri) for r in resources]
    assert "aiwatcher://feeds/list" in resource_uris
    assert "aiwatcher://stats" in resource_uris
