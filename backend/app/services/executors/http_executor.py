"""
Generic HTTP Executor: Eksekutor dinamis murni untuk segala jenis REST API tool.
100% Dinamis tanpa hardcode nama tool:
- Resolusi dinamis endpoint & placeholder URL ({id}, {city}, dll).
- Otomatis memetakan query params untuk GET dan JSON body untuk POST/PUT/PATCH.
- Header, autentikasi, timeout, dan ekstraksi response fields sepenuhnya digerakkan oleh metadata spesifikasi.
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional
from urllib.parse import quote
import httpx

logger = logging.getLogger("generic_http_executor")
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z0-9_-]+)\}")


class GenericHttpExecutor:
    """
    Eksekutor HTTP serbaguna yang mengeksekusi request berdasarkan konfigurasi deklaratif
    tanpa ketergantungan pada nama fungsi atau domain tertentu.
    """

    @staticmethod
    async def execute(
        implementation: Dict[str, Any],
        params: Dict[str, Any],
        api_base: Optional[str] = None,
        source_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Mengeksekusi HTTP request secara dinamis berdasarkan kamus implementation:
        - implementation['url']: URL lengkap atau template seperti '{api_base}/api/v1/bookings/{id}'
        - implementation['method']: 'GET', 'POST', 'PUT', 'DELETE', dll (default: 'GET')
        - implementation['headers']: Dict header kustom
        - implementation['auth']: Konfigurasi auth deklaratif
        - implementation['timeout_ms']: Timeout dalam milidetik (default: 8000)
        - implementation['response']: Konfigurasi ekstraksi respon (e.g. {'select': ['data', 'status']})
        """
        start_time = time.time()
        method = (implementation.get("method") or "GET").upper()
        raw_url = implementation.get("url") or ""

        if not raw_url:
            return {
                "status": "error",
                "error_type": "CONFIGURATION_ERROR",
                "message": "URL implementation tidak ditemukan pada spesifikasi tool.",
            }

        # 1. Resolusi dinamis placeholder {api_base}
        target_url = raw_url
        if "{api_base}" in target_url:
            base = (api_base or "").rstrip("/")
            target_url = target_url.replace("{api_base}", base)

        # 2. Substitusi dinamis path parameters: {param_name} -> quote(value)
        used_param_keys = set()
        
        # Cek apakah ada mapping alias parameter (misal: referral_id -> referral_no)
        param_mapping = implementation.get("param_mapping") or {}
        normalized_params = dict(params)
        for orig_key, alias_key in param_mapping.items():
            if orig_key in normalized_params and alias_key not in normalized_params:
                normalized_params[alias_key] = normalized_params[orig_key]

        for match in PLACEHOLDER_PATTERN.finditer(target_url):
            key = match.group(1)
            if key in normalized_params:
                val = str(normalized_params[key])
                target_url = target_url.replace(f"{{{key}}}", quote(val, safe=""))
                used_param_keys.add(key)

        # 3. Headers & Autentikasi Dinamis
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "AgentStudio-GenericHttpExecutor/1.0",
        }
        if implementation.get("headers"):
            headers.update(implementation["headers"])

        auth_config = implementation.get("auth") or {}
        if auth_config.get("in") == "header" and auth_config.get("name") and auth_config.get("secret"):
            headers[auth_config["name"]] = auth_config["secret"]

        # 4. Pemisahan Parameter (Query vs Body)
        # Parameter yang belum terpakai di path URL akan dialirkan:
        # - Method GET/HEAD: sebagai Query Parameter
        # - Method POST/PUT/PATCH/DELETE: sebagai JSON Body
        remaining_params = {
            k: v for k, v in normalized_params.items()
            if k not in used_param_keys and v is not None and not k.startswith("_")
        }

        query_params: Optional[Dict[str, Any]] = None
        json_body: Optional[Dict[str, Any]] = None

        if method in ("GET", "HEAD"):
            query_params = remaining_params if remaining_params else None
        else:
            headers["Content-Type"] = "application/json"
            # Jika implementation menentukan body_template khusus
            body_template = implementation.get("body_template")
            if body_template and isinstance(body_template, dict):
                json_body = {
                    k: (normalized_params.get(v.strip("{}")) if isinstance(v, str) and v.startswith("{") else v)
                    for k, v in body_template.items()
                }
            else:
                json_body = remaining_params if remaining_params else normalized_params

        timeout_sec = float(implementation.get("timeout_ms", 8000)) / 1000.0

        # 5. Eksekusi HTTP Call dengan httpx
        try:
            async with httpx.AsyncClient(timeout=timeout_sec, follow_redirects=True) as client:
                req_kwargs: Dict[str, Any] = {"headers": headers}
                if query_params:
                    req_kwargs["params"] = query_params
                if json_body is not None and method not in ("GET", "HEAD"):
                    req_kwargs["json"] = json_body

                resp = await client.request(method, target_url, **req_kwargs)

                # Ekstraksi response data
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = resp.text

                # Seleksi field jika dikonfigurasi
                select_fields = implementation.get("response", {}).get("select")
                if select_fields and isinstance(resp_data, dict):
                    resp_data = {k: resp_data.get(k) for k in select_fields if k in resp_data}

                if resp.status_code >= 400:
                    return {
                        "status": "error",
                        "error_type": "HTTP_ERROR",
                        "status_code": resp.status_code,
                        "_endpoint": target_url,
                        "_source": source_label or f"Generic HTTP ({method})",
                        "message": f"Server eksternal mengembalikan HTTP {resp.status_code}.",
                        "details": resp_data,
                    }

                # Bungkus response
                result: Dict[str, Any] = resp_data if isinstance(resp_data, dict) else {"data": resp_data}
                result["_endpoint"] = target_url
                result["_source"] = source_label or f"Generic HTTP ({method})"
                return result

        except httpx.TimeoutException:
            logger.warning(f"Timeout saat menghubungi endpoint {target_url}")
            return {
                "status": "error",
                "error_type": "TIMEOUT",
                "_endpoint": target_url,
                "_source": source_label or "External Service (Timeout)",
                "message": f"Endpoint '{target_url}' tidak merespons dalam batas waktu {timeout_sec} detik.",
            }
        except httpx.ConnectError as exc:
            logger.warning(f"Gagal koneksi ke {target_url}: {exc}")
            return {
                "status": "error",
                "error_type": "SERVICE_UNAVAILABLE",
                "_endpoint": target_url,
                "_source": source_label or "External Service (Offline)",
                "message": f"Layanan pada '{target_url}' sedang tidak dapat dijangkau / offline.",
            }
        except Exception as exc:
            logger.error(f"Eksepsi HTTP tidak terduga pada {target_url}: {exc}")
            return {
                "status": "error",
                "error_type": "UNEXPECTED_ERROR",
                "_endpoint": target_url,
                "_source": source_label or "External Service Error",
                "message": f"Terjadi kesalahan saat memanggil API: {str(exc)}",
            }
