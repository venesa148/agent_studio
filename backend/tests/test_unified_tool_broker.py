import pytest
from httpx import AsyncClient, Response
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.executors.http_executor import GenericHttpExecutor
from app.services.executors.native_executor import NativePythonExecutor
from app.services.tool_registry import ToolRegistryService
from app.models.tool import ToolModel


@pytest.mark.asyncio
async def test_native_calculator():
    """Menguji eksekutor kalkulator native Python."""
    res_add = await NativePythonExecutor.execute("calculator", {"expression": "25 * 4 + 10"})
    assert res_add["status"] == "ok"
    assert res_add["result"] == 110

    res_div = await NativePythonExecutor.execute("calculator", {"expression": "100 / 4"})
    assert res_div["status"] == "ok"
    assert res_div["result"] == 25.0

    # Uji ekspresi tidak aman / error sintaks
    res_err = await NativePythonExecutor.execute("calculator", {"expression": "__import__('os')"})
    assert res_err["status"] == "error"


@pytest.mark.asyncio
async def test_native_triage_clinical():
    """Menguji eksekutor triase klinis native Python."""
    # Skenario 1: Red Flag Emergency
    res_emergency = await NativePythonExecutor.execute("classify_complaint", {"complaint": "Pasien mengalami nyeri dada hebat dan sesak nafas"})
    assert res_emergency["status"] == "ok"
    assert res_emergency["triage_class"] == "EMERGENCY"
    assert res_emergency["red_flag"] is True
    assert "IGD" in res_emergency["candidate_service"][0]

    # Skenario 2: Stabil / Rujukan Reguler
    res_stable = await NativePythonExecutor.execute("classify_complaint", {"complaint": "Mata kanan terasa buram dan agak silau"})
    assert res_stable["status"] == "ok"
    assert res_stable["triage_class"] == "NEED_FURTHER_CARE"
    assert res_stable["red_flag"] is False
    assert "Poli Mata" in res_stable["candidate_service"]


@pytest.mark.asyncio
async def test_generic_http_executor_get_and_post():
    """Menguji eksekusi dinamis GenericHttpExecutor dengan mocking httpx."""
    # Uji 1: GET dengan placeholder URL dan query params
    impl_get = {
        "type": "http",
        "method": "GET",
        "url": "https://api.example.com/v1/items/{item_id}",
    }
    params_get = {"item_id": "ABC-123", "include_details": "true"}

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_resp = AsyncMock(spec=Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "ABC-123", "title": "Kopi Arabika", "stock": 50}
        mock_req.return_value = mock_resp

        result = await GenericHttpExecutor.execute(impl_get, params_get)
        assert result["id"] == "ABC-123"
        assert result["_endpoint"] == "https://api.example.com/v1/items/ABC-123"
        assert "_source" in result

        # Verifikasi call kwargs
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == "GET"
        assert args[1] == "https://api.example.com/v1/items/ABC-123"
        assert kwargs["params"] == {"include_details": "true"}

    # Uji 2: POST dengan JSON body dinamis
    impl_post = {
        "type": "http",
        "method": "POST",
        "url": "https://api.example.com/v1/orders",
    }
    params_post = {"customer": "Budi", "items": ["Kopi"], "total": 25000}

    with patch("httpx.AsyncClient.request") as mock_req:
        mock_resp = AsyncMock(spec=Response)
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"order_id": "ORD-999", "status": "confirmed"}
        mock_req.return_value = mock_resp

        result = await GenericHttpExecutor.execute(impl_post, params_post)
        assert result["order_id"] == "ORD-999"
        mock_req.assert_called_once()
        args, kwargs = mock_req.call_args
        assert args[0] == "POST"
        assert kwargs["json"] == params_post


@pytest.mark.asyncio
async def test_tool_registry_service_routing(async_client: AsyncClient):
    """Menguji eksekusi via ToolRegistryService Unified Broker."""
    from tests.conftest import TestingSessionLocal
    import uuid

    async with TestingSessionLocal() as session:
        # Buat tool dinamis deklaratif baru buatan Builder
        custom_tool = ToolModel(
            id=str(uuid.uuid4()),
            name="test_custom_booking_api",
            description="Tool dinamis buatan builder untuk booking meja",
            source_type="builtin",
            is_active=True,
            status="published",
            effect="write",
            implementation={
                "type": "http",
                "method": "POST",
                "url": "https://kafe.internal/api/reserve",
            }
        )
        session.add(custom_tool)
        await session.commit()

        # Eksekusi via ToolRegistryService
        with patch("httpx.AsyncClient.request") as mock_req:
            mock_resp = AsyncMock(spec=Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"booking_code": "KAFE-001", "status": "reserved"}
            mock_req.return_value = mock_resp

            exec_res = await ToolRegistryService.execute_tool(
                session, "test_custom_booking_api", {"customer_name": "Ani", "pax": 2}
            )
            assert exec_res["name"] == "test_custom_booking_api"
            assert exec_res["result"]["booking_code"] == "KAFE-001"
            assert exec_res["duration_ms"] >= 0

        # Eksekusi native tool via ToolRegistryService
        calc_res = await ToolRegistryService.execute_tool(
            session, "calculator", {"expression": "50 * 2"}
        )
        assert calc_res["result"]["result"] == 100
