"""Validator provenance: setiap elemen build harus bersumber, dan setiap nilainya harus ditemukan."""
import json
import re

try:
    from .coverage import Ledger
except ImportError:
    from coverage import Ledger

URL_RE = re.compile(r"https?://[^\s'\"<>]+")
NUM_RE = re.compile(r"\b\d{2,}(?:[.,]\d+)?\b|\b\d+[.,]\d+\b")


def extract_values(text: str) -> list[str]:
    return URL_RE.findall(text) + NUM_RE.findall(text)


def _ledger_corpus(ledger: Ledger, docs) -> str:
    parts = [f"{e.verbatim} {json.dumps(e.claim, ensure_ascii=False)}" for e in ledger.entries if e.confirmed]
    return " ".join(parts + list(docs)).lower()


def validate_build(elements, ledger: Ledger, policies: dict[str, str] | None = None, docs=()) -> list[dict]:
    """elements: [{id, source_ids, values?, text?}]. policies: id kebijakan admin -> teksnya."""
    policies = policies or {}
    confirmed = {e.id for e in ledger.entries if e.confirmed}
    base = _ledger_corpus(ledger, docs)
    errors = []
    for el in elements:
        sources = el.get("source_ids") or []
        if not sources:
            errors.append({"element": el["id"], "code": "no_source"})
            continue
        unknown = [s for s in sources if s not in confirmed and s not in policies]
        if unknown:
            errors.append({"element": el["id"], "code": "unknown_source", "ids": unknown})
            continue
        corpus = base + " " + " ".join(policies[s] for s in sources if s in policies).lower()
        values = list(el.get("values", [])) + extract_values(el.get("text", ""))
        for v in values:
            if str(v).lower() not in corpus:
                errors.append({"element": el["id"], "code": "ungrounded", "value": str(v)})
    return errors
