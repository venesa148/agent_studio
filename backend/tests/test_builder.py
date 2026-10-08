import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_builder_chat_bpjs(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/builder/chat",
        json={"prompt": "Buatkan CS BPJS yang bisa cari RS dan rujukan"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "BPJS" in data["spec"]["name"] or "Asisten" in data["spec"]["name"] or "CS" in data["spec"]["name"]
    assert len(data["spec"]["tools"]) >= 1 or len(data["spec"]["instructions"]) > 10

@pytest.mark.asyncio
async def test_builder_chat_custom(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/builder/chat",
        json={"prompt": "Buat agent penulisan artikel tech"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["spec"]["name"]) > 0
    assert data["spec"]["instructions"] is not None

@pytest.mark.asyncio
async def test_builder_save_persists_spec(async_client: AsyncClient):
    # Save a new custom agent spec
    save_res = await async_client.post(
        "/api/v1/builder/save",
        json={
            "name": "Finance & Research Agent",
            "description": "Agent riset pasar dan kalkulasi keuangan",
            "instructions": "Bantu pengguna melakukan riset web dan menghitung perkiraan.",
            "model": "gpt-4o-mini",
            "tools": ["calculator", "search_web"],
            "mcp_servers": [],
            "harness": "default-safe-v1",
            "status": "active"
        }
    )
    assert save_res.status_code == 200
    saved = save_res.json()
    assert saved["id"] is not None
    assert saved["name"] == "Finance & Research Agent"
    assert "calculator" in saved["tools"]
    assert "search_web" in saved["tools"]

    # Verify agent is retrieved from /api/v1/agent
    get_res = await async_client.get(f"/api/v1/agent/{saved['id']}")
    assert get_res.status_code == 200
    agent_data = get_res.json()
    assert agent_data["name"] == "Finance & Research Agent"

