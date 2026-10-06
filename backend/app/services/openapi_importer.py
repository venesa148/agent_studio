import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import HTTPException


class OpenAPIImporter:
    """Turns OpenAPI operations into safe, registry-owned tool records."""

    @staticmethod
    def _tool_name(prefix: str, operation: Dict[str, Any], method: str, path: str) -> str:
        raw = operation.get("operationId") or f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}"
        name = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_").lower()
        return f"{prefix}_{name}" if prefix else name

    @staticmethod
    def _schema(operation: Dict[str, Any], path_item: Dict[str, Any], server_url: str, method: str, path: str) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}
        required: List[str] = []
        parameter_locations: Dict[str, str] = {}
        for parameter in [*path_item.get("parameters", []), *operation.get("parameters", [])]:
            if not isinstance(parameter, dict) or not parameter.get("name"):
                continue
            name = parameter["name"]
            properties[name] = parameter.get("schema", {"type": "string"})
            if parameter.get("description"):
                properties[name]["description"] = parameter["description"]
            parameter_locations[name] = parameter.get("in", "query")
            if parameter.get("required"):
                required.append(name)

        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {}) if isinstance(request_body, dict) else {}
        body_schema = next((value.get("schema") for value in content.values() if isinstance(value, dict) and value.get("schema")), None)
        if body_schema:
            properties["body"] = body_schema
            parameter_locations["body"] = "body"
            if request_body.get("required"):
                required.append("body")

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "x-openapi": {
                "server_url": server_url,
                "method": method.upper(),
                "path": path,
                "parameter_locations": parameter_locations,
            },
        }

    @classmethod
    async def fetch_operations(cls, spec_url: str, prefix: str = "") -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
                response = await client.get(spec_url, headers={"Accept": "application/json, application/yaml"})
                response.raise_for_status()
                spec = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"OpenAPI document could not be loaded as JSON: {exc}") from exc

        if not isinstance(spec, dict) or not (spec.get("openapi") or spec.get("swagger")) or not isinstance(spec.get("paths"), dict):
            raise HTTPException(status_code=422, detail="The URL does not contain a valid OpenAPI JSON document.")

        servers = spec.get("servers", [])
        if servers and isinstance(servers[0], dict) and servers[0].get("url"):
            server_url = urljoin(spec_url, servers[0]["url"])
        elif spec.get("swagger"):
            parsed = urlsplit(spec_url)
            server_url = f"{(spec.get('schemes') or [parsed.scheme])[0]}://{spec.get('host') or parsed.netloc}{spec.get('basePath', '')}"
        else:
            parsed = urlsplit(spec_url)
            server_url = f"{parsed.scheme}://{parsed.netloc}"

        operations: List[Dict[str, Any]] = []
        for path, path_item in spec["paths"].items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"} or not isinstance(operation, dict):
                    continue
                operations.append({
                    "name": cls._tool_name(prefix, operation, method, path),
                    "description": operation.get("summary") or operation.get("description") or f"{method.upper()} {path}",
                    "input_schema": cls._schema(operation, path_item, server_url, method, path),
                })
        if not operations:
            raise HTTPException(status_code=422, detail="No callable operations were found in this OpenAPI document.")
        return operations
