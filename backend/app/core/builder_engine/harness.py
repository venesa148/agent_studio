"""Test Harness: kasus uji dari ledger, tool dimock, penilaian deterministik dulu."""
try:
    from .runner import run_agent
except ImportError:
    from runner import run_agent


def run_case(case: dict, registry: dict, guardrails: list[dict], limits: dict) -> dict:
    script = iter(case["script"])  # keluaran model yang direkam / disimulasikan
    mock = case.get("mock", {})
    result = run_agent(
        lambda messages, tools: next(script),
        registry, guardrails, limits, case["user"],
        lambda tool, args: mock.get(tool["spec"]["name"], {"error": "no_mock"}),  # tanpa efek samping nyata
    )
    called = [(t["tool"], t["args"]) for t in result["trace"]]
    exp, fails = case["expect"], []
    for call in exp.get("calls", []):
        if tuple(call) not in [tuple(c) for c in called]:
            fails.append(f"tool belum dipanggil: {call}")
    for name in exp.get("never_call", []):
        if any(n == name for n, _ in called):
            fails.append(f"tool terlarang dipanggil: {name}")
    if "final_contains" in exp and exp["final_contains"].lower() not in result.get("text", "").lower():
        fails.append("jawaban akhir tidak memuat yang diharapkan")
    if "stop_reason" in exp and result.get("reason") != exp["stop_reason"]:
        fails.append(f"alasan berhenti: {result.get('reason')}")
    return {"case": case["name"], "source_ids": case["source_ids"], "passed": not fails, "fails": fails}


def prepublish_gate(coverage: dict, spec_hash_now: str, spec_hash_approved: str, provenance_errors: list,
                    test_results: list, tools: list[dict], vault_names: set, secrets_needed: set,
                    ledger_ids_with_behavior: set) -> list[str]:
    blockers = []
    if not coverage["can_build"]:
        blockers.append("coverage_incomplete")
    if spec_hash_now != spec_hash_approved:
        blockers.append("spec_changed")
    if provenance_errors:
        blockers.append("ungrounded")
    if any(not r["passed"] for r in test_results):
        blockers.append("tests_failed")
    covered = {s for r in test_results for s in r["source_ids"]}
    if ledger_ids_with_behavior - covered:
        blockers.append("behavior_without_test")  # entri ledger melahirkan perilaku tanpa test
    if any(t["status"] not in ("approved", "published") for t in tools):
        blockers.append("tool_not_approved")
    if secrets_needed - vault_names:
        blockers.append("secret_missing")
    return blockers
