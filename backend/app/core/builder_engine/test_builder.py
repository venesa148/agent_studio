import unittest

from coverage import CORE_KEYS, Ledger, coverage_check, next_questions
from egress import Blocked, check_url
from harness import prepublish_gate, run_case
from provenance import validate_build
from tool_factory import execute_http, transition, validate_spec

PUBLIC = lambda host: ["93.184.216.34"]
HOSTS = ["api.klien.co.id"]

SPEC = {
    "name": "claim_status_lookup",
    "description": "Ambil status klaim berdasarkan nomor klaim. Pakai saat user menyebut nomor klaim. Jangan pakai untuk mengubah status.",
    "input_schema": {"type": "object", "properties": {"claim_no": {"type": "string"}}, "required": ["claim_no"]},
    "implementation": {
        "type": "http", "method": "GET", "url": "https://api.klien.co.id/claims/{claim_no}",
        "auth": {"secret": "claims_api_key", "in": "header", "name": "Authorization"},
        "response": {"select": ["status", "updated_at"], "max_bytes": 20000}, "timeout_ms": 8000,
    },
    "effect": "read", "source_ids": ["L-001"],
}


def full_ledger():
    lg = Ledger()
    for k in CORE_KEYS:
        e = lg.add(k, f"jawaban {k}", {"value": k})
        lg.confirm(e.id)
    return lg


class CoverageTests(unittest.TestCase):
    def test_empty_ledger_blocks_build(self):
        r = coverage_check(Ledger(), "custom")
        self.assertFalse(r["can_build"])
        self.assertEqual(r["percent"], 0)

    def test_full_ledger_allows_build(self):
        self.assertTrue(coverage_check(full_ledger(), "custom")["can_build"])

    def test_unconfirmed_answer_does_not_count(self):
        lg = Ledger()
        lg.add("C1", "tujuan saya", {"value": "x"})
        self.assertEqual(coverage_check(lg, "custom")["satisfied"], 0)

    def test_conflict_detected(self):
        lg = Ledger()
        a = lg.add("C4", "boleh ubah status", {"allow": ["write:claim_status"]}); lg.confirm(a.id)
        b = lg.add("C4", "jangan ubah status", {"deny": ["write:claim_status"]}); lg.confirm(b.id)
        item = next(o for o in coverage_check(lg, "custom")["open"] if o["key"] == "C4")
        self.assertEqual(item["status"], "konflik")

    def test_supersede_resolves_conflict(self):
        lg = Ledger()
        a = lg.add("C4", "boleh ubah", {"allow": ["write:x"]}); lg.confirm(a.id)
        b = lg.add("C4", "tidak jadi, jangan ubah", {"deny": ["write:x"]}, supersedes=a.id); lg.confirm(b.id)
        self.assertNotIn("C4", [o["key"] for o in coverage_check(lg, "custom")["open"]])

    def test_next_questions_max_two_by_priority(self):
        self.assertEqual(next_questions(coverage_check(Ledger(), "custom")), ["C4", "C3"])

    def test_handed_off_stays_open(self):
        lg = full_ledger(); lg.entries = [e for e in lg.entries if e.key != "C6"]; lg.handed_off["C6"] = "Bu Rina"
        item = next(o for o in coverage_check(lg, "custom")["open"] if o["key"] == "C6")
        self.assertEqual(item["owner"], "Bu Rina")


class ProvenanceTests(unittest.TestCase):
    def test_no_source_rejected(self):
        errs = validate_build([{"id": "g1", "source_ids": []}], full_ledger())
        self.assertEqual(errs[0]["code"], "no_source")

    def test_invented_number_rejected(self):
        lg = Ledger(); e = lg.add("C11", "sekitar 200 pertanyaan per hari", {"per_day": 200}); lg.confirm(e.id)
        ok = validate_build([{"id": "l1", "source_ids": [e.id], "text": "batas harian 300"}], lg)
        self.assertEqual(ok[0]["code"], "ungrounded")
        good = validate_build([{"id": "l1", "source_ids": [e.id], "text": "volume 200"}], lg)
        self.assertEqual(good, [])

    def test_unconfirmed_entry_is_not_a_source(self):
        lg = Ledger(); e = lg.add("C1", "tujuan", {})
        self.assertEqual(validate_build([{"id": "x", "source_ids": [e.id]}], lg)[0]["code"], "unknown_source")

    def test_policy_default_is_accepted_only_when_cited(self):
        lg = Ledger()
        pol = {"D-LIMIT-01": "max turn 6"}
        self.assertEqual(validate_build([{"id": "l", "source_ids": ["D-LIMIT-01"], "text": "max 10 turn"}], lg, pol)[0]["code"], "ungrounded")
        self.assertEqual(validate_build([{"id": "l", "source_ids": ["D-LIMIT-01"], "values": ["6"]}], lg, pol), [])


class EgressTests(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(check_url("https://api.klien.co.id/x", HOSTS, PUBLIC))

    def test_blocks(self):
        cases = {
            "http://api.klien.co.id/x": "scheme",
            "https://evil.com/x": "host_not_allowed",
            "https://u:p@api.klien.co.id/x": "credentials",
            "https://api.klien.co.id:8443/x": "port",
        }
        for url, why in cases.items():
            with self.assertRaises(Blocked, msg=url) as cm:
                check_url(url, HOSTS, PUBLIC)
            self.assertEqual(str(cm.exception), why)

    def test_private_and_metadata_ip_blocked(self):
        for ip in ("10.0.0.5", "127.0.0.1", "169.254.169.254"):
            with self.assertRaises(Blocked):
                check_url("https://api.klien.co.id/x", HOSTS, lambda h, ip=ip: [ip])

    def test_wildcard(self):
        self.assertTrue(check_url("https://a.klien.co.id/x", ["*.klien.co.id"], PUBLIC))
        with self.assertRaises(Blocked):
            check_url("https://klien.co.id.evil.com/x", ["*.klien.co.id"], PUBLIC)


class ToolTests(unittest.TestCase):
    def test_valid_spec(self):
        self.assertEqual(validate_spec(SPEC, HOSTS), [])

    def test_bad_specs(self):
        import copy
        bad = copy.deepcopy(SPEC); bad["name"] = "mcp__x"
        self.assertIn("name", validate_spec(bad, HOSTS))
        bad = copy.deepcopy(SPEC); bad["source_ids"] = []
        self.assertIn("source_ids", validate_spec(bad, HOSTS))
        bad = copy.deepcopy(SPEC); bad["implementation"]["auth"]["secret"] = "sk-abc123.real"
        self.assertIn("secret_must_be_a_name", validate_spec(bad, HOSTS))
        bad = copy.deepcopy(SPEC); bad["implementation"]["url"] = "https://evil.com/{claim_no}"
        self.assertIn("egress_host_not_allowed", validate_spec(bad, HOSTS))
        bad = copy.deepcopy(SPEC); bad["implementation"]["url"] = "https://api.klien.co.id/{zzz}"
        self.assertIn("placeholder_zzz", validate_spec(bad, HOSTS))
        bad = copy.deepcopy(SPEC); bad["implementation"]["method"] = "POST"  # menulis tapi dilabeli read
        self.assertIn("effect_method_mismatch", validate_spec(bad, HOSTS))
        bad["effect"] = "write"
        self.assertNotIn("effect_method_mismatch", validate_spec(bad, HOSTS))

    def test_lifecycle_cannot_skip(self):
        t = {"status": "draft", "spec": SPEC}
        with self.assertRaises(ValueError):
            transition(t, "published")
        with self.assertRaises(ValueError):
            transition(t, "tested", tests_passed=False)
        transition(t, "tested", tests_passed=True)
        with self.assertRaises(ValueError):
            transition(t, "approved", user_ok=False)
        transition(t, "approved", user_ok=True)  # read: admin tidak wajib
        transition(t, "published")

    def test_write_tool_needs_admin(self):
        spec = dict(SPEC, effect="write")
        t = {"status": "tested", "spec": spec}
        with self.assertRaises(ValueError):
            transition(t, "approved", user_ok=True)
        transition(t, "approved", user_ok=True, admin_ok=True)

    def test_execute_selects_fields_and_hides_secret(self):
        seen = {}

        def transport(method, url, headers, timeout):
            seen.update(url=url, headers=headers)
            return 200, b'{"status": "diproses", "updated_at": "2026-10-11", "internal": "rahasia", "echo": "KUNCI123"}'

        out = execute_http(SPEC, {"claim_no": "CLM 1/2"}, {"claims_api_key": "KUNCI123"}, HOSTS, transport, PUBLIC)
        self.assertEqual(out["data"], {"status": "diproses", "updated_at": "2026-10-11"})
        self.assertEqual(seen["url"], "https://api.klien.co.id/claims/CLM%201%2F2")  # argumen di-encode, tidak bisa menyisipkan path
        self.assertEqual(seen["headers"]["Authorization"], "KUNCI123")

    def test_execute_blocked_and_missing_secret(self):
        t = lambda *a: (200, b"{}")
        self.assertEqual(execute_http(SPEC, {"claim_no": "1"}, {}, HOSTS, t, PUBLIC)["error"], "secret_missing")
        self.assertTrue(execute_http(SPEC, {"claim_no": "1"}, {"claims_api_key": "k"}, ["lain.com"], t, PUBLIC)["error"].startswith("egress_blocked"))
        self.assertEqual(execute_http(SPEC, {}, {"claims_api_key": "k"}, HOSTS, t, PUBLIC)["error"], "missing_args")

    def test_http_error_does_not_leak(self):
        out = execute_http(SPEC, {"claim_no": "1"}, {"claims_api_key": "k"}, HOSTS, lambda *a: (500, b"boom"), PUBLIC)
        self.assertEqual(out, {"error": "http_500"})


class RunnerHarnessTests(unittest.TestCase):
    def setUp(self):
        self.read = {"status": "published", "spec": SPEC}
        self.write = {"status": "published", "spec": dict(SPEC, name="claim_update", effect="write")}
        self.draft = {"status": "draft", "spec": dict(SPEC, name="claim_draft")}
        self.reg = {"claim_status_lookup": self.read, "claim_update": self.write, "claim_draft": self.draft}
        self.guards = [{"id": "g-no-write", "type": "tool_call", "rule": "deny_effect_write"}]
        self.limits = {"max_turns": 3, "max_tokens": 1000}

    def test_happy_path(self):
        case = {"name": "cek status", "source_ids": ["L-014"], "user": "status CLM-1?",
                "script": [{"type": "tool_use", "name": "claim_status_lookup", "input": {"claim_no": "CLM-1"}},
                           {"type": "text", "text": "Status klaim: diproses"}],
                "mock": {"claim_status_lookup": {"ok": True, "data": {"status": "diproses"}}},
                "expect": {"calls": [["claim_status_lookup", {"claim_no": "CLM-1"}]], "final_contains": "diproses"}}
        self.assertTrue(run_case(case, self.reg, self.guards, self.limits)["passed"])

    def test_guardrail_and_allowlist(self):
        for tool in ("claim_update", "claim_draft", "tidak_ada"):
            case = {"name": f"coba {tool}", "source_ids": ["L-014"], "user": "ubah status",
                    "script": [{"type": "tool_use", "name": tool, "input": {}}, {"type": "text", "text": "maaf"}],
                    "expect": {"final_contains": "maaf"}}
            res = run_case(case, self.reg, self.guards, self.limits)
            self.assertTrue(res["passed"])
        from runner import run_agent
        out = run_agent(lambda m, t: {"type": "tool_use", "name": "claim_update", "input": {}}, self.reg, self.guards, self.limits, "x", lambda t, a: {"ok": True})
        self.assertEqual(out["trace"][0]["result"]["error"], "blocked_by_guardrail")

    def test_model_only_sees_published_tools(self):
        seen = []
        from runner import run_agent
        run_agent(lambda m, tools: (seen.append([t["name"] for t in tools]), {"type": "text", "text": "ok"})[1], self.reg, [], self.limits, "x", None)
        self.assertEqual(sorted(seen[0]), ["claim_status_lookup", "claim_update"])

    def test_loop_stops_at_max_turns(self):
        case = {"name": "loop", "source_ids": ["L-025"], "user": "x",
                "script": [{"type": "tool_use", "name": "claim_status_lookup", "input": {"claim_no": "1"}}] * 5,
                "mock": {"claim_status_lookup": {"ok": True}}, "expect": {"stop_reason": "max_turns"}}
        self.assertTrue(run_case(case, self.reg, self.guards, self.limits)["passed"])

    def test_gate(self):
        cov = coverage_check(full_ledger(), "custom")
        ok_tests = [{"passed": True, "source_ids": ["L-014"]}]
        base = dict(coverage=cov, spec_hash_now="h1", spec_hash_approved="h1", provenance_errors=[], test_results=ok_tests,
                    tools=[{"status": "approved"}], vault_names={"claims_api_key"}, secrets_needed={"claims_api_key"},
                    ledger_ids_with_behavior={"L-014"})
        self.assertEqual(prepublish_gate(**base), [])
        self.assertEqual(prepublish_gate(**dict(base, spec_hash_now="h2")), ["spec_changed"])
        self.assertEqual(prepublish_gate(**dict(base, ledger_ids_with_behavior={"L-014", "L-019"})), ["behavior_without_test"])
        self.assertEqual(prepublish_gate(**dict(base, tools=[{"status": "draft"}], vault_names=set())), ["tool_not_approved", "secret_missing"])
        self.assertIn("coverage_incomplete", prepublish_gate(**dict(base, coverage=coverage_check(Ledger(), "custom"))))


if __name__ == "__main__":
    unittest.main(verbosity=1)
