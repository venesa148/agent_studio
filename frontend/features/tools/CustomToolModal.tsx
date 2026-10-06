"use client";

import React, { useState } from "react";
import {
  X,
  Wrench,
  Plus,
  Trash2,
  ChevronDown,
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
  onSaveTool: (toolData: any) => void;
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

  const handleSubmit = (e: React.FormEvent) => {
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
      parameters: parameters.filter((p) => p.name.trim() !== ""),
    };

    onSaveTool(toolPayload);
    onClose();
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
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
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

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold shadow-2xs cursor-pointer"
            >
              Create Tool
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
