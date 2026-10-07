"""
Test Script: End-to-End Validation & Deployment Flow
=====================================================
1. Validasi integritas agent.yaml (skema & graph nodes).
2. Simulasi eksekusi engine runtime (run_step).
3. Verifikasi response triase BPJS dan output state-machine.
"""

import sys
import asyncio
from pathlib import Path

# Setup Windows async loop policy jika berjalan di Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from agent_runtime_server import engine, CONFIG_PATH
from app.api.v1.deployment import validate_agent_yaml
import yaml

async def test_full_pipeline():
    print("==================================================")
    print(" [*] TESTING AGENT RUNTIME & DEPLOYMENT FLOW")
    print("==================================================")

    # 1. Test Validasi agent.yaml
    print("[1/3] Memeriksa file agent.yaml...")
    assert CONFIG_PATH.exists(), f"File {CONFIG_PATH} tidak ditemukan!"
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    validate_agent_yaml(spec)
    print(f"  [OK] Validasi Skema & Graph LOLOS! (Agent ID: {spec['agent_id']}, Nodes: {len(spec['flow']['nodes'])})")

    # 2. Test Inisialisasi Runtime Engine
    print("[2/3] Memeriksa inisialisasi AgentRuntimeEngine...")
    assert engine.agent_id == spec["agent_id"]
    assert len(engine.nodes_by_id) == len(spec["flow"]["nodes"])
    print(f"  [OK] Runtime Engine siap dengan entry_node: '{engine.entry_node}'")

    # 3. Test Invoke Percakapan Pasien
    print("[3/3] Menjalankan test invoke (pesan pasien)...")
    sample_message = "Kepala saya pusing berputar sejak kemarin pagi."
    session_id = "test-session-pasien-001"
    
    result = await engine.run_step(session_id, sample_message)
    print(f"  [OK] Response Diterima dari Agent:")
    print(f"    - Agent Name   : {engine.name}")
    print(f"    - Current Node : {result.current_node}")
    print(f"    - Status       : {result.status}")
    print(f"    - Turn Count   : {result.turn_count}")
    print(f"    - Pesan Balasan:\n\"{result.response}\"")

    assert result.status in ["in_progress", "completed"]
    assert len(result.response) > 10
    print("\n==================================================")
    print(" [SUCCESS] ALL TESTS PASSED! PIPELINE DEPLOYMENT MVP VALID.")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
