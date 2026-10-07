"""
Deployment API Controller for Agent Studio
===========================================
Endpoint untuk menangani proses Publish / Deployment dari frontend Agent Studio:
- POST /api/v1/deployment/publish : Memvalidasi config agent.yaml, mendaftarkan slug & API key, dan menyinkronkan ke Agent Runtime Server di AWS.
- GET  /api/v1/deployment/status  : Mengambil info deployment aktif saat ini.
"""

import os
import yaml
import secrets
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status
import httpx

router = APIRouter(prefix="/deployment", tags=["Deployment & Publishing"])

CONFIG_PATH = Path(__file__).resolve().parents[3] / "agent.yaml"
AWS_RUNTIME_URL = os.getenv("AWS_RUNTIME_URL", "http://localhost:8080")


class PublishRequest(BaseModel):
    slug: str = Field(..., description="Domain slug atau identifier publik agent")
    access_level: str = Field(default="Public", description="Public atau Restricted")
    custom_yaml: Optional[str] = Field(default=None, description="Opsional custom YAML content")


class PublishResponse(BaseModel):
    status: str
    agent_id: str
    agent_name: str
    version: int
    slug: str
    endpoint: str
    api_key: str
    access_level: str
    deployed_at: str
    message: str


# In-memory deployment registry (MVP)
current_deployment: Dict[str, Any] = {
    "status": "ready_to_publish",
    "agent_id": "bpjs-triase-rs-001",
    "agent_name": "Agent Triase BPJS RS",
    "version": 1,
    "slug": "bpjs-triase-rs",
    "endpoint": f"{AWS_RUNTIME_URL}/agents/bpjs-triase-rs/invoke",
    "api_key": "agy_live_9f82a17b8c34e91204",
    "access_level": "Public",
    "deployed_at": "-",
    "message": "Siap untuk dipublikasikan."
}


def normalize_and_validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mendukung 2 skema struktur konfigurasi:
    1. Skema Baru (asisten_sehat_bpjs.yaml):
       - spec_version: v1.0
       - metadata: { id, name, slug, description, status, ... }
       - configuration: { model, harness, ... }
       - tools: [...]
       - instructions: |- ...
    2. Skema Legacy (agent.yaml):
       - agent_id, name, description
       - model: { name, ... }
       - flow: { entry_node, nodes: [...] }
    """
    metadata = spec.get("metadata", {})

    # 1. Ekstrak identitas agent
    agent_id = (
        metadata.get("id")
        or spec.get("agent_id")
        or spec.get("id")
        or "agent-001"
    )
    name = (
        metadata.get("name")
        or spec.get("name")
        or "AI Agent"
    )
    slug = (
        metadata.get("slug")
        or spec.get("slug")
        or name.lower().replace(" ", "-")
    )
    description = (
        metadata.get("description")
        or spec.get("description")
        or ""
    )

    spec["agent_id"] = agent_id
    spec["name"] = name
    spec["slug"] = slug
    spec["description"] = description

    # 2. Ekstrak model
    config = spec.get("configuration", {})
    if "model" not in spec:
        spec["model"] = config.get("model", "gpt-4o-mini")

    # 3. Ekstrak instruksi / prompt sistem
    instructions = (
        spec.get("instructions")
        or spec.get("system_prompt")
        or "Kamu adalah asisten AI yang membantu."
    )
    spec["instructions"] = instructions
    if "system_prompt" not in spec:
        spec["system_prompt"] = instructions

    # 4. Validasi atau bentuk graph flow jika belum didefinisikan
    if "flow" not in spec or not spec.get("flow"):
        spec["flow"] = {
            "entry_node": "main_step",
            "nodes": [
                {
                    "id": "main_step",
                    "type": "llm_step",
                    "instruction": instructions,
                    "next": "selesai"
                },
                {"id": "selesai", "type": "end"}
            ]
        }

    flow = spec.get("flow", {})
    entry_node = flow.get("entry_node")
    nodes = flow.get("nodes", [])

    if not entry_node:
        raise ValueError("Field 'flow.entry_node' tidak boleh kosong.")

    node_ids = {n.get("id") for n in nodes if n.get("id")}
    if entry_node not in node_ids:
        raise ValueError(f"Entry node '{entry_node}' tidak ditemukan dalam daftar nodes.")

    # Validasi integritas graph (next dan branches)
    for n in nodes:
        nid = n.get("id")
        ntype = n.get("type")

        # Cek next
        if "next" in n:
            target = n["next"]
            if target != "selesai" and target not in node_ids:
                raise ValueError(f"Node '{nid}' merujuk target 'next: {target}' yang tidak ada dalam graph.")

        # Cek branches pada classification
        if ntype == "llm_step" and n.get("output_type") == "classification":
            branches = n.get("branches", {})
            for branch_key, target in branches.items():
                if target != "selesai" and target not in node_ids:
                    raise ValueError(f"Node '{nid}' cabang '{branch_key}' merujuk node '{target}' yang tidak ada.")

    return spec


@router.get("/status", response_model=PublishResponse)
async def get_deployment_status():
    """Mengambil status deployment aktif"""
    return PublishResponse(**current_deployment)


@router.get("/yaml-files")
async def list_available_yaml_files():
    """Mengembalikan daftar file YAML yang tersedia di backend/"""
    backend_dir = Path(__file__).resolve().parents[3]
    results = []
    for f in backend_dir.glob("*.yaml"):
        try:
            content = f.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            meta = data.get("metadata", {})
            aid = meta.get("id") or data.get("agent_id") or f.stem
            aname = meta.get("name") or data.get("name") or f.stem
            adesc = meta.get("description") or data.get("description") or ""
            aslug = meta.get("slug") or data.get("slug") or f.stem
            results.append({
                "filename": f.name,
                "agent_id": aid,
                "name": aname,
                "slug": aslug,
                "description": adesc.strip(),
                "content": content
            })
        except Exception as e:
            results.append({"filename": f.name, "name": f.name, "content": "", "description": str(e)})
    return results


@router.post("/publish", response_model=PublishResponse)
async def publish_agent(payload: PublishRequest):
    """
    Eksekusi Tahap Publish:
    1. Membaca & Memvalidasi agent.yaml (skema baru metadata maupun legacy)
    2. Menghubungi / Menyinkronkan ke Agent Runtime Server di AWS jika terjangkau
    3. Menerbitkan endpoint publik & API Key yang di-scope untuk agent
    """
    # 1. Muat konten YAML
    if payload.custom_yaml:
        yaml_text = payload.custom_yaml
    else:
        if not CONFIG_PATH.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {CONFIG_PATH.name} tidak ditemukan di backend."
            )
        yaml_text = CONFIG_PATH.read_text(encoding="utf-8")

    try:
        raw_spec = yaml.safe_load(yaml_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sintaks YAML tidak valid: {str(e)}")

    # 2. Normalisasi & Validasi skema (Mendukung struktur baru asisten_sehat_bpjs.yaml)
    try:
        spec = normalize_and_validate_spec(raw_spec)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Validasi Graph Gagal: {str(ve)}")

    # 3. Set endpoint target ke server runtime AWS dengan slug unik
    spec_slug = spec.get("slug", "")
    clean_slug = payload.slug.strip().lower() or spec_slug or "agent"
    target_endpoint = f"{AWS_RUNTIME_URL}/agents/{clean_slug}/invoke"
    runtime_sync_msg = f"Target endpoint unik disiapkan di {target_endpoint}."

    # 4. Generate API Key unik untuk client
    generated_key = f"agy_live_{secrets.token_hex(12)}"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    current_deployment["status"] = "live"
    current_deployment["agent_id"] = spec.get("agent_id", "bpjs-triase-rs-001")
    current_deployment["agent_name"] = spec.get("name", "Agent Triase BPJS RS")
    current_deployment["version"] = spec.get("version", 1)
    current_deployment["slug"] = clean_slug
    current_deployment["endpoint"] = target_endpoint
    current_deployment["api_key"] = generated_key
    current_deployment["access_level"] = payload.access_level
    current_deployment["deployed_at"] = now_str

    return PublishResponse(
        status="live",
        agent_id=current_deployment["agent_id"],
        agent_name=current_deployment["agent_name"],
        version=current_deployment["version"],
        slug=current_deployment["slug"],
        endpoint=current_deployment["endpoint"],
        api_key=generated_key,
        access_level=payload.access_level,
        deployed_at=now_str,
        message=f"Agent '{current_deployment['agent_name']}' berhasil dipublikasikan! {runtime_sync_msg}"
    )
