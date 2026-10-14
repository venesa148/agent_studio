"""Tool Factory tipe A (HTTP deklaratif): validasi spec, lifecycle, dan eksekutor aman."""
import json
import re
import urllib.request
from urllib.parse import quote, urlparse

try:
    from .egress import Blocked, check_url
except ImportError:
    from egress import Blocked, check_url

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}")
EFFECTS = {"read", "write", "external"}
TRANSITIONS = {
    "draft": {"tested", "retired"},
    "tested": {"approved", "draft", "retired"},
    "approved": {"published", "retired"},
    "published": {"retired"},
    "retired": set(),
}


def validate_spec(spec: dict, allowed_hosts: list[str]) -> list[str]:
    errs = []
    name = spec.get("name", "")
    if not NAME_RE.match(name) or name.startswith(("mcp__", "ant__")):
        errs.append("name")
    if len(spec.get("description", "")) < 40:
        errs.append("description_too_short")  # deskripsi harus menjelaskan kapan dipakai dan tidak
    if spec.get("effect") not in EFFECTS:
        errs.append("effect")
    method = spec.get("implementation", {}).get("method", "")
    if method not in ("GET", "HEAD") and spec.get("effect") == "read":
        errs.append("effect_method_mismatch")  # efek diturunkan dari method, bukan dari klaim model
    if not spec.get("source_ids"):
        errs.append("source_ids")
    impl = spec.get("implementation", {})
    if impl.get("type") != "http":
        errs.append("impl_type")  # fase 1 hanya tipe A
    url = impl.get("url", "")
    host = urlparse(url).hostname or ""
    if "{" in host or not host:
        errs.append("host_must_be_literal")
    props = spec.get("input_schema", {}).get("properties", {})
    required = set(spec.get("input_schema", {}).get("required", []))
    for p in PLACEHOLDER_RE.findall(url):
        if p not in props or p not in required:
            errs.append(f"placeholder_{p}")
    secret = impl.get("auth", {}).get("secret")
    if secret is not None and not NAME_RE.match(secret):
        errs.append("secret_must_be_a_name")  # nilai kunci tidak boleh masuk spec
    try:
        check_url(url.replace("{", "x").replace("}", "x"), allowed_hosts, resolve=lambda h: ["93.184.216.34"])
    except Blocked as e:
        errs.append(f"egress_{e}")
    return errs


def needs_admin(spec: dict) -> bool:
    return spec["effect"] != "read"


def transition(tool: dict, new: str, *, tests_passed=False, user_ok=False, admin_ok=False) -> dict:
    if new not in TRANSITIONS[tool["status"]]:
        raise ValueError(f"{tool['status']} -> {new} tidak diizinkan")
    if new == "tested" and not tests_passed:
        raise ValueError("test belum lulus")
    if new == "approved" and not (user_ok and (admin_ok or not needs_admin(tool["spec"]))):
        raise ValueError("persetujuan belum lengkap")
    tool["status"] = new
    return tool


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # redirect = host lain = bisa lolos allowlist, jadi ditolak


def default_transport(method, url, headers, timeout, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 503, json.dumps({"error": f"Layanan target tidak dapat dijangkau: {str(e)}"}).encode()


def execute_http(spec: dict, args: dict, vault: dict, allowed_hosts: list[str],
                 transport=default_transport, resolve=None) -> dict:
    impl = spec["implementation"]
    missing = [r for r in spec["input_schema"].get("required", []) if r not in args]
    if missing:
        return {"error": "missing_args", "args": missing}
    
    used_keys = set()
    for m in PLACEHOLDER_RE.finditer(impl["url"]):
        used_keys.add(m.group(1))
    url = PLACEHOLDER_RE.sub(lambda m: quote(str(args[m.group(1)]), safe=""), impl["url"])
    
    try:
        kw = {"resolve": resolve} if resolve else {}
        check_url(url, allowed_hosts, **kw)
    except Blocked as e:
        return {"error": f"egress_blocked:{e}"}
        
    headers = {"Accept": "application/json"}
    secret_value = None
    auth = impl.get("auth")
    if auth:
        secret_value = vault.get(auth["secret"])
        if secret_value is None:
            return {"error": "secret_missing", "secret": auth["secret"]}  # hanya nama yang disebut
        headers[auth["name"]] = secret_value
        
    data = None
    method = (impl.get("method") or "GET").upper()
    if method in ("GET", "HEAD"):
        remaining_args = {k: v for k, v in args.items() if k not in used_keys and v is not None}
        if remaining_args:
            from urllib.parse import urlencode
            delimiter = "&" if "?" in url else "?"
            url = f"{url}{delimiter}{urlencode(remaining_args)}"
    else:
        headers["Content-Type"] = "application/json"
        data = json.dumps(args).encode("utf-8")
        
    try:
        status, body = transport(method, url, headers, impl.get("timeout_ms", 8000) / 1000, data=data)
    except TypeError:
        status, body = transport(method, url, headers, impl.get("timeout_ms", 8000) / 1000)
        
    if status >= 400:
        return {"error": f"http_{status}"}
    body = body[: impl.get("response", {}).get("max_bytes", 20000)]
    text = body.decode("utf-8", "replace")
    if secret_value and secret_value in text:
        text = text.replace(secret_value, "[REDACTED]")
    try:
        res_data = json.loads(text)
    except ValueError:
        return {"error": "bad_json"}
    select = impl.get("response", {}).get("select")
    if select and isinstance(res_data, dict):
        res_data = {k: res_data.get(k) for k in select}
    return {"ok": True, "data": res_data}
