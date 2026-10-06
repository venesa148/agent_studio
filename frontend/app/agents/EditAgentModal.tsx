import React, { useState, useEffect } from "react";
import { X, CheckCircle2, AlertCircle } from "lucide-react";

export interface EditAgentModalProps {
  agent: any;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updatedAgent: any) => void;
}

export function EditAgentModal({ agent, isOpen, onClose, onSave }: EditAgentModalProps) {
  const [formData, setFormData] = useState<any>(null);
  const [dbTools, setDbTools] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (agent) {
      setFormData({ ...agent });
    }
  }, [agent]);

  useEffect(() => {
    if (isOpen) {
      fetch("http://localhost:8000/api/v1/tools")
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => setDbTools(data))
        .catch((err) => console.warn("Failed to load tools from database:", err));
    }
  }, [isOpen]);

  if (!isOpen || !formData) return null;

  const handleChange = (field: string, value: any) => {
    setFormData((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleToggleTool = (toolName: string) => {
    setFormData((prev: any) => {
      const currentTools = prev.tools || [];
      const exists = currentTools.includes(toolName);
      const updatedTools = exists
        ? currentTools.filter((t: string) => t !== toolName)
        : [...currentTools, toolName];
      return { ...prev, tools: updatedTools };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(`http://localhost:8000/api/v1/agent/${formData.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          instructions: formData.instructions,
          model: formData.model,
          tools: formData.tools,
          status: formData.status,
          mcp_servers: formData.mcp_servers,
          harness: formData.harness
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to update agent");
      }

      const updatedAgent = await res.json();
      onSave(updatedAgent);
    } catch (err: any) {
      setError(err.message || "An error occurred while saving.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <h2 className="text-lg font-bold text-slate-800">Edit Agent</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form id="edit-agent-form" onSubmit={handleSubmit} className="space-y-4 text-sm">
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Name
              </label>
              <input
                type="text"
                required
                value={formData.name || ""}
                onChange={(e) => handleChange("name", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-slate-800"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Description
              </label>
              <textarea
                value={formData.description || ""}
                onChange={(e) => handleChange("description", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-slate-800 resize-y"
                rows={2}
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Instructions (System Prompt)
              </label>
              <textarea
                value={formData.instructions || ""}
                onChange={(e) => handleChange("instructions", e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-slate-800 font-mono text-xs resize-y"
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Model
                </label>
                <input
                  type="text"
                  value={formData.model || "gpt-4o-mini"}
                  onChange={(e) => handleChange("model", e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-slate-800 font-mono text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                  Status
                </label>
                <select
                  value={formData.status || "active"}
                  onChange={(e) => handleChange("status", e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all text-slate-800"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="testing">Testing</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                Tools
              </label>
              <div className="flex flex-wrap gap-1 mb-2">
                {formData.tools && formData.tools.length > 0 ? (
                  formData.tools.map((tool: string) => (
                    <span
                      key={tool}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-blue-50 text-blue-700 border border-blue-200/60 font-mono text-xs"
                    >
                      <span>{tool}()</span>
                      <button
                        type="button"
                        onClick={() => handleToggleTool(tool)}
                        className="text-blue-400 hover:text-rose-600 font-bold ml-1"
                      >
                        ✕
                      </button>
                    </span>
                  ))
                ) : (
                  <span className="text-slate-400 text-xs italic">No tools selected</span>
                )}
              </div>
              {dbTools.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-100">
                  <span className="text-xs text-slate-500 block mb-2">
                    Available Database Tools:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {dbTools.map((dbTool) => {
                      const isSelected = formData.tools?.includes(dbTool.name);
                      return (
                        <button
                          key={dbTool.id || dbTool.name}
                          type="button"
                          onClick={() => handleToggleTool(dbTool.name)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-mono border transition-all ${
                            isSelected
                              ? "bg-blue-600 text-white border-blue-600 shadow-2xs"
                              : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
                          }`}
                        >
                          {isSelected ? "✓ " : "+ "}
                          {dbTool.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </form>
        </div>

        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-4 py-2 rounded-xl text-slate-600 text-sm font-medium hover:bg-slate-200 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="edit-agent-form"
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <CheckCircle2 className="w-4 h-4" />
            )}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}
