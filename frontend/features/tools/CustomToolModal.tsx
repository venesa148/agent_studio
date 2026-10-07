"use client";

import React, { useState } from "react";
import {
  X,
  Wrench,
  Plus,
  Trash2,
  ChevronDown,
  CheckCircle2,
  Loader2,
  Play,
} from "lucide-react";

interface ParamField {
  id: string;
  name: string;
  type: "string" | "number" | "boolean" | "object";
  required: boolean;
  description: string;
}

const REGISTERED_BACKEND_FUNCTIONS = [
  { id: "check_bpjs", label: "check_bpjs(hospital_id)" },
  { id: "search_hospital", label: "search_hospital(city, bpjs)" },
  { id: "get_hospital_detail", label: "get_hospital_detail(hospital_id)" },
  { id: "find_specialist", label: "find_specialist(specialty, city)" },
  { id: "get_referral_status", label: "get_referral_status(referral_id)" },
  { id: "knowledge_search", label: "knowledge_search(query)" },
];

interface CustomToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveTool: (toolData: any) => Promise<void>;
}

export function CustomToolModal({
  isOpen,
  onClose,
  onSaveTool,
}: CustomToolModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedBackendFn, setSelectedBackendFn] = useState(
    REGISTERED_BACKEND_FUNCTIONS[0].id
  );

  // Dynamic parameters builder
  const [parameters, setParameters] = useState<ParamField[]>([
    {
      id: "param-1",
      name: "",
      type: "string",
      required: true,
      description: "",
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
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const toolPayload = {
      id: `builtin_${name.trim().toLowerCase().replace(/\s+/g, "_")}`,
      name: name.trim().toLowerCase().replace(/\s+/g, "_"),
      description: description.trim(),
      source: "BUILTIN",
      auth: "platform",
      health: "ok",
      usedBy: "0 agent",
      enabled: true,
      config: {
        functionName: selectedBackendFn,
      },
      parameters: parameters,
    };

    setSaveError(null);
    setIsSaving(true);
    try {
      await onSaveTool(toolPayload);
      onClose();
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Tool tidak dapat disimpan.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wrench className="w-4 h-4 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">
              Create Custom Built-in Tool
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form id="custom-tool-form" onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {/* Tool Name */}
          <div>
            <label className="block font-semibold text-slate-800 mb-1">
              Tool Name <span className="text-rose-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. check_bpjs"
              className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-xs"
              required
            />
            <p className="text-[11px] text-slate-400 mt-0.5">
              Nama fungsi (huruf kecil, gunakan underscore tanpa spasi).
            </p>
          </div>

          {/* Description */}
          <div>
            <label className="block font-semibold text-slate-800 mb-1">
              Description <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Jelaskan fungsi tool ini agar LLM memahami kapan harus memanggilnya..."
              className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-xs resize-none"
              required
            />
          </div>

          {/* Backend Function Selection */}
          <div>
            <label className="block font-semibold text-slate-800 mb-1">
              Backend Function
            </label>
            <div className="relative">
              <select
                value={selectedBackendFn}
                onChange={(e) => setSelectedBackendFn(e.target.value)}
                className="w-full appearance-none px-3 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-xs"
              >
                {REGISTERED_BACKEND_FUNCTIONS.map((fn) => (
                  <option key={fn.id} value={fn.id}>
                    {fn.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>
          </div>

          {/* Dynamic Parameters */}
          <div className="space-y-2 pt-1 border-t border-slate-100">
            <div className="flex items-center justify-between">
              <label className="font-semibold text-slate-800">
                Parameters
              </label>
              <button
                type="button"
                onClick={handleAddParam}
                className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-700 text-[11px] font-semibold cursor-pointer"
              >
                <Plus className="w-3 h-3" />
                <span>Tambah Param</span>
              </button>
            </div>

            <div className="space-y-2 max-h-40 overflow-y-auto pr-0.5">
              {parameters.map((param) => (
                <div
                  key={param.id}
                  className="p-2 rounded-xl border border-slate-200 bg-slate-50/50 flex items-center gap-2"
                >
                  <input
                    type="text"
                    value={param.name}
                    onChange={(e) =>
                      handleParamChange(param.id, "name", e.target.value)
                    }
                    placeholder="nama_param"
                    className="flex-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white font-mono text-xs outline-hidden"
                  />

                  <select
                    value={param.type}
                    onChange={(e) =>
                      handleParamChange(param.id, "type", e.target.value)
                    }
                    className="w-24 px-2 py-1.5 rounded-lg border border-slate-200 bg-white font-mono text-xs outline-hidden"
                  >
                    <option value="string">string</option>
                    <option value="number">number</option>
                    <option value="boolean">boolean</option>
                    <option value="object">object</option>
                  </select>

                  <label className="flex items-center gap-1 text-[11px] text-slate-500 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={param.required}
                      onChange={(e) =>
                        handleParamChange(param.id, "required", e.target.checked)
                      }
                      className="rounded text-blue-600"
                    />
                    <span>Wajib</span>
                  </label>

                  {parameters.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveParam(param.id)}
                      className="p-1 text-slate-400 hover:text-rose-600 rounded"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
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
          {saveError && <div className="px-5 pb-4"><p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700">{saveError}</p></div>}

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
