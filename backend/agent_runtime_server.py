"""
Agent Runtime Server v3 (Dedicated Multi-Agent ReAct Runtime, domain-agnostic)
==============================================================================
Data Plane untuk Agent Studio. Runtime ini TIDAK mengenal domain spesifik apa pun
(kesehatan, keuangan, e-commerce, HR, customer support, dsb). Semua perilaku domain
didefinisikan secara deklaratif dari agent.yaml:

  - instructions            -> system prompt
  - tools_required          -> tool HTTP / builtin yang boleh dipakai
  - guardrails              -> batas giliran, larangan, konfirmasi, dan "flags"
                               (aturan keselamatan deklaratif)

Fitur utama
-----------
* Release immutable per agent  : deployed_agents/{slug}/releases/v{n}-{hash}.yaml
* Pointer aktif + canary + rollback (activate / rollback / releases)
* Sesi persisten di SQLite (riwayat percakapan, flags, konfirmasi tertunda) + TTL
* Autentikasi: DEPLOY_SECRET untuk endpoint kontrol, API key per agent untuk invoke
* Perlindungan SSRF untuk tool HTTP, secret hanya dari env berawalan AGENT_
* Guardrail deklaratif: max_turns, require_confirmation_for, flags (set_when /
  blocks_tools / instruction), disallowed_behaviors, strict_grounding
* Builtin tool generik: web_search, calculator, datetime, dan classifier
  (aturan keyword + LLM) yang label dan kriterianya ditentukan oleh YAML

Catatan operasional
-------------------
* Jalankan dengan SATU worker uvicorn (registry & lock ada di memori proses).
* Pasang HTTPS di depan runtime (Caddy/Nginx) pada deployment publik.
"""

import asyncio
import ast
import copy
import hashlib
import hmac
import ipaddress
import json
import logging
import operator
import os
import re
import socket
import sqlite3
import sys
import threading
import time
import uuid
import weakref
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agent.runtime")


# =============================================================================
# 0. Konfigurasi (semua dari environment)
# =============================================================================
def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

AGENTS_DIR = Path(os.getenv("AGENTS_DIR", str(BASE_DIR / "deployed_agents")))
AGENTS_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DB_PATH = Path(os.getenv("SESSION_DB", str(BASE_DIR / "data" / "sessions.db")))

RUNTIME_ENVIRONMENT = os.getenv("RUNTIME_ENVIRONMENT", "production")
DEPLOY_SECRET = os.getenv("DEPLOY_SECRET", "")
# Default: izinkan unauthenticated jika DEPLOY_SECRET belum diset di development
ALLOW_UNAUTHENTICATED = _env_bool("ALLOW_UNAUTHENTICATED", default=(not bool(DEPLOY_SECRET)))

SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(24 * 3600)))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "60"))
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "8000"))
MAX_YAML_BYTES = int(os.getenv("MAX_YAML_BYTES", str(256 * 1024)))
MAX_TOOL_RESULT_CHARS = int(os.getenv("MAX_TOOL_RESULT_CHARS", "8000"))
MAX_TOOL_BODY_BYTES = int(os.getenv("MAX_TOOL_BODY_BYTES", str(1024 * 1024)))
MAX_RELEASES_KEPT = int(os.getenv("MAX_RELEASES_KEPT", "30"))
CONFIRMATION_TTL_SECONDS = int(os.getenv("CONFIRMATION_TTL_SECONDS", "900"))

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Jakarta")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# Hanya variabel env berawalan ini yang boleh direferensikan dari YAML
# (${AGENT_X}, auth_secret_ref). Mencegah YAML membocorkan API key sistem.
ENV_REF_PREFIX = os.getenv("TOOL_ENV_PREFIX", "AGENT_")
TOOL_ALLOWED_HOSTS = [h.strip().lower() for h in os.getenv("TOOL_ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOW_PRIVATE_TOOL_HOSTS = _env_bool("ALLOW_PRIVATE_TOOL_HOSTS", default=True)  # default true di dev lokal
EXPOSE_TOOL_DETAILS = _env_bool("EXPOSE_TOOL_DETAILS", default=True)  # dev: kirim params & hasil tool ke klien

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SpecError(ValueError):
    """agent.yaml tidak valid."""


class ToolError(Exception):
    """Kegagalan tool; pesan aman untuk ditampilkan ke LLM."""


class LLMError(Exception):
    pass


class LLMUnavailable(LLMError):
    pass


def normalize_slug(raw: Any) -> str:
    slug = str(raw or "").strip().lower().replace(" ", "-")
    if not SLUG_RE.match(slug):
        raise SpecError("Slug tidak valid. Gunakan huruf kecil, angka, '-' atau '_' (maks 63 karakter).")
    return slug


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write(path: Path, text: str, mode: Optional[int] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex[:6]}.tmp")
    tmp.write_text(text, encoding="utf-8")
    if mode is not None:
        try:
            os.chmod(tmp, mode)
        except OSError:
            pass
    os.replace(tmp, path)


# =============================================================================
# 1. Keamanan tool: env reference & SSRF guard
# =============================================================================
_ENV_REF = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def expand_env(value: str) -> str:
    def repl(m: "re.Match[str]") -> str:
        name = m.group(1)
        if not name.startswith(ENV_REF_PREFIX):
            raise ToolError(f"Variabel '{name}' tidak diizinkan (harus berawalan {ENV_REF_PREFIX}).")
        val = os.getenv(name)
        if val is None:
            raise ToolError(f"Variabel environment '{name}' belum diset di server.")
        return val

    return _ENV_REF.sub(repl, value)


def _host_allowed(host: str) -> bool:
    if not TOOL_ALLOWED_HOSTS:
        return True
    for pat in TOOL_ALLOWED_HOSTS:
        if pat.startswith("*."):
            if host == pat[2:] or host.endswith(pat[1:]):
                return True
        elif host == pat:
            return True
    return False


async def assert_safe_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ToolError("Endpoint tool harus berupa URL http/https yang valid.")
    host = p.hostname.lower()
    if not _host_allowed(host):
        raise ToolError("Host endpoint tool tidak ada di allowlist server (TOOL_ALLOWED_HOSTS).")
    if ALLOW_PRIVATE_TOOL_HOSTS:
        return
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ToolError("Host endpoint tool tidak dapat di-resolve.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ToolError("Endpoint tool mengarah ke alamat jaringan internal dan diblokir.")


# =============================================================================
# 2. LLM gateway
# =============================================================================
_llm_client: Any = None
_llm_is_openrouter = False


def _llm_key() -> str:
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or ""


def get_llm() -> Any:
    global _llm_client, _llm_is_openrouter
    if _llm_client is not None:
        return _llm_client
    key = _llm_key()
    if not key:
        raise LLMUnavailable("API key LLM belum dikonfigurasi di server.")
    from openai import AsyncOpenAI

    _llm_is_openrouter = key.startswith("sk-or-") or "openrouter.ai" in os.getenv("LLM_BASE_URL", "")
    base_url = "https://openrouter.ai/api/v1" if _llm_is_openrouter else (
        os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL"))
    headers = {"X-Title": "Agent Studio Runtime"} if _llm_is_openrouter else None
    if _llm_is_openrouter and os.getenv("LLM_REFERER"):
        headers["HTTP-Referer"] = os.getenv("LLM_REFERER", "")
    _llm_client = AsyncOpenAI(api_key=key, base_url=base_url, default_headers=headers,
                              timeout=LLM_TIMEOUT_SECONDS, max_retries=2)
    return _llm_client


def resolve_model(name: str) -> str:
    get_llm()
    if _llm_is_openrouter and "/" not in name:
        return f"openai/{name}"
    return name


async def llm_chat(model: str, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
                   tool_choice: Optional[str] = None, temperature: float = 0.3, max_tokens: int = 1500) -> Any:
    client = get_llm()
    kwargs: Dict[str, Any] = {"model": resolve_model(model), "messages": messages,
                              "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
    try:
        res = await client.chat.completions.create(**kwargs)
        return res.choices[0].message
    except LLMError:
        raise
    except Exception as e:
        logger.error("[LLM Error] %s: %s", type(e).__name__, e)
        raise LLMError("Layanan model bahasa sedang bermasalah.") from e


# =============================================================================
# 3. Parser tool-call teks (fallback untuk model dengan sintaks tag <tool_call>)
# =============================================================================
_TOOL_BLOCK = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S)
_ARG_PAIR = re.compile(r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>(.*?)</arg_value>", re.S)
_KW_ARG = re.compile(r"""([A-Za-z0-9_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^,]+))""")
_THINK = re.compile(r"<think>.*?</think>", re.S)


def coerce_args(args: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    out = {}
    for k, v in args.items():
        t = (props.get(k) or {}).get("type")
        if isinstance(v, str):
            try:
                if t == "boolean":
                    v = v.strip().lower() in ("true", "1", "ya", "yes")
                elif t == "integer":
                    v = int(v.strip())
                elif t == "number":
                    v = float(v.strip())
            except ValueError:
                pass
        out[k] = v
    return out


def parse_text_tool_calls(text: str, known: set) -> Tuple[str, List[Dict[str, Any]]]:
    calls: List[Dict[str, Any]] = []
    for m in _TOOL_BLOCK.finditer(text):
        body = m.group(1).strip()
        if not body:
            continue
        name: Optional[str] = None
        args: Dict[str, Any] = {}
        if body.startswith("{"):
            try:
                obj = json.loads(body)
                name = obj.get("name")
                args = obj.get("arguments") or obj.get("parameters") or {}
                if isinstance(args, str):
                    args = json.loads(args)
            except Exception:
                name = None
        if name is None:
            pairs = _ARG_PAIR.findall(body)
            if pairs:
                name = body.split("<arg_key>")[0].strip()
                args = {k.strip(): v.strip() for k, v in pairs}
        if name is None:
            mm = re.match(r"([A-Za-z0-9_-]+)\s*\((.*)\)\s*$", body, re.S)
            if mm:
                name, raw = mm.group(1), mm.group(2).strip()
                if raw.startswith("{"):
                    try:
                        args = json.loads(raw)
                    except Exception:
                        args = {}
                if not args and raw:
                    for km in _KW_ARG.finditer(raw):
                        val = km.group(2) if km.group(2) is not None else (
                            km.group(3) if km.group(3) is not None else km.group(4).strip())
                        args[km.group(1)] = val
        if name and name in known and isinstance(args, dict):
            calls.append({"id": f"call_txt_{uuid.uuid4().hex[:8]}", "name": name, "arguments": args})
    cleaned = _TOOL_BLOCK.sub("", text).strip()
    return cleaned, calls


# =============================================================================
# 4. Spesifikasi agent (parser & validasi agent.yaml)
# =============================================================================
@dataclass
class ToolSpec:
    name: str
    description: str
    schema: Dict[str, Any]
    endpoint: Optional[str] = None
    method: str = "POST"
    auth_secret_ref: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 10.0
    source_label: str = "tool"
    requires_confirmation: bool = False
    config: Dict[str, Any] = field(default_factory=dict)


_COND_OPS = ("equals", "in", "contains", "exists", "gte", "lte")


@dataclass
class FlagRule:
    name: str
    triggers: List[Dict[str, Any]]
    blocks_tools: List[str]
    blocked_message: str
    instruction: str


class AgentRuntimeEngine:
    def __init__(self, yaml_text: str, slug: str, release_id: str = "unreleased"):
        if len(yaml_text.encode("utf-8")) > MAX_YAML_BYTES:
            raise SpecError("agent.yaml terlalu besar.")
        try:
            loaded = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            raise SpecError(f"YAML tidak valid: {e}") from e
        if not isinstance(loaded, dict):
            raise SpecError("agent.yaml harus berupa mapping YAML.")

        self.slug = slug
        self.release_id = release_id
        self.raw_spec: Dict[str, Any] = loaded
        meta = loaded.get("metadata") or {}
        self.agent_id = str(meta.get("id") or loaded.get("agent_id") or slug)
        self.name = str(meta.get("name") or loaded.get("name") or slug)
        self.description = str(meta.get("description") or "")
        self.entry_node = str((loaded.get("flow") or {}).get("entry_node") or "main_step")

        inst = loaded.get("instructions")
        if isinstance(inst, dict):
            inst = inst.get("system") or inst.get("instruction")
        inst = inst or loaded.get("system_prompt")
        if not isinstance(inst, str) or not inst.strip():
            raise SpecError("Field 'instructions' wajib diisi.")
        self.system_prompt = inst.strip()

        cfg = loaded.get("configuration") or {}
        model = cfg.get("model") or loaded.get("model") or DEFAULT_MODEL
        if isinstance(model, dict):
            model = model.get("name") or DEFAULT_MODEL
        self.model_name = str(model)
        try:
            self.temperature = min(2.0, max(0.0, float(cfg.get("temperature", 0.3))))
            self.max_tokens = min(8000, max(64, int(cfg.get("max_tokens", 1500))))
        except (TypeError, ValueError) as e:
            raise SpecError("configuration.temperature / max_tokens tidak valid.") from e
        tz_name = str(cfg.get("timezone") or DEFAULT_TIMEZONE)
        try:
            self.tz = ZoneInfo(tz_name)
        except Exception as e:
            raise SpecError(f"Timezone '{tz_name}' tidak dikenal.") from e
        self.tz_name = tz_name

        self.tools: Dict[str, ToolSpec] = {}
        self._parse_tools(loaded)
        self._parse_guardrails(loaded.get("guardrails") or {})

        self.openai_tools = [{
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.schema},
        } for t in self.tools.values()]

    def _parse_tools(self, spec: Dict[str, Any]) -> None:
        for t in spec.get("tools_required") or []:
            if not isinstance(t, dict):
                raise SpecError("Setiap item tools_required harus berupa mapping.")
            ref = str(t.get("tool_ref") or t.get("tool_name") or t.get("name") or "")
            if not TOOL_NAME_RE.match(ref):
                raise SpecError(f"Nama tool '{ref}' tidak valid (huruf/angka/_/-, maks 64).")
            if ref in self.tools:
                raise SpecError(f"Tool '{ref}' didefinisikan lebih dari sekali.")
            schema = t.get("input_schema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema = {"type": "object", "properties": {}}
            method = str(t.get("method") or "POST").upper()
            if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "INTERNAL"):
                raise SpecError(f"Method '{method}' pada tool '{ref}' tidak didukung.")
            try:
                timeout = min(30.0, max(1.0, float(t.get("timeout", 10.0))))
            except (TypeError, ValueError) as e:
                raise SpecError(f"timeout pada tool '{ref}' tidak valid.") from e
            headers = t.get("headers") if isinstance(t.get("headers"), dict) else {}
            self.tools[ref] = ToolSpec(
                name=ref,
                description=str(t.get("purpose") or t.get("description") or f"Tool {ref}"),
                schema=schema,
                endpoint=(str(t["endpoint"]).strip() if t.get("endpoint") else None),
                method=method,
                auth_secret_ref=(str(t["auth_secret_ref"]) if t.get("auth_secret_ref") else None),
                headers={str(k): str(v) for k, v in headers.items()},
                timeout=timeout,
                source_label=str(t.get("mcp_server_name") or t.get("source_type") or "tool"),
                requires_confirmation=bool(t.get("requires_confirmation", False)),
                config=t.get("config") if isinstance(t.get("config"), dict) else {},
            )
        for name in spec.get("tools") or []:
            if isinstance(name, str) and name not in self.tools:
                if not TOOL_NAME_RE.match(name):
                    raise SpecError(f"Nama tool '{name}' tidak valid.")
                self.tools[name] = ToolSpec(name=name, description=f"Tool {name}",
                                            schema={"type": "object", "properties": {}})

    def _parse_guardrails(self, g: Dict[str, Any]) -> None:
        if not isinstance(g, dict):
            raise SpecError("guardrails harus berupa mapping.")
        try:
            self.max_turns = max(0, int(g.get("max_turns") or 0))
            self.max_tool_steps = min(12, max(1, int(g.get("max_tool_steps") or 6)))
        except (TypeError, ValueError) as e:
            raise SpecError("guardrails.max_turns / max_tool_steps harus berupa angka.") from e
        self.max_turns_message = str(g.get("max_turns_message") or
                                     "Batas percakapan untuk sesi ini telah tercapai. Silakan mulai sesi baru.")
        self.strict_grounding = bool(g.get("strict_grounding", False))
        self.disallowed = [str(x) for x in (g.get("disallowed_behaviors") or [])]

        confirm = set(str(x) for x in (g.get("require_confirmation_for") or []))
        confirm |= {t.name for t in self.tools.values() if t.requires_confirmation}
        for name in confirm:
            if name not in self.tools:
                raise SpecError(f"require_confirmation_for merujuk tool '{name}' yang tidak ada.")
        self.confirm_tools = confirm

        self.flag_rules: Dict[str, FlagRule] = {}
        for fname, fdef in (g.get("flags") or {}).items():
            if not isinstance(fdef, dict):
                raise SpecError(f"Flag '{fname}' harus berupa mapping.")
            triggers = fdef.get("set_when") or []
            for tr in triggers:
                if not isinstance(tr, dict) or tr.get("tool") not in self.tools or "path" not in tr \
                        or not any(op in tr for op in _COND_OPS):
                    raise SpecError(f"Trigger pada flag '{fname}' tidak valid "
                                    f"(butuh tool, path, dan salah satu dari {_COND_OPS}).")
            blocks = [str(x) for x in (fdef.get("blocks_tools") or [])]
            for b in blocks:
                if b not in self.tools:
                    raise SpecError(f"Flag '{fname}' memblokir tool '{b}' yang tidak ada.")
            self.flag_rules[str(fname)] = FlagRule(
                name=str(fname), triggers=triggers, blocks_tools=blocks,
                blocked_message=str(fdef.get("blocked_message") or
                                    f"Tindakan ini diblokir karena kondisi '{fname}' aktif pada sesi ini. "
                                    "Jelaskan kepada pengguna dan arahkan sesuai instruksi."),
                instruction=str(fdef.get("instruction") or ""),
            )

    def build_system_prompt(self, flags: List[str]) -> str:
        parts = [self.system_prompt]
        policy: List[str] = []
        if self.strict_grounding:
            policy.append("- Jawab hanya berdasarkan hasil tool atau informasi dari pengguna. "
                          "Jika data tidak tersedia, katakan dengan jujur dan jangan mengarang.")
        for d in self.disallowed:
            policy.append(f"- Jangan pernah: {d}.")
        if self.confirm_tools:
            policy.append(f"- Tool berikut berefek nyata: {', '.join(sorted(self.confirm_tools))}. "
                          "Sebelum memanggilnya, tampilkan ringkasan lengkap dan minta persetujuan eksplisit "
                          "pengguna. Panggil hanya setelah pengguna menyetujui di pesan berikutnya.")
        if policy:
            parts.append("ATURAN KETAT RUNTIME:\n" + "\n".join(policy))
        for f in flags:
            rule = self.flag_rules.get(f)
            if rule and rule.instruction:
                parts.append(f"KONDISI SESI AKTIF '{f}': {rule.instruction}")
        now = datetime.now(self.tz)
        parts.append(f"Waktu saat ini: {now:%Y-%m-%d %H:%M} ({self.tz_name}, {now:%A}).")
        return "\n\n".join(parts)

    async def execute_tool(self, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("[Tool] %s (param: %s)", spec.name, sorted(params.keys()))
        try:
            handler = resolve_builtin(spec)
            if handler:
                return await handler(self, spec, params)
            if spec.endpoint and not spec.endpoint.startswith("internal://"):
                return await self._call_http(spec, params)
            return {"status": "unconfigured",
                    "message": f"Tool '{spec.name}' belum dikonfigurasi (endpoint HTTP atau handler builtin)."}
        except ToolError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.warning("[Tool Error] %s: %s", spec.name, e)
            return {"status": "error", "message": "Tool gagal dijalankan."}

    async def _call_http(self, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
        url = expand_env(spec.endpoint or "")
        await assert_safe_url(url)
        headers = {"Content-Type": "application/json"}
        if spec.auth_secret_ref:
            token = os.getenv(spec.auth_secret_ref) if spec.auth_secret_ref.startswith(ENV_REF_PREFIX) else None
            if not token:
                raise ToolError("Kredensial tool belum dikonfigurasi di server.")
            headers["Authorization"] = f"Bearer {token}"
        for k, v in spec.headers.items():
            headers[k] = expand_env(v)

        client = get_http()
        try:
            if spec.method in ("GET", "DELETE"):
                resp = await client.request(spec.method, url, params=params, headers=headers, timeout=spec.timeout)
            else:
                resp = await client.request(spec.method if spec.method != "INTERNAL" else "POST", url,
                                            json=params, headers=headers, timeout=spec.timeout)
        except httpx.HTTPError as e:
            logger.warning("[Tool HTTP] %s gagal: %s", spec.name, type(e).__name__)
            raise ToolError("Layanan eksternal tidak dapat dijangkau.")

        if len(resp.content) > MAX_TOOL_BODY_BYTES:
            raise ToolError("Respons layanan eksternal terlalu besar.")
        if not 200 <= resp.status_code < 300:
            logger.warning("[Tool HTTP] %s -> %s", spec.name, resp.status_code)
            return {"status": "error", "status_code": resp.status_code,
                    "message": f"Layanan eksternal mengembalikan HTTP {resp.status_code}."}
        try:
            body = resp.json()
        except ValueError:
            body = {"text": resp.text}
        data = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"status": "ok", "count": len(data), "items": data}
        return {"status": "ok", "result": data}

    async def _user_confirmed(self, pending: Dict[str, Any], user_message: str) -> bool:
        prompt = (
            "Tugasmu menilai persetujuan pengguna.\n"
            f"Tindakan yang menunggu persetujuan: tool '{pending['tool']}' dengan argumen "
            f"{json.dumps(pending['args'], ensure_ascii=False)}\n"
            f"Pesan terbaru pengguna: {user_message!r}\n"
            "Apakah pengguna SECARA EKSPLISIT menyetujui tindakan tersebut? "
            "Jawab hanya satu kata: YA atau TIDAK. Jika ragu atau menolak, jawab TIDAK."
        )
        msg = await llm_chat(self.model_name, [{"role": "user", "content": prompt}],
                             temperature=0.0, max_tokens=5)
        return (msg.content or "").strip().upper().startswith("YA")

    def _blocked_by_flag(self, tool: str, flags: set) -> Optional[FlagRule]:
        for fname in flags:
            rule = self.flag_rules.get(fname)
            if rule and tool in rule.blocks_tools:
                return rule
        return None

    def _apply_triggers(self, tool: str, result: Dict[str, Any], flags: set) -> None:
        if result.get("status") in ("error", "blocked", "confirmation_required", "unconfigured"):
            return
        for rule in self.flag_rules.values():
            for tr in rule.triggers:
                if tr["tool"] == tool and _cond_match(_get_path(result, str(tr["path"])), tr):
                    if rule.name not in flags:
                        logger.info("[Flag] '%s' aktif (dipicu oleh %s)", rule.name, tool)
                    flags.add(rule.name)

    async def dispatch_tool(self, name: str, args: Dict[str, Any], state: "TurnState") -> Dict[str, Any]:
        spec = self.tools.get(name)
        if not spec:
            return {"status": "error", "message": f"Tool '{name}' tidak tersedia."}
        args = coerce_args(args if isinstance(args, dict) else {}, spec.schema)
        missing = [k for k in spec.schema.get("required", []) if args.get(k) in (None, "")]
        if missing:
            return {"status": "error", "message": f"Parameter wajib belum ada: {missing}"}

        rule = self._blocked_by_flag(name, state.flags)
        if rule:
            return {"status": "blocked", "message": rule.blocked_message}

        if name in self.confirm_tools:
            key = json.dumps(args, sort_keys=True, ensure_ascii=False)
            p = state.pending
            fresh = p and (time.time() - p["created"] <= CONFIRMATION_TTL_SECONDS)
            if fresh and p["tool"] == name and p["key"] == key and p["turn"] < state.turn_no:
                if await self._user_confirmed(p, state.user_message):
                    state.pending = None
                else:
                    return {"status": "confirmation_required",
                            "message": "Pengguna belum memberikan persetujuan eksplisit. "
                                       "Tanyakan kembali dan jangan eksekusi."}
            else:
                state.pending = {"tool": name, "key": key, "args": args,
                                 "turn": state.turn_no, "created": time.time()}
                return {"status": "confirmation_required",
                        "message": "Belum dieksekusi. Tampilkan ringkasan lengkap tindakan ini kepada pengguna "
                                   "dan minta persetujuan eksplisit. Panggil lagi dengan argumen yang sama "
                                   "setelah pengguna menyetujui."}

        result = await self.execute_tool(spec, args)
        self._apply_triggers(name, result, state.flags)
        return result

    async def run_turn(self, session: "Session", user_message: str) -> "TurnResult":
        if self.max_turns and session.turn_count >= self.max_turns:
            return TurnResult(self.max_turns_message, [], "max_turns_reached")

        state = TurnState(turn_no=session.turn_count + 1, user_message=user_message,
                          flags=set(session.flags), pending=copy.deepcopy(session.pending))
        messages = trim_history(list(session.history))
        messages.append({"role": "user", "content": user_message})
        summaries: List[Dict[str, Any]] = []
        known = set(self.tools)
        final_text = ""

        for step in range(self.max_tool_steps + 1):
            last = step == self.max_tool_steps
            sys_msg = {"role": "system", "content": self.build_system_prompt(sorted(state.flags))}
            msg = await llm_chat(self.model_name, [sys_msg] + messages, tools=self.openai_tools,
                                 tool_choice="none" if last else None,
                                 temperature=self.temperature, max_tokens=self.max_tokens)
            raw = msg.content or ""
            calls: List[Dict[str, Any]] = []
            if getattr(msg, "tool_calls", None):
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except ValueError:
                        args = {}
                    calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
                content = raw
            else:
                content, calls = parse_text_tool_calls(raw, known)
            content = _THINK.sub("", content).strip()

            if last or not calls:
                final_text = content
                break

            messages.append({
                "role": "assistant", "content": content,
                "tool_calls": [{"id": c["id"], "type": "function",
                                "function": {"name": c["name"],
                                             "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                               for c in calls],
            })
            for c in calls:
                result = await self.dispatch_tool(c["name"], c["arguments"], state)
                status = result.get("status") if isinstance(result.get("status"), str) else "ok"
                summary: Dict[str, Any] = {"tool": c["name"], "status": status}
                if EXPOSE_TOOL_DETAILS:
                    summary.update({"params": c["arguments"], "result": result})
                summaries.append(summary)
                payload = json.dumps(result, ensure_ascii=False, default=str)
                if len(payload) > MAX_TOOL_RESULT_CHARS:
                    payload = payload[:MAX_TOOL_RESULT_CHARS] + "...[dipotong]"
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": payload})

        if not final_text:
            raise LLMError("Model tidak menghasilkan jawaban.")

        messages.append({"role": "assistant", "content": final_text})
        session.history = trim_history(messages)
        session.flags = sorted(state.flags)
        session.pending = state.pending
        session.turn_count = state.turn_no
        status = "awaiting_confirmation" if state.pending and state.pending["turn"] == state.turn_no \
            else "in_progress"
        return TurnResult(final_text, summaries, status)


@dataclass
class TurnState:
    turn_no: int
    user_message: str
    flags: set
    pending: Optional[Dict[str, Any]]


@dataclass
class TurnResult:
    text: str
    tool_calls: List[Dict[str, Any]]
    status: str


def trim_history(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Potong dari awal, tapi selalu mulai di pesan user agar pasangan tool_call/tool tidak terpisah."""
    if len(msgs) <= MAX_HISTORY_MESSAGES:
        return msgs
    tail = msgs[-MAX_HISTORY_MESSAGES:]
    for i, m in enumerate(tail):
        if m.get("role") == "user":
            return tail[i:]
    return []


_MISSING = object()


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return _MISSING
    return cur


def _cond_match(value: Any, cond: Dict[str, Any]) -> bool:
    if "exists" in cond:
        return (value is not _MISSING) == bool(cond["exists"])
    if value is _MISSING:
        return False

    def norm(x: Any) -> Any:
        return x.strip().lower() if isinstance(x, str) else x

    try:
        if "equals" in cond:
            return norm(value) == norm(cond["equals"])
        if "in" in cond:
            return norm(value) in [norm(x) for x in cond["in"]]
        if "contains" in cond:
            return str(norm(cond["contains"])) in str(norm(value))
        if "gte" in cond:
            return float(value) >= float(cond["gte"])
        if "lte" in cond:
            return float(value) <= float(cond["lte"])
    except (TypeError, ValueError):
        return False
    return False


# =============================================================================
# 5. Builtin tools (generik, tanpa hardcode domain)
# =============================================================================
BuiltinHandler = Callable[["AgentRuntimeEngine", ToolSpec, Dict[str, Any]], Awaitable[Dict[str, Any]]]
BUILTINS: Dict[str, BuiltinHandler] = {}
BUILTIN_ALIASES: Dict[str, str] = {}


def builtin(endpoint: str, *aliases: str):
    def deco(fn: BuiltinHandler) -> BuiltinHandler:
        BUILTINS[endpoint] = fn
        for a in aliases:
            BUILTIN_ALIASES[a] = endpoint
        return fn
    return deco


def resolve_builtin(spec: ToolSpec) -> Optional[BuiltinHandler]:
    if spec.endpoint and spec.endpoint.startswith("internal://"):
        if spec.endpoint in BUILTINS:
            return BUILTINS[spec.endpoint]
        # endpoint internal apa pun yang punya config.labels atau kueri klasifikasi
        if spec.config.get("labels") or "classify" in spec.endpoint or "triage" in spec.endpoint:
            return BUILTINS["internal://llm/classify"]
        return None
    if not spec.endpoint and spec.name in BUILTIN_ALIASES:
        return BUILTINS[BUILTIN_ALIASES[spec.name]]
    return None


@builtin("internal://builtin/web_search", "web_search", "search_web")
async def _builtin_web_search(engine: AgentRuntimeEngine, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
    query = str(params.get("query") or params.get("q") or "").strip()
    if not query:
        raise ToolError("Parameter 'query' tidak boleh kosong.")

    def _search() -> List[Dict[str, Any]]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, region="id-id", max_results=4))
            return raw or list(ddgs.text(query, region="wt-wt", max_results=4))

    try:
        raw = await asyncio.to_thread(_search)
    except Exception:
        raise ToolError("Layanan pencarian web tidak dapat memuat hasil.")
    return {"status": "ok", "query": query,
            "results": [{"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")} for r in raw]}


_CALC_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
             ast.USub: operator.neg, ast.UAdd: operator.pos}


def _calc_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _CALC_OPS:
        left, right = _calc_eval(node.left), _calc_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 50 or abs(left) > 10000):
            raise ValueError("pangkat terlalu besar")
        return _CALC_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _CALC_OPS:
        return _CALC_OPS[type(node.op)](_calc_eval(node.operand))
    raise ValueError("operator tidak diizinkan")


@builtin("internal://builtin/calculator", "calculator", "math_eval", "calculate")
async def _builtin_calculator(engine: AgentRuntimeEngine, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
    expr = str(params.get("expression") or params.get("expr") or "").strip()
    if not expr or len(expr) > 200:
        raise ToolError("Parameter 'expression' kosong atau terlalu panjang.")
    try:
        return {"status": "ok", "expression": expr, "result": _calc_eval(ast.parse(expr, mode="eval").body)}
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        raise ToolError(f"Gagal menghitung: {e}")


@builtin("internal://builtin/datetime", "get_current_time", "get_current_date", "current_datetime")
async def _builtin_datetime(engine: AgentRuntimeEngine, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now(engine.tz)
    return {"status": "ok", "datetime": now.isoformat(), "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"), "weekday": now.strftime("%A"), "timezone": engine.tz_name}


@builtin("internal://llm/classify", "classify_complaint", "triage")
async def _builtin_classify(engine: AgentRuntimeEngine, spec: ToolSpec, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifier generik. Domain ditentukan sepenuhnya oleh tools_required[].config:
      labels:      [A, B, C]                   (opsional, default jika tidak ada)
      instructions: "kriteria tiap label ..."  (opsional)
      rules:       [{label: A, keywords: [...]}]  (opsional; dicek lebih dulu, urutan = prioritas)
      attributes_hint: "field tambahan yang diminta dari model"  (opsional)
      input_field: nama parameter yang berisi teks  (opsional; default string pertama)
    """
    cfg = spec.config
    labels = [str(x) for x in cfg.get("labels") or []]
    # Fallback aman jika YAML lama belum mengisi labels
    if not labels:
        labels = ["EMERGENCY", "NEED_FURTHER_CARE", "INFORMATION_ONLY"]

    field_name = cfg.get("input_field")
    text = str(params.get(field_name) or "") if field_name else \
        next((str(v) for v in params.values() if isinstance(v, str) and v.strip()), "")
    if not text.strip():
        raise ToolError("Teks yang akan diklasifikasi kosong.")

    low = text.lower()
    for rule in cfg.get("rules") or []:
        label = str(rule.get("label") or "")
        for kw in rule.get("keywords") or []:
            if str(kw).lower() in low and label in labels:
                return {"status": "ok", "label": label, "matched_by": "rule", "confidence": 1.0}

    sys_prompt = (
        "Kamu adalah classifier. Klasifikasikan teks ke tepat satu label.\n"
        f"Label yang valid: {', '.join(labels)}.\n"
        f"{cfg.get('instructions') or ''}\n"
        'Balas HANYA JSON: {"label": "<label>", "confidence": <0-1>, "rationale": "<singkat>", '
        f'"attributes": {{}}}}. {cfg.get("attributes_hint") or ""}'
    )
    msg = await llm_chat(engine.model_name,
                         [{"role": "system", "content": sys_prompt}, {"role": "user", "content": text}],
                         temperature=0.0, max_tokens=400)
    m = re.search(r"\{.*\}", _THINK.sub("", msg.content or ""), re.S)
    try:
        obj = json.loads(m.group(0)) if m else {}
    except ValueError:
        obj = {}
    by_lower = {l.lower(): l for l in labels}
    label = by_lower.get(str(obj.get("label", "")).strip().lower())
    if not label:
        label = labels[0]
    return {"status": "ok", "label": label, "matched_by": "llm",
            "confidence": obj.get("confidence", 0.9), "rationale": obj.get("rationale", ""),
            "attributes": obj.get("attributes") if isinstance(obj.get("attributes"), dict) else {}}


# =============================================================================
# 6. Penyimpanan: sesi (SQLite) & release (disk)
# =============================================================================
@dataclass
class Session:
    slug: str
    session_id: str
    release: Optional[str] = None
    turn_count: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    pending: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        return json.dumps({"release": self.release, "turn_count": self.turn_count, "history": self.history,
                           "flags": self.flags, "pending": self.pending}, ensure_ascii=False)

    @classmethod
    def from_json(cls, slug: str, sid: str, data: str) -> "Session":
        d = json.loads(data)
        return cls(slug, sid, d.get("release"), int(d.get("turn_count", 0)), d.get("history") or [],
                   d.get("flags") or [], d.get("pending"))


class SessionStore:
    def __init__(self, path: Path, ttl: int):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._lock = threading.Lock()
        self._writes = 0
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("CREATE TABLE IF NOT EXISTS sessions (slug TEXT NOT NULL, session_id TEXT NOT NULL, "
                               "data TEXT NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY (slug, session_id))")
            self._conn.commit()
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        self.purge()

    def purge(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM sessions WHERE updated_at < ?", (time.time() - self.ttl,))
            self._conn.commit()

    def _get(self, slug: str, sid: str) -> Optional[Session]:
        with self._lock:
            row = self._conn.execute("SELECT data, updated_at FROM sessions WHERE slug=? AND session_id=?",
                                     (slug, sid)).fetchone()
        if not row or row[1] < time.time() - self.ttl:
            return None
        return Session.from_json(slug, sid, row[0])

    def _put(self, s: Session) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO sessions (slug, session_id, data, updated_at) VALUES (?,?,?,?)",
                               (s.slug, s.session_id, s.to_json(), time.time()))
            self._conn.commit()
            self._writes += 1
            do_purge = self._writes % 200 == 0
        if do_purge:
            self.purge()

    async def get(self, slug: str, sid: str) -> Optional[Session]:
        return await asyncio.to_thread(self._get, slug, sid)

    async def put(self, s: Session) -> None:
        await asyncio.to_thread(self._put, s)


class AgentRecord:
    """Satu agent: kumpulan release immutable + pointer aktif + hash API key."""

    def __init__(self, slug: str):
        self.slug = slug
        self.dir = AGENTS_DIR / slug
        self.engines: Dict[str, AgentRuntimeEngine] = {}
        self.active: Dict[str, Any] = {"stable": None, "canary": None, "canary_percent": 0, "history": []}
        self.api_key_sha256: Optional[str] = None
        self.lock = asyncio.Lock()
        self._load_meta()

    def _release_file(self, rid: str) -> Path:
        return self.dir / "releases" / f"{rid}.yaml"

    def _load_meta(self) -> None:
        for fname, attr in (("auth.json", "auth"), ("active.json", "active")):
            p = self.dir / fname
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if attr == "auth":
                        h = str(data.get("api_key_sha256") or "")
                        self.api_key_sha256 = h if SHA256_RE.match(h) else None
                    else:
                        self.active.update(data)
                except (OSError, ValueError) as e:
                    logger.warning("[%s] gagal membaca %s: %s", self.slug, fname, e)

    def save_active(self) -> None:
        atomic_write(self.dir / "active.json", json.dumps(self.active, indent=2))

    def set_api_key_hash(self, h: str) -> None:
        self.api_key_sha256 = h
        atomic_write(self.dir / "auth.json", json.dumps({"api_key_sha256": h}), mode=0o600)

    def release_ids(self) -> List[str]:
        rel = self.dir / "releases"
        ids = [p.stem for p in rel.glob("v*.yaml")] if rel.exists() else []
        def sort_key(r: str) -> int:
            m = re.match(r"v(\d+)-", r)
            return int(m.group(1)) if m else 0
        return sorted(ids, key=sort_key)

    def release_meta(self, rid: str) -> Dict[str, Any]:
        p = self.dir / "releases" / f"{rid}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (OSError, ValueError):
            return {}

    def get_engine(self, rid: str) -> AgentRuntimeEngine:
        eng = self.engines.get(rid)
        if eng:
            return eng
        f = self._release_file(rid)
        if not f.exists():
            raise KeyError(rid)
        eng = AgentRuntimeEngine(f.read_text(encoding="utf-8"), self.slug, rid)
        self.engines[rid] = eng
        return eng

    def write_release(self, yaml_text: str, env: str) -> Tuple[str, bool]:
        """Buat release baru (atau pakai ulang bila isi identik). Mengembalikan (release_id, baru?)."""
        digest = sha256_hex(yaml_text)
        for rid in self.release_ids():
            if self.release_meta(rid).get("sha256") == digest:
                return rid, False
        ids = self.release_ids()
        last_n = 0
        if ids:
            m = re.match(r"v(\d+)-", ids[-1])
            if m:
                last_n = int(m.group(1))
        rid = f"v{last_n + 1}-{digest[:8]}"
        atomic_write(self._release_file(rid), yaml_text)
        atomic_write(self.dir / "releases" / f"{rid}.json", json.dumps(
            {"sha256": digest, "created_at": datetime.now(timezone.utc).isoformat(), "environment": env}))
        self._prune()
        return rid, True

    def _prune(self) -> None:
        protected = {self.active.get("stable"), self.active.get("canary"), *self.active.get("history", [])}
        ids = self.release_ids()
        for rid in ids[:-MAX_RELEASES_KEPT] if MAX_RELEASES_KEPT > 0 else []:
            if rid not in protected:
                for ext in (".yaml", ".json"):
                    try:
                        (self.dir / "releases" / f"{rid}{ext}").unlink()
                    except OSError:
                        pass
                self.engines.pop(rid, None)

    def activate(self, rid: str, strategy: str, canary_percent: int) -> None:
        if rid not in self.release_ids():
            raise KeyError(rid)
        self.get_engine(rid)  # pastikan bisa dimuat sebelum dipakai
        a = self.active
        if strategy == "canary" and a.get("stable") and a["stable"] != rid:
            if canary_percent <= 0:
                raise ValueError("canary_percent harus > 0 untuk strategi canary.")
            a["canary"], a["canary_percent"] = rid, canary_percent
        else:
            old = a.get("stable")
            if old and old != rid:
                a["history"] = (a.get("history", []) + [old])[-20:]
            a["stable"], a["canary"], a["canary_percent"] = rid, None, 0
        self.save_active()

    def rollback(self, target: Optional[str]) -> str:
        a = self.active
        if target:
            if target not in self.release_ids():
                raise KeyError(target)
            rid = target
        else:
            rid = None
            while a.get("history"):
                cand = a["history"].pop()
                if cand in self.release_ids():
                    rid = cand
                    break
            if not rid:
                raise LookupError("Tidak ada release sebelumnya untuk rollback.")
        self.get_engine(rid)
        a["stable"], a["canary"], a["canary_percent"] = rid, None, 0
        self.save_active()
        return rid

    def pick_release(self, session_id: str) -> str:
        a = self.active
        if not a.get("stable"):
            raise LookupError("Agent belum memiliki release aktif.")
        pct = int(a.get("canary_percent") or 0)
        if a.get("canary") and pct > 0 and int(sha256_hex(session_id)[:8], 16) % 100 < pct:
            return a["canary"]
        return a["stable"]


# =============================================================================
# 7. Registry global, boot, dan migrasi file lama
# =============================================================================
agents_registry: Dict[str, AgentRecord] = {}
session_store: Optional[SessionStore] = None
_session_locks: "weakref.WeakValueDictionary[Tuple[str, str], asyncio.Lock]" = weakref.WeakValueDictionary()
_http_client: Optional[httpx.AsyncClient] = None


def get_http() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(follow_redirects=False)
    return _http_client


def get_session_lock(slug: str, sid: str) -> asyncio.Lock:
    key = (slug, sid)
    lock = _session_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[key] = lock
    return lock


def boot_registry() -> None:
    # migrasi layout lama: deployed_agents/{slug}.yaml -> release v1
    for f in sorted(AGENTS_DIR.glob("*.yaml")):
        try:
            slug = normalize_slug(f.stem)
            text = f.read_text(encoding="utf-8")
            AgentRuntimeEngine(text, slug)  # validasi
            rec = AgentRecord(slug)
            rid, _ = rec.write_release(text, RUNTIME_ENVIRONMENT)
            if not rec.active.get("stable"):
                rec.activate(rid, "all", 0)
            f.rename(f.with_suffix(".yaml.migrated"))
            logger.warning("[Migrasi] %s -> release %s. API key belum diset.", f.name, rid)
        except Exception as e:
            logger.warning("[Migrasi] gagal untuk %s: %s", f.name, e)

    for d in sorted(p for p in AGENTS_DIR.iterdir() if p.is_dir()):
        try:
            slug = normalize_slug(d.name)
            rec = AgentRecord(slug)
            for rid in {rec.active.get("stable"), rec.active.get("canary")} - {None}:
                rec.get_engine(rid)
            agents_registry[slug] = rec
            logger.info("[Boot] agent '%s' dimuat (stable=%s, canary=%s)", slug,
                        rec.active.get("stable"), rec.active.get("canary"))
        except Exception as e:
            logger.warning("[Boot] gagal memuat agent di %s: %s", d.name, e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global session_store
    session_store = SessionStore(SESSION_DB_PATH, SESSION_TTL_SECONDS)
    boot_registry()
    if not DEPLOY_SECRET and not ALLOW_UNAUTHENTICATED:
        logger.warning("DEPLOY_SECRET belum diset: endpoint deploy/kontrol DITOLAK sampai diset.")
    yield
    if _http_client is not None:
        await _http_client.aclose()


# =============================================================================
# 8. FastAPI Endpoints
# =============================================================================
class InvokeRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)


class InvokeResponse(BaseModel):
    session_id: str
    agent_id: str
    agent_slug: str
    release: str
    response: str
    current_node: str
    status: str
    turn_count: int
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class DeployRequest(BaseModel):
    yaml_content: str
    slug: Optional[str] = None
    target_environment: str = "production"
    activate: bool = True
    strategy: str = "all"          # "all" | "canary"
    canary_percent: int = Field(0, ge=0, le=100)
    api_key_sha256: Optional[str] = None
    api_key: Optional[str] = None  # opsional; di-hash seketika dan tidak disimpan mentah


# =============================================================================
# 2. Agent Runtime Engine (Parser & Autonomous ReAct Loop)
# =============================================================================
class AgentRuntimeEngine:
    def __init__(self, config_content: str, slug: str):
        self.slug = slug
        self.raw_spec: Dict[str, Any] = {}
        self.agent_id: str = slug
        self.name: str = "AI Assistant"
        self.version: int = 1
        self.description: str = ""
        self.system_prompt: str = ""
        self.model_name: str = "gpt-4o-mini"
        self.tools_required: List[Dict[str, Any]] = []
        self.tools_by_ref: Dict[str, Dict[str, Any]] = {}
        self.openai_tools: List[Dict[str, Any]] = []
        self.load_config(config_content)

    def load_config(self, content: str):
        try:
            loaded = yaml.safe_load(content)
            self.raw_spec = loaded if isinstance(loaded, dict) else {}
            meta = self.raw_spec.get("metadata", {})
            self.agent_id = str(meta.get("id") or self.raw_spec.get("agent_id") or self.slug)
            self.name = str(meta.get("name") or self.raw_spec.get("name") or "AI Assistant")
            self.version = int(meta.get("version") or self.raw_spec.get("version") or 1)
            self.description = str(meta.get("description") or self.raw_spec.get("description") or "")

            inst = self.raw_spec.get("instructions")
            if isinstance(inst, str) and inst.strip():
                self.system_prompt = inst.strip()
            elif isinstance(inst, dict):
                self.system_prompt = inst.get("system", "") or inst.get("instruction", "")
            else:
                self.system_prompt = self.raw_spec.get("system_prompt", f"Kamu adalah {self.name}.")

            cfg = self.raw_spec.get("configuration", {}).get("model") or self.raw_spec.get("model", "gpt-4o-mini")
            if isinstance(cfg, dict):
                self.model_name = cfg.get("name", "gpt-4o-mini")
            else:
                self.model_name = str(cfg)

            # Parse tools_required dari YAML
            self.tools_required = self.raw_spec.get("tools_required", [])
            self.tools_by_ref = {}
            for t in self.tools_required:
                ref = t.get("tool_ref") or t.get("name") or t.get("tool_name")
                if ref:
                    self.tools_by_ref[ref] = t

            # Fallback jika tools didefinisikan dalam format list string tools: [...]
            for tname in self.raw_spec.get("tools", []):
                if isinstance(tname, str) and tname not in self.tools_by_ref:
                    self.tools_by_ref[tname] = {"tool_ref": tname, "endpoint": None, "purpose": f"Layanan tool {tname}"}

            # Siapkan schema tool function calling untuk LLM
            self.openai_tools = []
            for ref, t_info in self.tools_by_ref.items():
                schema = t_info.get("input_schema")
                if not isinstance(schema, dict) or "type" not in schema:
                    schema = {"type": "object", "properties": {}}
                desc = t_info.get("purpose") or t_info.get("description") or f"Layanan tool {ref}"
                self.openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": ref,
                        "description": desc,
                        "parameters": schema
                    }
                })

            logger.info(
                f"[Engine] Agent '{self.name}' (slug: {self.slug}) dimuat dengan "
                f"{len(self.openai_tools)} live tools. Model: {self.model_name}"
            )
        except Exception as e:
            logger.error(f"[Engine Load Error] Gagal memuat YAML: {e}")

    async def execute_tool(self, tool_ref: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generic Dynamic Tool Dispatcher:
        - Mengeksekusi live HTTP/REST endpoints (GET, POST, PUT, DELETE) sesuai deklarasi tool di YAML.
        - Meneruskan parameter dinamis dan custom auth headers secara universal tanpa hardcoded domain logic.
        - Menyediakan built-in general utilities (DuckDuckGo Search, Safe Math Calculator, Current Datetime).
        - Menangani unconfigured/mock tools secara graceful dan terstruktur.
        """
        logger.info(f"[Runtime Tool Call] Menjalankan tool '{tool_ref}' dengan params: {params}")
        t_info = self.tools_by_ref.get(tool_ref, {})
        endpoint = t_info.get("endpoint")
        method = str(t_info.get("method") or "POST").upper()

        # 1. Live HTTP/REST Web API & MCP HTTP Runner (100% Dinamis & Universal)
        if endpoint and (endpoint.startswith("http://") or endpoint.startswith("https://")):
            headers = {"Content-Type": "application/json"}
            
            # Auth header dinamis jika ada
            auth_secret = t_info.get("auth_secret_ref") or t_info.get("api_key")
            if auth_secret:
                headers["Authorization"] = f"Bearer {auth_secret}"
            
            # Custom headers tambahan dari spesifikasi tool di YAML
            if isinstance(t_info.get("headers"), dict):
                headers.update(t_info["headers"])

            timeout_sec = float(t_info.get("timeout", 10.0))

            try:
                async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
                    if method == "GET":
                        resp = await client.get(endpoint, params=params, headers=headers)
                    elif method in ("PUT", "PATCH"):
                        resp = await client.request(method, endpoint, json=params, headers=headers)
                    elif method == "DELETE":
                        resp = await client.delete(endpoint, params=params, headers=headers)
                    else:
                        resp = await client.post(endpoint, json=params, headers=headers)

                    if 200 <= resp.status_code < 300:
                        try:
                            body = resp.json()
                        except Exception:
                            body = {"text": resp.text}

                        data = body.get("data", body) if isinstance(body, dict) else body
                        logger.info(f"[Live HTTP Tool OK] {tool_ref} -> {resp.status_code}")
                        
                        source_label = t_info.get("mcp_server_name") or t_info.get("source_type") or "Live Web API"
                        if isinstance(data, dict):
                            data["_endpoint"] = endpoint
                            data["_source"] = source_label
                            return data
                        elif isinstance(data, list):
                            return {
                                "status": "ok",
                                "count": len(data),
                                "items": data,
                                "_endpoint": endpoint,
                                "_source": source_label
                            }
                        return {"status": "ok", "result": data, "_endpoint": endpoint, "_source": source_label}
                    else:
                        logger.warning(f"[Live HTTP Tool Status {resp.status_code}] {tool_ref}: {resp.text[:200]}")
                        return {
                            "status": "error",
                            "status_code": resp.status_code,
                            "_endpoint": endpoint,
                            "_source": t_info.get("mcp_server_name") or "Live Web API",
                            "message": f"Server eksternal mengembalikan HTTP {resp.status_code} untuk tool '{tool_ref}'."
                        }
            except Exception as e:
                logger.warning(f"[Live HTTP Tool Error] {tool_ref} ({endpoint}): {e}")
                return {
                    "status": "error",
                    "error_type": "SERVICE_UNAVAILABLE",
                    "_endpoint": endpoint,
                    "_source": t_info.get("mcp_server_name") or "Live Web API (Offline)",
                    "message": f"Server live API ({endpoint}) tidak dapat dijangkau: {str(e)}"
                }

        # 2. General Utility: Live Web Search (DuckDuckGo Search)
        if tool_ref in ["search_web", "web_search"]:
            query = str(params.get("query") or params.get("q") or "").strip()
            if not query:
                return {"status": "error", "message": "Parameter 'query' tidak boleh kosong."}
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, region="id-id", max_results=4))
                    if not raw:
                        raw = list(ddgs.text(query, region="wt-wt", max_results=4))
                    if raw:
                        return {
                            "status": "ok",
                            "query": query,
                            "results": [{"title": r.get("title"), "snippet": r.get("body"), "url": r.get("href")} for r in raw],
                            "_source": "DuckDuckGo Web Search",
                            "_endpoint": "https://duckduckgo.com"
                        }
            except Exception as e_search:
                logger.warning(f"[Web Search Warning] {e_search}")
            return {"status": "error", "query": query, "message": "Layanan pencarian web sedang tidak dapat memuat hasil."}

        # 3. General Utility: Safe Math Calculator
        if tool_ref in ["calculator", "math_eval", "calculate"]:
            expr = str(params.get("expression") or params.get("expr") or "").strip()
            if not expr:
                return {"status": "error", "message": "Parameter 'expression' tidak boleh kosong."}
            try:
                import ast
                import operator
                ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}
                def _eval(node):
                    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                        return node.value
                    elif isinstance(node, ast.BinOp) and type(node.op) in ops:
                        return ops[type(node.op)](_eval(node.left), _eval(node.right))
                    elif isinstance(node, ast.UnaryOp) and type(node.op) in ops:
                        return ops[type(node.op)](_eval(node.operand))
                    raise ValueError("Operator tidak diizinkan")
                val = _eval(ast.parse(expr, mode='eval').body)
                return {"status": "ok", "expression": expr, "result": val, "_endpoint": "internal://calculator"}
            except Exception as e_calc:
                return {"status": "error", "expression": expr, "message": f"Gagal menghitung: {str(e_calc)}"}

        # 4. General Utility: Current Datetime
        if tool_ref in ["get_current_time", "get_current_date", "current_datetime"]:
            from datetime import datetime
            now = datetime.now()
            return {
                "status": "ok",
                "datetime": now.isoformat(),
                "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "_endpoint": "internal://datetime"
            }

        # 5. Generic Unconfigured Tool
        return {
            "status": "unconfigured",
            "tool": tool_ref,
            "message": f"Tool '{tool_ref}' belum dikonfigurasi endpoint HTTP live-nya.",
            "params": params
        }

    async def execute_llm_step(
        self, user_message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Autonomous ReAct Agent Loop:
        - Mendukung multi-turn tool calling secara berurutan dan riwayat percakapan
        - Mendukung format function calling OpenAI JSON resmi
        - Fallback Regex Interceptor jika model (misal GLM / ChatGLM) mencetak <tool_call> di teks
        - Otomatis merangkum hasil tool menjadi jawaban ramah & profesional
        """
        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
            or ""
        )
        if not api_key:
            return f"Halo! Saya {self.name}. (Server belum dikonfigurasi API Key LLM).", []

        from openai import AsyncOpenAI
        is_openrouter = api_key.startswith("sk-or-") or "openrouter.ai" in os.getenv("LLM_BASE_URL", "")
        base_url = "https://openrouter.ai/api/v1" if is_openrouter else os.getenv("OPENAI_BASE_URL")

        target_model = self.model_name
        if is_openrouter and "/" not in target_model:
            target_model = f"openai/{target_model}"

        headers = {
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Agent Studio Runtime"
        } if is_openrouter else None

        client = AsyncOpenAI(api_key=api_key, base_url=base_url, default_headers=headers)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        if history:
            for h in history[-20:]:
                if h.get("role") in ["user", "assistant"] and h.get("content"):
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_message})

        executed_tools: List[Dict[str, Any]] = []
        max_turns = 5

        for turn in range(max_turns):
            call_kwargs: Dict[str, Any] = {
                "model": target_model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.3
            }
            if self.openai_tools:
                call_kwargs["tools"] = self.openai_tools

            try:
                res = await client.chat.completions.create(**call_kwargs)
            except Exception as e:
                logger.error(f"[LLM Call Error] {e}")
                break

            msg = res.choices[0].message
            raw_content = msg.content or ""
            parsed_tool_calls: List[Dict[str, Any]] = []

            # 1. Parsing jika LLM mengembalikan format OpenAI Tool Calls resmi
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except Exception:
                        args = {}
                    parsed_tool_calls.append({
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": args,
                        "raw_args": tc.function.arguments or "{}"
                    })

            # 2. Fallback Regex Interceptor jika model (misal GLM / ChatGLM) mencetak tag <tool_call> di teks
            elif "<tool_call>" in raw_content:
                import re
                matches = re.findall(r'<tool_call>\s*([a-zA-Z0-9_-]+)\s*\((.*?)\)', raw_content)
                for fn_name, raw_args in matches:
                    args = {}
                    raw_args = raw_args.strip()
                    if raw_args.startswith("{") and raw_args.endswith("}"):
                        try:
                            args = json.loads(raw_args)
                        except Exception:
                            pass
                    if not args and raw_args:
                        pattern = r'([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,)]+))'
                        for m in re.finditer(pattern, raw_args):
                            k = m.group(1)
                            v = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4).strip())
                            args[k] = v

                    parsed_tool_calls.append({
                        "id": f"call_regex_{uuid.uuid4().hex[:8]}",
                        "name": fn_name,
                        "arguments": args,
                        "raw_args": json.dumps(args, ensure_ascii=False)
                    })

            # Jika tidak ada pemanggilan tool lagi, kita telah sampai pada jawaban akhir
            if not parsed_tool_calls:
                final_text = raw_content
                if not final_text and getattr(msg, "reasoning", None):
                    final_text = msg.reasoning
                if final_text and final_text.strip():
                    return final_text.strip(), executed_tools
                break

            # Catat instruksi assistant ke percakapan
            tool_payload = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["raw_args"]}
                }
                for tc in parsed_tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": raw_content or "",
                "tool_calls": tool_payload
            })

            # Eksekusi setiap tool secara dinamis
            for tc in parsed_tool_calls:
                fn_name = tc["name"]
                fn_args = tc["arguments"]
                tool_res = await self.execute_tool(fn_name, fn_args)
                executed_tools.append({"tool": fn_name, "params": fn_args, "result": tool_res})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(tool_res, ensure_ascii=False)
                })

        # Jika loop tools selesai tetapi belum menghasilkan teks final yang dirangkum
        if executed_tools:
            try:
                messages.append({
                    "role": "user",
                    "content": (
                        "Tolong rangkum semua data yang sudah kamu peroleh dari tools di atas ke dalam format jawaban yang "
                        "jelas, solutif, terstruktur, dan ramah sesuai dengan peran dan instruksi kamu kepada pengguna."
                    )
                })
                synth_res = await client.chat.completions.create(
                    model=target_model,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.3
                )
                synth_msg = synth_res.choices[0].message
                final_synth = synth_msg.content or getattr(synth_msg, "reasoning", "")
                if final_synth and final_synth.strip():
                    return final_synth.strip(), executed_tools
            except Exception as e:
                logger.error(f"[Synthesis Call Error] {e}")

        fallback = f"Halo, data Anda telah berhasil diverifikasi oleh {self.name}."
        return fallback, executed_tools

    async def run_step(self, session_id: str, user_message: str) -> InvokeResponse:
        # Batasi ukuran session_memory agar tidak terjadi memory leak (maksimal 1000 sesi)
        if len(session_memory) > 1000:
            oldest_keys = list(session_memory.keys())[:200]
            for ok in oldest_keys:
                session_memory.pop(ok, None)

        session = session_memory.setdefault(session_id, {"turn_count": 0, "history": []})
        session["turn_count"] += 1

        history = session.get("history", [])
        response_text, tool_calls = await self.execute_llm_step(user_message, history=history)

        # Simpan interaksi ke riwayat session untuk multi-turn context
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": response_text})
        session["history"] = history[-30:]

        return InvokeResponse(
            session_id=session_id,
            agent_id=self.agent_id,
            agent_slug=self.slug,
            response=response_text,
            current_node="main_step",
            status="in_progress",
            turn_count=session["turn_count"],
            tool_calls=tool_calls
        )


class RollbackRequest(BaseModel):
    release: Optional[str] = None


class ApiKeyRequest(BaseModel):
    api_key_sha256: Optional[str] = None
    api_key: Optional[str] = None


app = FastAPI(title="Agent Studio Multi-Agent Runtime", version="3.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bearer(authorization: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def require_deploy_auth(authorization: Optional[str] = Header(None),
                        x_deploy_secret: Optional[str] = Header(None)) -> None:
    if not DEPLOY_SECRET:
        if ALLOW_UNAUTHENTICATED:
            return
        raise HTTPException(503, "DEPLOY_SECRET belum dikonfigurasi di runtime.")
    supplied = x_deploy_secret or _bearer(authorization)
    if not supplied or not hmac.compare_digest(supplied.encode(), DEPLOY_SECRET.encode()):
        raise HTTPException(401, "Kredensial deploy tidak valid.", headers={"WWW-Authenticate": "Bearer"})


def authenticate_invoke(record: AgentRecord, authorization: Optional[str]) -> None:
    if record.api_key_sha256 is None:
        if ALLOW_UNAUTHENTICATED:
            return
        raise HTTPException(401, "Agent ini belum memiliki API key.", headers={"WWW-Authenticate": "Bearer"})
    token = _bearer(authorization)
    if not token or not hmac.compare_digest(sha256_hex(token).encode(), record.api_key_sha256.encode()):
        raise HTTPException(401, "API key tidak valid.", headers={"WWW-Authenticate": "Bearer"})


def _resolve_key_hash(api_key_sha256: Optional[str], api_key: Optional[str]) -> Optional[str]:
    if api_key_sha256:
        h = api_key_sha256.strip().lower()
        if not SHA256_RE.match(h):
            raise HTTPException(400, "api_key_sha256 harus berupa 64 karakter hex.")
        return h
    if api_key:
        if len(api_key) < 16:
            raise HTTPException(400, "api_key terlalu pendek (minimal 16 karakter).")
        return sha256_hex(api_key)
    return None


def _get_record(slug_raw: str) -> AgentRecord:
    try:
        slug = normalize_slug(slug_raw)
    except SpecError:
        raise HTTPException(404, "Agent tidak ditemukan.")
    rec = agents_registry.get(slug)
    if not rec:
        raise HTTPException(404, "Agent tidak ditemukan.")
    return rec


def _endpoint_url(slug: str) -> str:
    base = PUBLIC_BASE_URL or f"http://{'localhost' if HOST == '0.0.0.0' else HOST}:{PORT}"
    return f"{base}/agents/{slug}/invoke"


@app.get("/health", tags=["Monitoring"])
def health():
    return {"status": "healthy", "agents": len(agents_registry), "environment": RUNTIME_ENVIRONMENT}


@app.get("/agents/{agent_slug}/health", tags=["Monitoring"])
def health_by_slug(agent_slug: str):
    rec = _get_record(agent_slug)
    stable = rec.active.get("stable")
    if not stable:
        return {"status": "no_active_release", "slug": rec.slug}
    eng = rec.get_engine(stable)
    return {"status": "healthy", "slug": rec.slug, "release": stable, "agent_name": eng.name,
            "tools_count": len(eng.openai_tools), "canary": rec.active.get("canary"),
            "canary_percent": rec.active.get("canary_percent", 0)}


@app.post("/deploy", tags=["Deployment"], dependencies=[Depends(require_deploy_auth)])
async def deploy_agent(req: DeployRequest):
    if req.target_environment != RUNTIME_ENVIRONMENT:
        raise HTTPException(400, f"Runtime ini melayani environment '{RUNTIME_ENVIRONMENT}', "
                                 f"bukan '{req.target_environment}'.")
    if req.strategy not in ("all", "canary"):
        raise HTTPException(400, "strategy harus 'all' atau 'canary'.")
    try:
        loaded = yaml.safe_load(req.yaml_content) or {}
        meta = loaded.get("metadata") or {} if isinstance(loaded, dict) else {}
        slug = normalize_slug(req.slug or meta.get("slug") or (loaded.get("slug") if isinstance(loaded, dict) else None))
        engine = AgentRuntimeEngine(req.yaml_content, slug)  # validasi penuh sebelum menyentuh disk
    except (SpecError, yaml.YAMLError) as e:
        raise HTTPException(400, f"agent.yaml ditolak: {e}")

    key_hash = _resolve_key_hash(req.api_key_sha256, req.api_key)
    rec = agents_registry.get(slug) or AgentRecord(slug)
    if key_hash is None and rec.api_key_sha256 is None and not ALLOW_UNAUTHENTICATED:
        raise HTTPException(400, "Sertakan api_key_sha256 (atau api_key) untuk agent baru.")

    async with rec.lock:
        rid, created = await asyncio.to_thread(rec.write_release, req.yaml_content, req.target_environment)
        engine.release_id = rid
        rec.engines[rid] = engine
        if key_hash:
            rec.set_api_key_hash(key_hash)
        activated = False
        if req.activate:
            try:
                rec.activate(rid, req.strategy, req.canary_percent)
                activated = True
            except ValueError as e:
                raise HTTPException(400, str(e))
        agents_registry[slug] = rec

    logger.info("[Deploy] %s release=%s baru=%s aktif=%s", slug, rid, created, activated)
    return {"status": "deployed" if activated else "staged", "agent_id": engine.agent_id, "agent_slug": slug,
            "release": rid, "new_release": created, "active": rec.active, "endpoint": _endpoint_url(slug),
            "message": f"Release {rid} untuk '{engine.name}' "
                       f"{'aktif' if activated else 'disimpan (belum aktif)'}."}


@app.get("/agents/{agent_slug}/releases", tags=["Deployment"], dependencies=[Depends(require_deploy_auth)])
def list_releases(agent_slug: str):
    rec = _get_record(agent_slug)
    return {"slug": rec.slug, "active": rec.active,
            "releases": [{"id": r, **rec.release_meta(r)} for r in rec.release_ids()]}


@app.post("/agents/{agent_slug}/activate", tags=["Deployment"], dependencies=[Depends(require_deploy_auth)])
async def activate_release(agent_slug: str, req: ActivateRequest):
    rec = _get_record(agent_slug)
    async with rec.lock:
        try:
            rec.activate(req.release, req.strategy, req.canary_percent)
        except KeyError:
            raise HTTPException(404, "Release tidak ditemukan.")
        except (ValueError, SpecError) as e:
            raise HTTPException(400, str(e))
    return {"status": "activated", "active": rec.active}


@app.post("/agents/{agent_slug}/rollback", tags=["Deployment"], dependencies=[Depends(require_deploy_auth)])
async def rollback_release(agent_slug: str, req: RollbackRequest = RollbackRequest()):
    rec = _get_record(agent_slug)
    async with rec.lock:
        try:
            rid = rec.rollback(req.release)
        except KeyError:
            raise HTTPException(404, "Release tidak ditemukan.")
        except LookupError as e:
            raise HTTPException(409, str(e))
    return {"status": "rolled_back", "release": rid, "active": rec.active}


@app.post("/agents/{agent_slug}/api-key", tags=["Deployment"], dependencies=[Depends(require_deploy_auth)])
async def set_api_key(agent_slug: str, req: ApiKeyRequest):
    rec = _get_record(agent_slug)
    h = _resolve_key_hash(req.api_key_sha256, req.api_key)
    if not h:
        raise HTTPException(400, "Sertakan api_key_sha256 atau api_key.")
    async with rec.lock:
        rec.set_api_key_hash(h)
    return {"status": "updated"}


@app.post("/agents/{agent_slug}/invoke", response_model=InvokeResponse, tags=["Invocation"])
async def invoke_by_slug(agent_slug: str, payload: InvokeRequest, authorization: Optional[str] = Header(None)):
    rec = _get_record(agent_slug)
    authenticate_invoke(rec, authorization)
    sid = payload.session_id or str(uuid.uuid4())
    if not SESSION_ID_RE.match(sid):
        raise HTTPException(400, "session_id tidak valid (huruf/angka . _ : -, maks 128).")
    assert session_store is not None

    async with get_session_lock(rec.slug, sid):
        session = await session_store.get(rec.slug, sid) or Session(rec.slug, sid)
        try:
            rid = session.release if session.release in rec.release_ids() else rec.pick_release(sid)
            engine = rec.get_engine(rid)
        except LookupError as e:
            raise HTTPException(503, str(e))
        except (KeyError, SpecError):
            raise HTTPException(503, "Release agent tidak dapat dimuat.")
        session.release = rid
        try:
            result = await engine.run_turn(session, payload.message)
        except LLMUnavailable as e:
            raise HTTPException(503, str(e))
        except LLMError as e:
            raise HTTPException(502, str(e))
        await session_store.put(session)

    return InvokeResponse(session_id=sid, agent_id=engine.agent_id, agent_slug=rec.slug, release=rid,
                          response=result.text, current_node=engine.entry_node, status=result.status,
                          turn_count=session.turn_count, tool_calls=result.tool_calls)


if __name__ == "__main__":
    print("=" * 60)
    print(f" Agent Runtime v3 di {HOST}:{PORT}  (env: {RUNTIME_ENVIRONMENT})")
    print(f" DEPLOY_SECRET : {'terpasang' if DEPLOY_SECRET else 'BELUM DISET'}")
    print(f" Mode tanpa auth (dev): {ALLOW_UNAUTHENTICATED}")
    print("=" * 60)
    uvicorn.run(app, host=HOST, port=PORT, workers=1)
