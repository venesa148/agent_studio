"use client";

import React, { useState, useEffect } from "react";
import { X, Wrench, Save, AlertCircle, Globe } from "lucide-react";

interface EditToolModalProps {
  isOpen: boolean;
  tool: any | null;
  onClose: () => void;
  onSaveTool: (
    toolId: string,
    updatedData: { name: string; description: string; apiUrl?: string; input_schema?: any }
  ) => Promise<void>;
}

export function EditToolModal({
  isOpen,
  tool,
  onClose,
  onSaveTool,
}: EditToolModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (tool) {
      setName(tool.name || "");
      setDescription(tool.description || "");
      const existingUrl =
        tool.input_schema?.["x-api-config"]?.base_url ||
        tool.input_schema?.["x-openapi"]?.server_url ||
        tool.input_schema?.base_url ||
        "";
      setApiUrl(existingUrl);
      setErrorMsg(null);
    }
  }, [tool]);

  if (!isOpen || !tool) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg("Nama tool tidak boleh kosong.");
      return;
    }

    setIsSaving(true);
    setErrorMsg(null);
    try {
      const updatedSchema = { ...(tool.input_schema || {}) };
      if (apiUrl.trim()) {
        if (!updatedSchema["x-api-config"]) {
          updatedSchema["x-api-config"] = {};
        }
        updatedSchema["x-api-config"]["base_url"] = apiUrl.trim();
      } else if (updatedSchema["x-api-config"]?.base_url) {
        delete updatedSchema["x-api-config"]["base_url"];
      }

      await onSaveTool(tool.id, {
        name: name.trim(),
        description: description.trim(),
        apiUrl: apiUrl.trim() || undefined,
        input_schema: updatedSchema,
      });
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "Gagal memperbarui tool.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div
        className="fixed inset-0"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden z-10 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-blue-50 text-blue-600">
              <Wrench className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Edit Tool</h3>
              <p className="text-[11px] text-slate-500">
                Perbarui konfigurasi tool dan tautan sumber data.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Nama Tool
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Contoh: search_hospital, get_menu_makanan"
              className="w-full text-xs font-mono px-3.5 py-2.5 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-hidden transition-all bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Deskripsi Tool
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Jelaskan fungsi tool ini..."
              className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-hidden transition-all bg-white resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              API Base URL / Hosting Tunnel (Opsional)
            </label>
            <div className="relative">
              <input
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="https://xxx.trycloudflare.com"
                className="w-full pl-8 pr-3 py-2 text-xs font-mono border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-slate-800"
              />
              <Globe className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            </div>
            <p className="text-[10px] text-slate-400 mt-1">
              Tautan hosting sumber data khusus tool ini. Jika dikosongkan, akan mengikuti server MCP terkait.
            </p>
          </div>

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
            >
              Batal
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 rounded-xl transition-all shadow-2xs cursor-pointer"
            >
              {isSaving ? (
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              <span>Simpan Perubahan</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
