import pytest
from httpx import AsyncClient, Response
from unittest.mock import patch, AsyncMock, MagicMock
from tests.conftest import TestingSessionLocal
from app.models.agent import AgentSpecModel
from app.models.evaluation import EvaluationModel
from app.services.mcp_client import MCPClientService, MCPProtocolError
from app.services.evaluator_service import EvaluatorService


# ======================================================================
# 1. MCP FORMAL PROTOCOL JSON-RPC 2.0 TESTS
# ======================================================================

@pytest.mark.asyncio
async def test_mcp_client_initialize_handshake_success():
    """Menguji formal handshake JSON-RPC 2.0 'initialize' MCP."""
    mock_response = Response(
        status_code=200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "serverInfo": {
                    "name": "mock-mcp-inventory-server",
                    "version": "1.2.0"
                }
            }
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        res = await MCPClientService.initialize("http://mock-mcp-server:8000")
        assert res["status"] == "connected"
        assert res["protocol_version"] == "2024-11-05"
        assert res["server_info"]["name"] == "mock-mcp-inventory-server"
        assert res["capabilities"]["tools"]["listChanged"] is True


@pytest.mark.asyncio
async def test_mcp_client_initialize_handshake_error():
    """Menguji kegagalan handshake jika server menolak protokol."""
    mock_response = Response(
        status_code=200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32600,
                "message": "Unsupported protocol version"
            }
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        with pytest.raises(RuntimeError) as exc_info:
            await MCPClientService.initialize("http://mock-mcp-server:8000")
        assert "Unsupported protocol version" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_client_discover_tools_normalization():
    """Menguji normalisasi tools/list MCP standar."""
    mock_response = Response(
        status_code=200,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "query_inventory_db",
                        "description": "Ambil data inventaris stok produk dari database toko",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"sku": {"type": "string"}},
                            "required": ["sku"]
                        },
                        "effect": "read"
                    }
                ]
            }
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        tools = await MCPClientService.discover_tools("http://mock-mcp-server:8000")
        assert len(tools) == 1
        t = tools[0]
        assert t["name"] == "query_inventory_db"
        assert t["source_type"] == "mcp"
        assert "sku" in t["input_schema"]["properties"]


@pytest.mark.asyncio
async def test_mcp_client_call_tool_multipart_content():
    """Menguji pemanggilan tools/call dengan content block multi-part standar MCP."""
    mock_response = Response(
        status_code=200,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "result": {
                "content": [
                    {"type": "text", "text": "Stok produk SKU-889 tersedia 45 unit di gudang utama."}
                ],
                "data": {"sku": "SKU-889", "available": 45}
            }
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        call_res = await MCPClientService.call_tool(
            server_url="http://mock-mcp-server:8000",
            tool_name="query_inventory_db",
            arguments={"sku": "SKU-889"}
        )
        assert call_res["status"] == "ok"
        assert "SKU-889 tersedia 45 unit" in call_res["output"]
        assert call_res["data"]["available"] == 45


@pytest.mark.asyncio
async def test_mcp_client_call_tool_error_mapping():
    """Menguji mapping error JSON-RPC ketika pemanggilan tool gagal di server MCP."""
    mock_response = Response(
        status_code=200,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "error": {
                "code": -32602,
                "message": "Invalid params: 'sku' format tidak valid"
            }
        }
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        call_res = await MCPClientService.call_tool(
            server_url="http://mock-mcp-server:8000",
            tool_name="query_inventory_db",
            arguments={"sku": ""}
        )
        assert call_res["status"] == "error"
        assert call_res["error_type"] == "MCP_PROTOCOL_ERROR"
        assert call_res["code"] == -32602
        assert "Invalid params" in call_res["message"]


# ======================================================================
# 2. SEMI-AUTOMATED HUMAN-IN-THE-LOOP (HITL) FLYWHEEL TESTS
# ======================================================================

@pytest.mark.asyncio
async def test_hitl_evaluator_generates_prompt_patch_on_low_score():
    """
    Evaluator Flywheel:
    Saat evaluasi menghasilkan skor rendah / FAILED, sistem secara otomatis
    membuat usulan perbaikan instruksi (suggested_patch) untuk ditinjau manusia.
    """
    async with TestingSessionLocal() as db:
        # Buat agen uji
        agent = AgentSpecModel(
            id="agent_hitl_test_01",
            name="E-Commerce Customer Care",
            description="Agent bantuan pesanan e-commerce",
            instructions="Bantu pengguna melacak pesanan belanja mereka.",
            model="gpt-4o-mini",
            status="published",
            tools=["track_shipping"]
        )
        db.add(agent)

        # Buat test case evaluasi yang gagal
        eval_item = EvaluationModel(
            id="eval_hitl_test_01",
            agent="E-Commerce Customer Care",
            input="Saya ingin mengajukan pengembalian dana barang rusak",
            expected="refund_request_tool",
            status="idle"
        )
        db.add(eval_item)
        await db.commit()

        # Jalankan evaluasi dengan mock test_agent untuk isolasi unit test yang deterministik
        mock_agent_resp = MagicMock()
        mock_agent_resp.response = "Halo, saya hanya bisa melacak nomor resi paket pengiriman."
        mock_agent_resp.trace_steps = []
        with patch("app.services.agent_service.AgentService.test_agent", new_callable=AsyncMock) as mock_test_agent:
            mock_test_agent.return_value = mock_agent_resp
            evaluated = await EvaluatorService.run_single_evaluation(db, eval_item.id)

        assert evaluated is not None
        assert evaluated.status == "failed"
        assert evaluated.details is not None

        # Verifikasi usulan patch instruksi
        patch_data = evaluated.details.get("suggested_patch")
        assert patch_data is not None
        assert patch_data["status"] == "pending_review"
        assert "refund_request_tool" in patch_data["suggested_instruction"]
        assert "pengembalian dana" in patch_data["suggested_instruction"]


@pytest.mark.asyncio
async def test_hitl_human_approval_applies_patch_to_agent_spec(async_client: AsyncClient):
    """
    Human-in-the-Loop Approval:
    Pengembang menyetujui usulan perbaikan melalui API /apply-patch.
    Instruksi agen diperbarui secara terstruktur tanpa prompt drift liar.
    """
    async with TestingSessionLocal() as db:
        agent = AgentSpecModel(
            id="agent_hitl_approval_test",
            name="Helpdesk Tech Agent",
            description="Agent helpdesk teknis",
            instructions="Instruksi awal agen tech support.",
            model="gpt-4o-mini",
            status="published",
            tools=[]
        )
        db.add(agent)

        eval_item = EvaluationModel(
            id="eval_hitl_approval_test",
            agent="Helpdesk Tech Agent",
            input="Koneksi VPN saya terputus",
            expected="check_vpn_gateway",
            status="failed",
            score=45,
            details={
                "suggested_patch": {
                    "patch_id": "patch_vpn_01",
                    "scenario_input": "Koneksi VPN saya terputus",
                    "expected_outcome": "check_vpn_gateway",
                    "suggested_instruction": "### Penanganan VPN:\nBila pengguna bermasalah VPN, arahkan ke gateway VPN internal.",
                    "status": "pending_review"
                }
            }
        )
        db.add(eval_item)
        await db.commit()

    # User klik tombol 'Terapkan ke Draf' -> POST /api/v1/agent/{agent_id}/apply-patch
    response = await async_client.post(
        "/api/v1/agent/agent_hitl_approval_test/apply-patch",
        json={"eval_id": "eval_hitl_approval_test"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "### Penanganan VPN:" in data["instructions"]
    assert "Instruksi awal agen tech support." in data["instructions"]

    # Verifikasi status di evaluasi terupdate menjadi 'applied'
    async with TestingSessionLocal() as db:
        from sqlalchemy import select
        res = await db.execute(select(EvaluationModel).where(EvaluationModel.id == "eval_hitl_approval_test"))
        updated_eval = res.scalars().first()
        assert updated_eval.details["suggested_patch"]["status"] == "applied"
        assert "applied_at" in updated_eval.details["suggested_patch"]
