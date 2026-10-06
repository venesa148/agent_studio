"use client";

import React, { useState } from "react";
import {
  X,
  Globe,
  Upload,
  Link as LinkIcon,
  FileCode,
  CheckSquare,
  Square,
  ShieldCheck,
  ChevronDown,
  Info,
} from "lucide-react";

interface EndpointItem {
  id: string;
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  operationId: string;
  summary: string;
  selected: boolean;
}

const AVAILABLE_SECRETS = [
  "HOSPITAL_API_KEY",
  "BPJS_SERVICE_SECRET",
  "OPENROUTER_SECRET",
  "API_GATEWAY_TOKEN",
];

const SAMPLE_ENDPOINTS: EndpointItem[] = [
  {
    id: "ep-1",
    method: "GET",
    path: "/hospitals",
    operationId: "search_hospitals",
    summary: "Cari daftar rumah sakit berdasarkan wilayah",
    selected: true, // GET default checked
  },
  {
    id: "ep-2",
    method: "GET",
    path: "/hospitals/{id}",
    operationId: "get_hospital",
    summary: "Ambil detail spesifik faskes rumah sakit",
    selected: true, // GET default checked
  },
  {
    id: "ep-3",
    method: "POST",
    path: "/referrals",
    operationId: "create_referral",
    summary: "Buat tiket rujukan baru untuk pasien",
    selected: false, // POST default unchecked
  },
  {
    id: "ep-4",
    method: "DELETE",
    path: "/hospitals/{id}",
    operationId: "delete_hospital",
    summary: "Hapus catatan rumah sakit dari direktori",
    selected: false, // DELETE default unchecked
  },
];

interface ImportOpenApiModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveTools: (sourceData: any, importedTools: any[]) => void;
}

export function ImportOpenApiModal({
  isOpen,
  onClose,
  onSaveTools,
}: ImportOpenApiModalProps) {
  const [sourceType, setSourceType] = useState<"url" | "upload" | "paste">("url");
  const [name, setName] = useState("hospital-api");
  const [specUrl, setSpecUrl] = useState("https://api.hospital.id/v1/openapi.json");
  const [pastedSpec, setPastedSpec] = useState("");
  const [fileName, setFileName] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.hospital.id/v1");
  const [prefix, setPrefix] = useState("hosp_");
  const [auth, setAuth] = useState<"No credential" | "Bearer token" | "API Key">(
    "Bearer token"
  );
  const [secretName, setSecretName] = useState(AVAILABLE_SECRETS[0]);
  const [docs, setDocs] = useState("");

  const [endpoints, setEndpoints] = useState<EndpointItem[]>(SAMPLE_ENDPOINTS);

  if (!isOpen) return null;

  const toggleEndpoint = (id: string) => {
    setEndpoints((prev) =>
      prev.map((ep) => (ep.id === id ? { ...ep, selected: !ep.selected } : ep))
    );
  };

  const handleSelectAllGet = () => {
    setEndpoints((prev) =>
      prev.map((ep) => (ep.method === "GET" ? { ...ep, selected: true } : ep))
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const selectedEndpoints = endpoints.filter((ep) => ep.selected);
    if (selectedEndpoints.length === 0) return;

    const sourceData = {
      id: name.toLowerCase().replace(/[^a-z0-9]/g, "-"),
      name: name.trim(),
      baseUrl: baseUrl.trim(),
      prefix: prefix.trim(),
      auth: auth,
      secretName: auth !== "No credential" ? secretName : null,
      docs: docs.trim(),
    };

    const importedTools = selectedEndpoints.map((ep) => ({
      id: `openapi_${sourceData.id}_${prefix}${ep.operationId}`,
      name: `${prefix}${ep.operationId}`,
      description: ep.summary,
      source: "OPENAPI",
      sourceId: sourceData.id,
      auth: auth === "No credential" ? "platform" : secretName,
      health: "ok",
      usedBy: "0 agent",
      config: {
        method: ep.method,
        path: ep.path,
        baseUrl: baseUrl,
      },
    }));

    onSaveTools(sourceData, importedTools);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-3xl w-full my-8 max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <Globe className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Import OpenAPI / Swagger
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-1 max-w-xl leading-relaxed">
              Setiap endpoint API yang dicentang akan otomatis didaftarkan menjadi tool mandiri di Registry.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
          <form id="openapi-import-form" onSubmit={handleSubmit} className="space-y-4">
            {/* Field: Name */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="hospital-api"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs font-mono"
                required
              />
              <p className="text-[11px] text-slate-400 mt-0.5">
                Nama sumber API, misalnya <code className="text-slate-600">hospital-api</code>.
              </p>
            </div>

            {/* Spec Source Switcher */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1.5">
                Spec Source
              </label>
              <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl mb-2.5">
                <button
                  type="button"
                  onClick={() => setSourceType("url")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === "url"
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <LinkIcon className="w-3.5 h-3.5" />
                  <span>URL Spec</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceType("upload")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === "upload"
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>Upload File</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceType("paste")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all ${
                    sourceType === "paste"
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5" />
                  <span>Paste JSON/YAML</span>
                </button>
              </div>

              {sourceType === "url" && (
                <input
                  type="url"
                  value={specUrl}
                  onChange={(e) => setSpecUrl(e.target.value)}
                  placeholder="https://api.example.com/openapi.json"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                />
              )}

              {sourceType === "upload" && (
                <div className="border border-dashed border-slate-300 rounded-xl p-4 text-center cursor-pointer hover:bg-slate-50">
                  <Upload className="w-5 h-5 mx-auto text-slate-400 mb-1" />
                  <span className="text-slate-600 font-medium">
                    {fileName || "Klik untuk upload file .json atau .yaml"}
                  </span>
                  <input
                    type="file"
                    accept=".json,.yaml,.yml"
                    className="hidden"
                    id="spec-upload-input"
                    onChange={(e) => {
                      if (e.target.files?.[0]) setFileName(e.target.files[0].name);
                    }}
                  />
                  <label htmlFor="spec-upload-input" className="block text-[11px] text-blue-600 mt-1 cursor-pointer">
                    Pilih file
                  </label>
                </div>
              )}

              {sourceType === "paste" && (
                <textarea
                  rows={4}
                  value={pastedSpec}
                  onChange={(e) => setPastedSpec(e.target.value)}
                  placeholder="Tempelkan OpenAPI JSON atau YAML di sini..."
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                />
              )}
            </div>

            {/* Base URL & Tool Name Prefix */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  Base URL
                </label>
                <input
                  type="url"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.example.com/v1"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  Tool Name Prefix (Opsional)
                </label>
                <input
                  type="text"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value)}
                  placeholder="hosp_"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                />
              </div>
            </div>

            {/* Auth & Secret Name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  Auth
                </label>
                <div className="relative">
                  <select
                    value={auth}
                    onChange={(e) =>
                      setAuth(e.target.value as "No credential" | "Bearer token" | "API Key")
                    }
                    className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs"
                  >
                    <option value="No credential">No credential</option>
                    <option value="Bearer token">Bearer token</option>
                    <option value="API Key">API Key</option>
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>

              {auth !== "No credential" && (
                <div>
                  <label className="block font-semibold text-slate-800 mb-1">
                    Secret Name
                  </label>
                  <div className="relative">
                    <select
                      value={secretName}
                      onChange={(e) => setSecretName(e.target.value)}
                      className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs font-mono"
                    >
                      {AVAILABLE_SECRETS.map((sec) => (
                        <option key={sec} value={sec}>
                          {sec}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>
              )}
            </div>

            {/* Preview & Selection of Endpoints */}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-slate-900">
                    Preview Endpoints ({endpoints.filter((e) => e.selected).length}/{endpoints.length} terpilih)
                  </h4>
                  <p className="text-[11px] text-slate-400">
                    Endpoint GET otomatis dicentang. POST/PUT/DELETE dinonaktifkan secara default untuk keamanan operasi tulis.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleSelectAllGet}
                  className="text-blue-600 hover:text-blue-800 text-[11px] font-semibold"
                >
                  Pilih Semua GET
                </button>
              </div>

              <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden bg-white">
                {endpoints.map((ep) => (
                  <label
                    key={ep.id}
                    className="p-3 flex items-start gap-3 hover:bg-slate-50/70 transition-colors cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={ep.selected}
                      onChange={() => toggleEndpoint(ep.id)}
                      className="mt-1 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
                    />

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono ${
                            ep.method === "GET"
                              ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                              : ep.method === "POST"
                              ? "bg-blue-50 text-blue-700 border border-blue-200"
                              : "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}
                        >
                          {ep.method}
                        </span>

                        <span className="font-mono text-slate-900 font-semibold">
                          {ep.path}
                        </span>

                        <span className="text-slate-400">→</span>

                        <span className="font-mono text-blue-600 font-semibold bg-blue-50/60 px-1.5 py-0.2 rounded border border-blue-100">
                          {prefix}{ep.operationId}
                        </span>
                      </div>

                      <p className="text-[11px] text-slate-500 mt-1">
                        {ep.summary}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-2 shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 text-xs font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="openapi-import-form"
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors shadow-2xs"
          >
            Import {endpoints.filter((e) => e.selected).length} Tools
          </button>
        </div>
      </div>
    </div>
  );
}
