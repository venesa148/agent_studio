import urllib.request
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_end_to_end():
    print("=== STARTING END-TO-END WORKFLOW VERIFICATION ===")
    
    # 1. Builder Chat (Create Agent from prompt)
    prompt_payload = {
        "prompt": "Buat agent BPJS Kesehatan yang bisa cari RS dan cek rujukan"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/builder/chat",
        data=json.dumps(prompt_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        builder_data = json.loads(resp.read().decode())
    
    agent_id = builder_data["id"]
    agent_spec = builder_data["spec"]
    print(f"[OK] Step 1 (Builder Chat): Agent created & saved! ID: {agent_id}, Name: {agent_spec['name']}")
    assert agent_id is not None and len(agent_id) > 0
    assert agent_spec["name"] is not None

    # 2. Get Agent Detail from DB (Persistence Check 1)
    req = urllib.request.Request(f"{BASE_URL}/agent/{agent_id}")
    with urllib.request.urlopen(req) as resp:
        fetched_agent = json.loads(resp.read().decode())
    print(f"[OK] Step 2 (Get Agent Detail): Fetched Agent from DB! Name: {fetched_agent['name']}, Tools: {fetched_agent['tools']}")
    assert fetched_agent["id"] == agent_id

    # 3. Test Agent Chat in Right Panel using Agent ID from DB
    test_payload = {
        "agent_id": agent_id,
        "message": "Halo, tolong cek status rujukan saya RJ-1001"
    }
    req = urllib.request.Request(
        f"{BASE_URL}/agent/chat",
        data=json.dumps(test_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        test_response = json.loads(resp.read().decode())
    
    print(f"[OK] Step 3 (Test Chat): Agent Response Received!")
    print(f"   Agent Name: {test_response['agent_name']}")
    print(f"   Response:\n{test_response['response']}")
    assert test_response["agent_id"] == agent_id
    assert "BPJS" in test_response["agent_name"] or "Agent" in test_response["agent_name"]

    # 4. Refresh / List All Agents from DB (Persistence Check 2)
    req = urllib.request.Request(f"{BASE_URL}/agent")
    with urllib.request.urlopen(req) as resp:
        all_agents = json.loads(resp.read().decode())
    
    print(f"[OK] Step 4 (List Agents): Found {len(all_agents)} agents in database.")
    matching = [a for a in all_agents if a["id"] == agent_id]
    assert len(matching) == 1
    print(f"[SUCCESS] Verified: Agent {agent_id} is persisted in DB across page refreshes!")
    print("=== END-TO-END WORKFLOW VERIFICATION SUCCESSFUL ===")

if __name__ == "__main__":
    test_end_to_end()
