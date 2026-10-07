"""
src/registry.py
Katalog Kemampuan (Capabilities Registry) - Mengimplementasikan Tools & Protokol MCP sederhana.
Menyediakan data sumber kebenaran (Source of Truth) untuk rumah sakit dan BPJS.
"""

import json

# ==============================================================================
# DATA DUMMY RUMAH SAKIT & BPJS (Source of Truth)
# Sesuai spesifikasi PRD Halaman 9 (15-20 RS dummy, rujukan BPJS)
# ==============================================================================

HOSPITALS_DB = [
    {
        "id": "RS-01",
        "name": "RSUD Tarakan",
        "city": "Jakarta",
        "type": "Tipe B",
        "bpjs": True,
        "specialties": ["Jantung", "Orthopaedi", "Penyakit Dalam", "IGD 24 Jam"],
        "address": "Jl. Kyai Caringin No.7, Gambir, Jakarta Pusat"
    },
    {
        "id": "RS-02",
        "name": "RS Cipto Mangunkusumo (RSCM)",
        "city": "Jakarta",
        "type": "Tipe A (Rujukan Nasional)",
        "bpjs": True,
        "specialties": ["Orthopaedi", "Rehabilitasi Medik", "Jantung", "Bedah Saraf"],
        "address": "Jl. Diponegoro No.71, Senen, Jakarta Pusat"
    },
    {
        "id": "RS-03",
        "name": "RS Fatmawati",
        "city": "Jakarta",
        "type": "Tipe A",
        "bpjs": True,
        "specialties": ["Orthopaedi", "Rehabilitasi Medik", "Trauma Center"],
        "address": "Jl. RS. Fatmawati Raya, Cilandak, Jakarta Selatan"
    },
    {
        "id": "RS-04",
        "name": "RS Hasan Sadikin",
        "city": "Bandung",
        "type": "Tipe A",
        "bpjs": True,
        "specialties": ["Jantung", "Anak", "Mata", "Orthopaedi"],
        "address": "Jl. Pasteur No.38, Bandung"
    },
    {
        "id": "RS-05",
        "name": "RS Hermina Pasteur",
        "city": "Bandung",
        "type": "Tipe B",
        "bpjs": True,
        "specialties": ["Anak", "Kandungan", "Penyakit Dalam"],
        "address": "Jl. Dr. Djunjunan No.107, Bandung"
    },
    {
        "id": "RS-06",
        "name": "RS Swasta Mitra Kasih (Non-BPJS)",
        "city": "Jakarta",
        "type": "Swasta",
        "bpjs": False,
        "specialties": ["Umum", "Estetika"],
        "address": "Jakarta"
    }
]

PARTICIPANTS_DB = {
    "dicky": {
        "participant_name": "Dicky",
        "nik": "3171012345670001",
        "status": "AKTIF",
        "fktp": "Klinik Pratama Sehat Mandiri (Jakarta Pusat)",
        "card_type": "JKN-KIS PBI"
    },
    "budi": {
        "participant_name": "Budi",
        "nik": "3171012345670002",
        "status": "NON-AKTIF (MENUNGGAK)",
        "fktp": "Puskesmas Kebayoran Baru",
        "card_type": "JKN Mandiri Kelas 1"
    }
}

REFERRALS_DB = {
    "RJ-1001": {
        "referral_id": "RJ-1001",
        "patient_name": "Dicky",
        "status": "DISETUJUI",
        "poli": "Orthopaedi",
        "target_hospital": "RSUD Tarakan",
        "diagnosis_initial": "Suspect Osteoarthritis Genu Dextra (Nyeri Lutut Kanan)",
        "valid_until": "2026-11-30"
    },
    "RJ-1002": {
        "referral_id": "RJ-1002",
        "patient_name": "Budi",
        "status": "MENUNGGU_VERIFIKASI",
        "poli": "Jantung",
        "target_hospital": "RS Hasan Sadikin",
        "diagnosis_initial": "Pemeriksaan Aritmia",
        "valid_until": "2026-10-25"
    }
}

# ==============================================================================
# FUNGSI EKSEKUSI TOOL (Tool Handlers)
# ==============================================================================

def tool_search_hospitals(city: str, bpjs_only: bool = True) -> list[dict]:
    """Mencari rumah sakit berdasarkan kota dan status BPJS."""
    city_lower = city.strip().lower()
    results = []
    for rs in HOSPITALS_DB:
        if city_lower in rs["city"].lower():
            if bpjs_only and not rs["bpjs"]:
                continue
            results.append({
                "id": rs["id"],
                "name": rs["name"],
                "city": rs["city"],
                "type": rs["type"],
                "bpjs": rs["bpjs"],
                "specialties": rs["specialties"]
            })
    return results

def tool_get_participant_status(name: str) -> dict:
    """Mengecek status kepesertaan BPJS pasien berdasarkan nama."""
    name_clean = name.strip().lower()
    for key, data in PARTICIPANTS_DB.items():
        if key in name_clean or data["participant_name"].lower() in name_clean:
            return data
    return {"status": "NOT_FOUND", "message": f"Data peserta BPJS atas nama '{name}' tidak ditemukan."}

def tool_get_referral_status(referral_id: str) -> dict:
    """Mengecek surat rujukan pasien berdasarkan ID rujukan (misal: RJ-1001)."""
    ref_clean = referral_id.strip().upper()
    if ref_clean in REFERRALS_DB:
        return REFERRALS_DB[ref_clean]
    # Sesuai PRD Halaman 9 & 10: RJ-9999 atau id salah harus me-return NOT_FOUND
    return {
        "status": "NOT_FOUND",
        "referral_id": ref_clean,
        "message": f"Surat rujukan dengan kode {ref_clean} tidak terdaftar di sistem faskes BPJS."
    }

# ==============================================================================
# KATALOG REGISTRY & SCHEMA OPENAI (Tools & MCP Definition)
# ==============================================================================

REGISTRY = {
    "search_hospitals": {
        "name": "search_hospitals",
        "category": "Hospital Directory MCP",
        "description": "Mencari fasilitas rumah sakit rekanan BPJS berdasarkan nama kota (contoh: Jakarta, Bandung).",
        "schema": {
            "type": "function",
            "function": {
                "name": "search_hospitals",
                "description": "Mencari fasilitas rumah sakit berdasarkan kota dan dukungan BPJS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "Nama kota yang dicari, misal: Jakarta, Bandung."
                        },
                        "bpjs_only": {
                            "type": "boolean",
                            "description": "Set true untuk hanya menampilkan RS yang menerima BPJS.",
                            "default": True
                        }
                    },
                    "required": ["city"]
                }
            }
        },
        "handler": tool_search_hospitals
    },
    "get_participant_status": {
        "name": "get_participant_status",
        "category": "BPJS / JKN MCP",
        "description": "Mengecek status keaktifan BPJS dan faskes tingkat pertama (FKTP) pasien berdasarkan nama.",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_participant_status",
                "description": "Mengecek keaktifan kartu BPJS dan FKTP terdaftar pasien.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nama pasien atau peserta BPJS (misal: Dicky)."
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        "handler": tool_get_participant_status
    },
    "get_referral_status": {
        "name": "get_referral_status",
        "category": "BPJS / JKN MCP",
        "description": "Memeriksa status surat rujukan BPJS pasien dengan kode rujukan (misal: RJ-1001 atau RJ-9999).",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_referral_status",
                "description": "Memeriksa keabsahan dan status surat rujukan pasien di faskes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "referral_id": {
                            "type": "string",
                            "description": "Nomor rujukan pasien, contoh: RJ-1001, RJ-9999."
                        }
                    },
                    "required": ["referral_id"]
                }
            }
        },
        "handler": tool_get_referral_status
    }
}

def list_capabilities() -> list[dict]:
    """Mengembalikan daftar semua tool yang tersedia di registry untuk dibaca oleh Builder Agent."""
    return [
        {
            "name": tool["name"],
            "category": tool["category"],
            "description": tool["description"]
        }
        for tool in REGISTRY.values()
    ]

def get_tool_schemas(tool_names: list[str]) -> list[dict]:
    """Mengembalikan daftar skema OpenAI Tool Calling untuk tools yang diizinkan saja."""
    schemas = []
    for name in tool_names:
        if name in REGISTRY:
            schemas.append(REGISTRY[name]["schema"])
    return schemas

def execute_tool(tool_name: str, arguments: dict) -> dict | list:
    """Mengeksekusi handler tool dari nama dan parameter yang diminta model."""
    if tool_name not in REGISTRY:
        raise ValueError(f"Tool '{tool_name}' tidak terdaftar di Registry!")
    handler = REGISTRY[tool_name]["handler"]
    return handler(**arguments)
