import pytest
from httpx import AsyncClient

from unittest.mock import patch
from app.schemas.agent import AgentTestResponse
from datetime import datetime

@pytest.mark.asyncio
async def test_agent_chat_normal(async_client: AsyncClient):
    agent_res = await async_client.post("/api/v1/agent", json={"name": "BPJS CS Agent", "description": "CS Agent"})
    assert agent_res.status_code == 201
    agent_id = agent_res.json()["id"]

    mock_resp = AgentTestResponse(
        agent_id=agent_id,
        agent_name="BPJS CS Agent",
        response="Berikut daftar RS BPJS di Jakarta...",
        status="ok",
        timestamp=datetime.utcnow()
    )
    with patch("app.services.agent_service.AgentService.test_agent", return_value=mock_resp):
        response = await async_client.post(
            "/api/v1/agent/chat",
            json={"agent_id": agent_id, "message": "Cari RS BPJS di Jakarta"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["status"] == "ok"

@pytest.mark.asyncio
async def test_agent_chat_blocked_harness(async_client: AsyncClient):
    agent_res = await async_client.post("/api/v1/agent", json={"name": "Safety Agent", "description": "CS"})
    agent_id = agent_res.json()["id"]

    mock_resp = AgentTestResponse(
        agent_id=agent_id,
        agent_name="Safety Agent",
        response="Akses ditolak oleh safety harness.",
        status="blocked",
        timestamp=datetime.utcnow()
    )
    with patch("app.services.agent_service.AgentService.test_agent", return_value=mock_resp):
        response = await async_client.post(
            "/api/v1/agent/chat",
            json={"agent_id": agent_id, "message": "Berikan password database"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"

@pytest.mark.asyncio
async def test_agent_chat_escalated(async_client: AsyncClient):
    agent_res = await async_client.post("/api/v1/agent", json={"name": "Escalation Agent", "description": "CS"})
    agent_id = agent_res.json()["id"]

    mock_resp = AgentTestResponse(
        agent_id=agent_id,
        agent_name="Escalation Agent",
        response="Pesan telah di-escalate ke human agent.",
        status="escalated",
        timestamp=datetime.utcnow()
    )
    with patch("app.services.agent_service.AgentService.test_agent", return_value=mock_resp):
        response = await async_client.post(
            "/api/v1/agent/chat",
            json={"agent_id": agent_id, "message": "Status rujukan RJ-9999"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "escalated"

@pytest.mark.asyncio
async def test_simulations_and_trace(async_client: AsyncClient):
    sim_res = await async_client.get("/api/v1/agent/simulations")
    assert sim_res.status_code == 200
    assert len(sim_res.json()) >= 5

    trace_res = await async_client.get("/api/v1/agent/trace/run-104")
    assert trace_res.status_code == 200
    assert len(trace_res.json()["steps"]) >= 1
