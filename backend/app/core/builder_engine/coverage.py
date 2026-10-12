"""Requirement Ledger + Coverage Check. Deterministik: tidak ada LLM di sini."""
from dataclasses import dataclass

CORE_KEYS = [f"C{i}" for i in range(1, 13)]
EXTRA_KEYS = {
    "support_faq": ["X-scope", "X-hours", "X-escalation-target"],
    "doc_qa": ["X-citation", "X-not-found", "X-doc-scope"],
    "report": ["X-structure", "X-charts", "X-number-sources"],
    "triage": ["X-categories", "X-priority", "X-examples"],
    "web_research": ["X-domains", "X-depth", "X-source-format"],
    "api_operator": ["X-operations", "X-params", "X-approval-actions"],
    "meeting_notes": ["X-summary-format", "X-owner-rule"],
    "custom": [],
}
# Urutan bertanya: poin yang paling menentukan dulu.
PRIORITY = ["C4", "C3", "C5", "C1", "C6", "C12", "C8", "C9", "C7", "C10", "C2", "C11"]
OK_STATUS = {"terisi", "tidak_berlaku"}


@dataclass
class Entry:
    id: str
    key: str
    verbatim: str            # kutipan asli user, tidak pernah diubah model
    claim: dict              # klaim terstruktur hasil ekstraksi
    confirmed: bool = False  # sudah dibacakan balik dan disetujui user
    supersedes: str | None = None


class Ledger:
    def __init__(self):
        self.entries: list[Entry] = []
        self.defaults: dict[str, str] = {}    # key -> id default admin yang belum dikonfirmasi
        self.handed_off: dict[str, str] = {}  # key -> nama orang yang akan menjawab

    def add(self, key, verbatim, claim, supersedes=None) -> Entry:
        e = Entry(f"L-{len(self.entries) + 1:03d}", key, verbatim, claim, False, supersedes)
        self.entries.append(e)
        return e

    def confirm(self, entry_id):
        next(e for e in self.entries if e.id == entry_id).confirmed = True

    def active(self, key):
        replaced = {e.supersedes for e in self.entries if e.supersedes}
        return [e for e in self.entries if e.key == key and e.id not in replaced]


def _conflict(claims) -> bool:
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if set(a.get("allow", [])) & set(b.get("deny", [])):
                return True
            if set(b.get("allow", [])) & set(a.get("deny", [])):
                return True
            for k in (set(a) & set(b)) - {"allow", "deny"}:
                if not isinstance(a[k], list) and a[k] != b[k]:
                    return True
    return False


def key_status(ledger: Ledger, key: str) -> str:
    if key in ledger.handed_off:
        return "diserahkan"
    active = ledger.active(key)
    if not active:
        return "default_menunggu" if key in ledger.defaults else "kosong"
    if _conflict([e.claim for e in active]):
        return "konflik"
    if not all(e.confirmed for e in active):
        return "kosong"  # belum dikonfirmasi user = belum terisi
    if any(e.claim.get("not_applicable") for e in active):
        return "tidak_berlaku"
    return "terisi"


def coverage_check(ledger: Ledger, kind: str) -> dict:
    required = CORE_KEYS + EXTRA_KEYS.get(kind, [])
    open_items = []
    for key in required:
        status = key_status(ledger, key)
        if status in OK_STATUS:
            continue
        item = {"key": key, "status": status}
        if status == "konflik":
            item["entries"] = [e.id for e in ledger.active(key)]
        elif status == "default_menunggu":
            item["default_id"] = ledger.defaults[key]
        elif status == "diserahkan":
            item["owner"] = ledger.handed_off[key]
        open_items.append(item)
    n = len(required)
    return {
        "agent_kind": kind, "required": n, "satisfied": n - len(open_items),
        "percent": round(100 * (n - len(open_items)) / n),
        "open": open_items, "can_build": not open_items,
    }


def next_questions(report: dict, limit: int = 2) -> list[str]:
    """Maksimal dua poin per giliran, urut dari yang paling menentukan."""
    order = {k: i for i, k in enumerate(PRIORITY)}
    ask = [o["key"] for o in report["open"] if o["status"] in ("kosong", "konflik", "default_menunggu")]
    return sorted(ask, key=lambda k: order.get(k, 99))[:limit]
