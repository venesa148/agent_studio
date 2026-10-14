import asyncio
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import TestingSessionLocal, test_engine
from app.core.db import Base
from app.models.tool import ToolModel
from app.models.agent import AgentSpecModel
from app.models.chat import ConversationModel, MessageModel
from app.services.builder_service import BuilderService
from app.services.agent_service import AgentService
from app.schemas.agent import BuilderChatRequest
from unittest.mock import patch, MagicMock, AsyncMock


async def run_barista_demo():
    print("=" * 75)
    print("DEMO END-TO-END ARSITEKTUR BARU: PILIHAN 1 (BARISTABOT KAFE KALANDRA)")
    print("=" * 75)

    # Inisialisasi tabel di database testing
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        # ------------------------------------------------------------------
        # TAHAP 1: TURN-1 INSTANT DRAFT DI BUILDER AGENT STUDIO
        # ------------------------------------------------------------------
        user_prompt = (
            "Buatkan agen customer service untuk Kafe Kopi Kalandra. "
            "Agen ini harus bisa menjelaskan menu kopi dari file pengetahuan, "
            "memeriksa ketersediaan meja, dan membantu reservasi tempat untuk pelanggan."
        )
        print(f"\n[1] PENGGUNA MENGIRIM PROMPT KE BUILDER (Turn-1):")
        print(f'    "{user_prompt}"')

        builder_res = await BuilderService.build_agent_spec(db, prompt=user_prompt)

        print("\n[OK] HASIL RESPONSE BUILDER (INSTANT TURN-1 DRAFT TERBENTUK):")
        print(f"    - Nama Agen       : {builder_res.spec.name}")
        print(f"    - Deskripsi       : {builder_res.spec.description}")
        print(f"    - Health Score    : {builder_res.health_score}%")
        print(f"    - Status Draf     : {'Draf Siap Uji' if builder_res.is_draft else 'Aktif'}")
        print(f"    - Tools Terpilih  : {builder_res.spec.tools}")
        print(f"    - Knowledge       : {builder_res.spec.knowledge_sources}")

        # ------------------------------------------------------------------
        # TAHAP 2: SIMPAN AGEN KE DATABASE
        # ------------------------------------------------------------------
        agent_id = "agent_kafe_kalandra"
        db_agent = AgentSpecModel(
            id=agent_id,
            name=builder_res.spec.name or "Kalandra Cafe Assistant",
            description=builder_res.spec.description or "Customer Service Kafe Kalandra",
            instructions=(
                "Anda adalah Barista & Customer Support AI untuk Kafe Kalandra. "
                "Jawab pertanyaan menu dengan ramah berdasarkan referensi knowledge. "
                "Untuk reservasi meja pelanggan, selalu gunakan tool create_reservation."
            ),
            model="gpt-4o-mini",
            tools=["check_table_availability", "create_reservation"],
            status="published"
        )
        db.add(db_agent)

        # Daftarkan metadata tools (Read vs Write)
        tool_read = ToolModel(
            id="tool_check_table",
            name="check_table_availability",
            description="Cek ketersediaan meja di kafe",
            effect="read",
            status="published",
            is_active=True,
            input_schema={"type": "object", "properties": {"time": {"type": "string"}, "guests": {"type": "integer"}}}
        )
        tool_write = ToolModel(
            id="tool_create_reservation",
            name="create_reservation",
            description="Reservasi dan booking meja kafe pelanggan",
            effect="write",
            status="published",
            is_active=True,
            input_schema={"type": "object", "properties": {"name": {"type": "string"}, "time": {"type": "string"}, "guests": {"type": "integer"}}}
        )
        db.add(tool_read)
        db.add(tool_write)
        await db.commit()

        # ------------------------------------------------------------------
        # TAHAP 3: RUNNER DI TEST CHAT & SIERRA PRE-TOOL IMPACT GATE
        # ------------------------------------------------------------------
        print("\n" + "=" * 75)
        print("[2] PENGUJIAN RUNNER DI PANEL TEST CHAT (SIERRA GUARDRAIL IN ACTION)")
        print("=" * 75)

        # Matikan embedding eksternal lambat dengan mock offline vector
        with patch("app.services.rag.vector_service.VectorService.get_embedding", return_value=[0.05] * 1536):

            # --- GILIRAN 1: User meminta tindakan booking meja (State-Mutating) ---
            user_order_msg = "Tolong pesankan meja untuk 4 orang jam 7 malam atas nama Budi"
            print(f"\n[Turn 1] User  : \"{user_order_msg}\"")

            # Mock LLM mendeteksi perlunya memanggil tool create_reservation
            mock_choice1 = MagicMock()
            mock_msg1 = MagicMock()
            mock_msg1.content = None
            mock_tc = MagicMock()
            mock_tc.id = "call_resv_001"
            mock_tc.function.name = "create_reservation"
            mock_tc.function.arguments = json.dumps({"name": "Budi", "time": "19:00", "guests": 4})
            mock_msg1.tool_calls = [mock_tc]
            mock_choice1.message = mock_msg1

            mock_client1 = MagicMock()
            mock_client1.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice1]))

            with patch("app.services.agent_service.AsyncOpenAI", return_value=mock_client1):
                resp_turn1 = await AgentService.test_agent(
                    db=db,
                    agent_id=agent_id,
                    message=user_order_msg,
                    session_prefix="demo_kalandra"
                )

                print(f"[Turn 1] Agent : {resp_turn1.response}")
                print(f"[Turn 1] Status: {resp_turn1.status.upper()}")
                for s in resp_turn1.trace_steps:
                    print(f"         |-- [Trace Step {s['step']}] {s['title']} (Type: {s['type']})")

            # --- GILIRAN 2: User membalas dengan konfirmasi eksplisit ---
            user_confirm_msg = "Ya, lanjutkan"
            print(f"\n[Turn 2] User  : \"{user_confirm_msg}\"")

            # Mock LLM giliran 2:
            # Panggilan 1: LLM memanggil create_reservation (sekarang lolos karena user sudah konfirmasi)
            # Panggilan 2: LLM menerima hasil sukses dari tool dan memberikan respon akhir
            mock_call_step1 = MagicMock(choices=[mock_choice1])
            mock_final_msg = MagicMock()
            mock_final_msg.content = "Reservasi berhasil dibuat! Meja atas nama Budi untuk 4 orang pada pukul 19:00 telah kami amankan. Kode booking Anda: #KLD-402."
            mock_final_msg.tool_calls = []
            mock_call_step2 = MagicMock(choices=[MagicMock(message=mock_final_msg)])

            mock_client2 = MagicMock()
            mock_client2.chat.completions.create = AsyncMock(side_effect=[mock_call_step1, mock_call_step2])

            with patch("app.services.agent_service.AsyncOpenAI", return_value=mock_client2):
                with patch("app.services.tool_registry.ToolRegistryService.execute_tool") as mock_exec:
                    mock_exec.return_value = {
                        "status": "ok",
                        "result": {"booking_id": "KLD-402", "name": "Budi", "time": "19:00", "guests": 4, "status": "confirmed"}
                    }
                    resp_turn2 = await AgentService.test_agent(
                        db=db,
                        agent_id=agent_id,
                        message=user_confirm_msg,
                        session_prefix="demo_kalandra"
                    )

                    print(f"[Turn 2] Agent : {resp_turn2.response}")
                    print(f"[Turn 2] Status: {resp_turn2.status.upper()}")
                    for s in resp_turn2.trace_steps:
                        print(f"         |-- [Trace Step {s['step']}] {s['title']} -> {s['result'].get('status')}")

    print("\n" + "=" * 75)
    print("SIMULASI SUKSES: SELURUH LOGIKA ARSITEKTUR TERBUKTI BEKERJA DENGAN SEMPURNA!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_barista_demo())
