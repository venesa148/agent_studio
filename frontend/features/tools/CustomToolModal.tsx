"use client";

import React, { useState } from "react";
import {
  X,
  Wrench,
  Plus,
  Trash2,
  Play,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sliders,
  ChevronDown,
  Code2,
} from "lucide-react";

interface ParamField {
  id: string;
  name: string;
  type: "string" | "number" | "boolean" | "object";
  required: boolean;
  description: string;
}

const REGISTERED_BACKEND_FUNCTIONS = [
  { id: "knowledge_search", label: "knowledge_search(query)" },
  { id: "search_hospital", label: "search_hospital(city, bpjs)" },
  { id: "get_hospital_detail", label: "get_hospital_detail(hospital_id)" },
  { id: "check_bpjs", label: "check_bpjs(hospital_id)" },
  { id: "find_specialist", label: "find_specialist(specialty, city)" },
  { id: "get_referral_status", label: "get_referral_status(referral_id)" },
];

const AVAILABLE_SECRETS = [
  "HOSPITAL_API_KEY",
  "BPJS_SERVICE_SECRET",
  "OPENROUTER_SECRET",
];

interface CustomToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveTool: (toolData: any) => void;
}

export function CustomToolModal({
  isOpen,
  onClose,
  onSaveTool,
}: CustomToolModalProps) {
  // General Fields
  const [name, setName] = useState("check_bpjs");
  const [description, setDescription] = useState(
    "Cek apakah rumah sakit menerima layanan BPJS Kesehatan dan rawat jalan."
  );
  const [enabled, setEnabled] = useState(true);
  const [auth, setAuth] = useState<"none" | "bearer" | "api_key">("none");
  const [secretName, setSecretName] = useState(AVAILABLE_SECRETS[0]);

  // Implementation Type
  const [implType, setImplType] = useState<"backend_function" | "http_request">(
    "backend_function"
  );
  const [selectedBackendFn, setSelectedBackendFn] = useState(
    REGISTERED_BACKEND_FUNCTIONS[3].id
  );

  // HTTP Request fields (Phase 2 preview)
  const [httpMethod, setHttpMethod] = useState("GET");
  const [httpUrlTemplate, setHttpUrlTemplate] = useState(
    "https://api.rs.com/hospitals/{hospital_id}"
  );
  const [httpTimeout, setHttpTimeout] = useState(10);

  // Dynamic Parameters
  const [parameters, setParameters] = useState<ParamField[]>([
    {
      id: "param-1",
      name: "hospital_id",
      type: "string",
      required: true,
      description: "Kode ID unik faskes rumah sakit",
    },
  ]);

  // Test Panel States
  const [testInputs, setTestInputs] = useState<Record<string, string>>({
    hospital_id: "RS-01",
  });
  const [isTesting, setIsTesting] = useState(false);
  const [testOutput, setTestOutput] = useState<any>(null);
  const [testStatus, setTestStatus] = useState<"idle" | "success" | "error">(
    "idle"
  );

  if (!isOpen) return null;

  const handleAddParam = () => {
    const newId = `param-${Date.now()}`;
    setParameters((prev) => [
      ...prev,
      {
        id: newId,
        name: "",
        type: "string",
        required: false,
        description: "",
      },
    ]);
  };

  const handleRemoveParam = (id: string) => {
    setParameters((prev) => prev.filter((p) => p.id !== id));
  };

  const handleParamChange = (id: string, field: keyof ParamField, val: any) => {
    setParameters((prev) =>
      prev.map((p) => (p.id === id ? { ...p, [field]: val } : p))
    );
  };

  const handleRunTest = () => {
    setIsTesting(true);
    setTestOutput(null);
    setTestStatus("idle");

    setTimeout(() => {
      setIsTesting(false);
      setTestStatus("success");
      setTestOutput({
        hospital_id: testInputs["hospital_id"] || "RS-01",
        hospital_name: "RS Cipto Mangunkusumo",
        bpjs_active: true,
        quota_available: 14,
        status: "OK",
      });
    }, 800);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const toolPayload = {
      id: `builtin_${name.trim()}`,
      name: name.trim().replace(/\s+/g, "_"),
      description: description.trim(),
      source: implType === "backend_function" ? "BUILTIN" : "BUILTIN_HTTP",
      sourceType: implType,
      auth: auth === "none" ? "platform" : secretName,
      health: testStatus === "success" ? "ok" : "unknown",
      usedBy: "0 agent",
      enabled: enabled,
      config:
        implType === "backend_function"
          ? { functionName: selectedBackendFn }
          : {
              method: httpMethod,
              urlTemplate: httpUrlTemplate,
              timeout: httpTimeout,
            },
      parameters: parameters,
    };

    onSaveTool(toolPayload);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-3xl w-full my-8 max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <Wrench className="w-5 h-5 text-emerald-600" />
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Custom Built-in Tool
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-1 max-w-xl leading-relaxed">
              Definisikan function mandiri dengan parameter terstruktur dan validasi panel test sebelum masuk allowlist.
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
          <form id="custom-tool-form" onSubmit={handleSubmit} className="space-y-4">
            {/* Name & Enabled Toggle */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-start">
              <div className="sm:col-span-2">
                <label className="block font-semibold text-slate-800 mb-1">
                  Name (tanpa spasi) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value.replace(/\s+/g, "_"))}
                  placeholder="check_bpjs"
                  className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  Status
                </label>
                <button
                  type="button"
                  onClick={() => setEnabled(!enabled)}
                  className={`w-full py-2 px-3 rounded-xl border text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                    enabled
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-slate-200 bg-slate-50 text-slate-500"
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      enabled ? "bg-emerald-500" : "bg-slate-400"
                    }`}
                  />
                  <span>{enabled ? "Enabled (ON)" : "Disabled (OFF)"}</span>
                </button>
              </div>
            </div>

            {/* Description for LLM */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Description (Kapan tool dipakai oleh LLM) <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Cek apakah faskes RS menerima BPJS..."
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs"
                required
              />
            </div>

            {/* Implementation Section (Pilih satu: Backend function vs HTTP request) */}
            <div className="pt-2 border-t border-slate-100">
              <label className="block font-semibold text-slate-800 mb-1.5">
                Implementation Mode
              </label>
              <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl mb-3">
                <button
                  type="button"
                  onClick={() => setImplType("backend_function")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    implType === "backend_function"
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  Backend function (FastAPI Code)
                </button>
                <button
                  type="button"
                  onClick={() => setImplType("http_request")}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    implType === "http_request"
                      ? "bg-white text-slate-900 shadow-2xs"
                      : "text-slate-500 hover:text-slate-800"
                  }`}
                >
                  HTTP request (Fase 2)
                </button>
              </div>

              {implType === "backend_function" ? (
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Registered FastAPI Function
                  </label>
                  <div className="relative">
                    <select
                      value={selectedBackendFn}
                      onChange={(e) => setSelectedBackendFn(e.target.value)}
                      className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                    >
                      {REGISTERED_BACKEND_FUNCTIONS.map((fn) => (
                        <option key={fn.id} value={fn.id}>
                          {fn.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Fungsi internal siap pakai yang telah didefinisikan pada backend platform.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 p-3.5 rounded-xl border border-slate-200 bg-slate-50/50">
                  <div className="grid grid-cols-4 gap-2">
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Method</label>
                      <select
                        value={httpMethod}
                        onChange={(e) => setHttpMethod(e.target.value)}
                        className="w-full px-2 py-1.5 rounded-lg border border-slate-200 bg-white font-mono text-xs"
                      >
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="DELETE">DELETE</option>
                      </select>
                    </div>
                    <div className="col-span-3">
                      <label className="block font-semibold text-slate-700 mb-1">
                        URL Template dengan Placeholder
                      </label>
                      <input
                        type="text"
                        value={httpUrlTemplate}
                        onChange={(e) => setHttpUrlTemplate(e.target.value)}
                        placeholder="https://api.rs.com/hospitals/{hospital_id}"
                        className="w-full px-3 py-1.5 rounded-lg border border-slate-200 font-mono text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Dynamic Parameters Builder */}
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-slate-900">
                    Parameters ({parameters.length})
                  </h4>
                  <p className="text-[11px] text-slate-400">
                    Definisikan input schema fungsi (otomatis dikonversi ke JSON Schema Pydantic).
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddParam}
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-[11px] font-semibold"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>+ Tambah Parameter</span>
                </button>
              </div>

              <div className="space-y-2">
                {parameters.map((param, index) => (
                  <div
                    key={param.id}
                    className="p-3 rounded-xl border border-slate-200 bg-white grid grid-cols-1 sm:grid-cols-12 gap-2 items-center"
                  >
                    <div className="sm:col-span-4">
                      <input
                        type="text"
                        value={param.name}
                        onChange={(e) =>
                          handleParamChange(param.id, "name", e.target.value)
                        }
                        placeholder="nama_param"
                        className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 font-mono text-xs"
                        required
                      />
                    </div>

                    <div className="sm:col-span-3">
                      <select
                        value={param.type}
                        onChange={(e) =>
                          handleParamChange(param.id, "type", e.target.value)
                        }
                        className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-mono"
                      >
                        <option value="string">string</option>
                        <option value="number">number</option>
                        <option value="boolean">boolean</option>
                        <option value="object">object</option>
                      </select>
                    </div>

                    <div className="sm:col-span-4">
                      <input
                        type="text"
                        value={param.description}
                        onChange={(e) =>
                          handleParamChange(param.id, "description", e.target.value)
                        }
                        placeholder="Deskripsi fungsi param"
                        className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs"
                      />
                    </div>

                    <div className="sm:col-span-1 flex items-center justify-between sm:justify-end gap-2">
                      <label title="Wajib diisi" className="flex items-center gap-1 text-[11px] text-slate-500 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={param.required}
                          onChange={(e) =>
                            handleParamChange(param.id, "required", e.target.checked)
                          }
                          className="rounded text-blue-600"
                        />
                        <span className="sm:hidden">Wajib</span>
                      </label>

                      {parameters.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveParam(param.id)}
                          className="text-slate-400 hover:text-rose-600 p-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Panel Test (Uji coba sebelum masuk katalog) */}
            <div className="pt-2 border-t border-slate-100 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-slate-900 flex items-center gap-1.5">
                    <span>Panel Test</span>
                    {testStatus === "success" && (
                      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                        <CheckCircle2 className="w-3 h-3" />
                        Health: OK
                      </span>
                    )}
                  </h4>
                  <p className="text-[11px] text-slate-400">
                    Uji function dengan input contoh untuk memastikan respon valid dan mencegah tool rusak masuk katalog.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleRunTest}
                  disabled={isTesting}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold shadow-2xs"
                >
                  {isTesting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>Run Test</span>
                </button>
              </div>

              {/* Sample Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {parameters.map((p) => (
                  <div key={p.id}>
                    <label className="block text-[11px] font-mono text-slate-600 mb-0.5">
                      {p.name || "param"}:
                    </label>
                    <input
                      type="text"
                      value={testInputs[p.name] || ""}
                      onChange={(e) =>
                        setTestInputs((prev) => ({
                          ...prev,
                          [p.name]: e.target.value,
                        }))
                      }
                      placeholder={`Contoh value ${p.type}`}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-slate-200 font-mono text-xs"
                    />
                  </div>
                ))}
              </div>

              {/* Test Output Console */}
              {testOutput && (
                <div className="p-3 rounded-xl bg-slate-900 text-slate-100 font-mono text-[11px] space-y-1">
                  <div className="flex items-center justify-between text-slate-400 text-[10px] pb-1 border-b border-slate-800">
                    <span>Response Output (200 OK)</span>
                    <span className="text-emerald-400">Health: ok</span>
                  </div>
                  <pre className="overflow-x-auto pt-1">
                    {JSON.stringify(testOutput, null, 2)}
                  </pre>
                </div>
              )}
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
            form="custom-tool-form"
            className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-colors shadow-2xs"
          >
            Save Tool to Catalog
          </button>
        </div>
      </div>
    </div>
  );
}
