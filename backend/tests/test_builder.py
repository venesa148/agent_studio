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
    assert "BPJS Customer Service Agent" in data["spec"]["name"]
    assert "search_hospital" in data["spec"]["tools"]

@pytest.mark.asyncio
async def test_builder_chat_custom(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/builder/chat",
        json={"prompt": "Buat agent penulisan artikel tech"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "Custom AI Assistant" in data["spec"]["name"]
