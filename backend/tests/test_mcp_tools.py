import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"

@pytest.mark.asyncio
async def test_register_and_list_tools(async_client: AsyncClient):
    # Register custom tool
    register_res = await async_client.post(
        "/api/v1/tools",
        json={
            "name": "custom_search",
            "description": "Custom test tool",
            "source_type": "builtin"
        }
    )
    assert register_res.status_code == 201
    assert register_res.json()["name"] == "custom_search"

    # List tools
    list_res = await async_client.get("/api/v1/tools")
    assert list_res.status_code == 200
    tools = list_res.json()
    assert len(tools) >= 1
    assert any(t["name"] == "custom_search" for t in tools)

from unittest.mock import patch

@pytest.mark.asyncio
async def test_register_mcp_server(async_client: AsyncClient):
    with patch("app.services.mcp_client.MCPClientService.discover_tools", return_value=[{"name": "mcp_tool_1", "description": "Mocked tool", "inputSchema": {}}]):
        response = await async_client.post(
            "/api/v1/mcp",
            json={
                "name": "Test MCP Server",
                "url": "http://localhost:8001/sse"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test MCP Server"
        assert data["status"] == "connected"

@pytest.mark.asyncio
async def test_local_mcp_server_tools_list(async_client: AsyncClient):
    # Test JSON-RPC 2.0 tools/list on /api/v1/mcp/local-server
    response = await async_client.post(
        "/api/v1/mcp/local-server",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
    )
    assert response.status_code == 200
    res = response.json()
    assert "result" in res
    tools = res["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "system_time" in tool_names
    assert "system_diagnostics" in tool_names
    assert "currency_converter" in tool_names

@pytest.mark.asyncio
async def test_local_mcp_server_tools_call_currency(async_client: AsyncClient):
    # Test JSON-RPC 2.0 tools/call on /api/v1/mcp/local-server
    response = await async_client.post(
        "/api/v1/mcp/local-server",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "currency_converter",
                "arguments": {
                    "amount": 100,
                    "from_currency": "USD",
                    "to_currency": "IDR"
                }
            }
        }
    )
    assert response.status_code == 200
    res = response.json()
    assert "result" in res
    assert "content" in res["result"]
    assert "data" in res["result"]
    assert res["result"]["data"]["result"] > 0
    assert "USD" in res["result"]["content"][0]["text"]
