"use client";

import React, { useState, useEffect } from "react";
import {
  Columns2,
  RotateCcw,
  Settings,
  Paperclip,
  ArrowUp,
  Sparkles,
  Bot,
  User,
  CheckCircle2,
  FileCode2,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Wrench,
  Plus,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";

interface Message {
  id: string;
  sender: "user" | "builder";
  text: string;
  spec?: AgentSpecData;
  time?: string;
}

interface BuildAgentChatPaneProps {
  activeAgent?: AgentSpecData | null;
  onAgentCreated?: (agentSpec: AgentSpecData) => void;
  onClearActiveAgent?: () => void;
}

export function BuildAgentChatPane({ activeAgent, onAgentCreated, onClearActiveAgent }: BuildAgentChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [showSpecDetails, setShowSpecDetails] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [dbTools, setDbTools] = useState<any[]>([]);

  const skipClearRef = React.useRef(false);
  const currentAgentIdRef = React.useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!activeAgent) {
      if (currentAgentIdRef.current !== undefined) {
        setMessages([]);
        setInput("");
        setErrorMessage(null);
        setSaveSuccessMsg(null);
      }
      currentAgentIdRef.current = undefined;
      return;
    }

    if (currentAgentIdRef.current !== activeAgent.id) {
      if (!skipClearRef.current) {
        setMessages([
          {
            id: `system-spec-${activeAgent.id}`,
            sender: "builder",
            text: `Berikut adalah konfigurasi aktif untuk Agent '${activeAgent.name}'. Anda dapat langsung mengubahnya melalui form di bawah ini, atau memberi instruksi perubahan melalui chat.`,
            spec: activeAgent,
            time: "Sistem",
          }
        ]);
        setInput("");
        setErrorMessage(null);
        setSaveSuccessMsg(null);
      }
      currentAgentIdRef.current = activeAgent.id;
    }
  }, [activeAgent]);

  useEffect(() => {
    fetch("http://localhost:8000/api/v1/tools")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setDbTools(data))
      .catch((err) => console.warn("Failed to load tools from database:", err));
  }, []);

  const handleToggleTool = (msgId: string, toolName: string) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id === msgId && msg.spec) {
          const currentTools = msg.spec.tools || [];
          const exists = currentTools.includes(toolName);
          const updatedTools = exists
            ? currentTools.filter((t) => t !== toolName)
            : [...currentTools, toolName];
          return { ...msg, spec: { ...msg.spec, tools: updatedTools } };
        }
        return msg;
      })
    );
  };

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isBuilding) return;

    setErrorMessage(null);
    setSaveSuccessMsg(null);

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: input,
      time: "Baru saja",
    };

    setMessages((prev) => [...prev, userMsg]);
    const currentInput = input;
    setInput("");
    setIsBuilding(true);

    const lastSpecMsg = messages.slice().reverse().find((m) => m.spec);
    const currentSpec = lastSpecMsg ? lastSpecMsg.spec : activeAgent || null;

    const history = messages.map((m) => ({
      role: m.sender === "user" ? "user" : "assistant",
      content: m.text,
    }));

    try {
      const res = await fetch(`${apiUrl}/api/v1/builder/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: currentInput, current_spec: currentSpec, history }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Gagal membangun agent dari backend.");
      }

      const data = await res.json();

      const builderResponse: Message = {
        id: (Date.now() + 1).toString(),
        sender: "builder",
        text: data.message || `Spesifikasi Agent '${data.spec?.name}' telah berhasil disusun dan disimpan di database.`,
        spec: data.spec,
        time: "Baru saja",
      };

      setMessages((prev) => [...prev, builderResponse]);

      if (data.spec) {
        onAgentCreated?.(data.spec);
      }
    } catch (error: any) {
      console.warn("Error building agent:", error);
      const errTxt = error.message || "Terjadi kesalahan saat menghubungi server backend.";
      setErrorMessage(errTxt);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "builder",
          text: `⚠️ Error: ${errTxt}`,
          time: "Baru saja",
        },
      ]);
    } finally {
      setIsBuilding(false);
    }
  };

  const handleReset = () => {
    setMessages([]);
    setInput("");
    setErrorMessage(null);
    setSaveSuccessMsg(null);
  };

  const handleSpecChange = (msgId: string, field: string, value: any) => {
    setMessages((prev) =>
      prev.map((msg) => {
        if (msg.id === msgId && msg.spec) {
          return { ...msg, spec: { ...msg.spec, [field]: value } };
        }
        return msg;
      })
    );
  };

  const handleSaveSpec = async (spec: AgentSpecData) => {
    setErrorMessage(null);
    setSaveSuccessMsg(null);
    try {
      const res = await fetch(`${apiUrl}/api/v1/builder/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(spec),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Gagal menyimpan spesifikasi agent.");
      }

      const savedSpec: AgentSpecData = await res.json();
      
      skipClearRef.current = true;
      onAgentCreated?.(savedSpec);
      
      setTimeout(() => {
        skipClearRef.current = false;
      }, 500);

      setSaveSuccessMsg(`Agent '${savedSpec.name}' berhasil disimpan ke database.`);
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    } catch (e: any) {
      console.warn("Error saving spec:", e);
      setErrorMessage(e.message || "Gagal menyimpan ke database.");
    }
  };

  const handleExportYaml = async (spec: AgentSpecData) => {
    if (!spec.id) {
      setErrorMessage("Agent belum tersimpan di database. Silakan klik 'Simpan Perubahan Agent' terlebih dahulu.");
      return;
    }
    setErrorMessage(null);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/agent/${spec.id}/export-yaml?download=true`);
      if (!res.ok) {
        throw new Error("Gagal mengunduh berkas YAML dari backend.");
      }
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      const cleanSlug = (spec.name || "agent").toLowerCase().replace(/[^a-z0-9]+/g, "_");
      a.download = `${cleanSlug}.yaml`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);

      setSaveSuccessMsg(`Berkas deklaratif '${a.download}' berhasil diunduh dan tersimpan di folder agents/!`);
      setTimeout(() => setSaveSuccessMsg(null), 5000);
    } catch (err: any) {
      console.warn("Error exporting YAML:", err);
      setErrorMessage(err.message || "Gagal mengunduh berkas YAML.");
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-white border-r border-slate-200/80 min-w-0">
      {/* Top Bar */}
      <div className="h-14 px-4 border-b border-slate-200/70 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
          <button
            title="Toggle View"
            className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700"
          >
            <Columns2 className="w-4 h-4" />
          </button>
          <span className="text-slate-400 font-normal">0. Prompt Builder</span>
        </div>

        <div className="flex items-center gap-2">
          {activeAgent && (
            <span className="text-[11px] px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-medium border border-blue-200">
              Active: {activeAgent.name}
            </span>
          )}
          <button
            onClick={handleReset}
            title="Reset Prompt"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            title="Prompt Settings"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Error / Success Toast Banner */}
      {errorMessage && (
        <div className="mx-4 mt-3 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-rose-500 font-bold hover:text-rose-700 ml-2">
            ✕
          </button>
        </div>
      )}

      {saveSuccessMsg && (
        <div className="mx-4 mt-3 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{saveSuccessMsg}</span>
          </div>
          <button onClick={() => setSaveSuccessMsg(null)} className="text-emerald-500 font-bold hover:text-emerald-700 ml-2">
            ✕
          </button>
        </div>
      )}

      {/* Main Conversation & Empty State Area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-6">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center text-blue-600 mb-3 shadow-2xs">
              <Sparkles className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-700">
              Kirim instruksi untuk membuat AI Agent baru.
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-sm">
              Tulis kebutuhan Anda dalam bahasa natural (contoh: &ldquo;Buat agent CS BPJS yang bisa cari RS dan cek rujukan&rdquo;).
            </p>
          </div>
        ) : (
          <div className="space-y-4 max-w-2xl mx-auto w-full py-2">
            {messages.map((msg) => (
              <div key={msg.id} className="space-y-2">
                <div
                  className={`flex gap-3 ${
                    msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {msg.sender === "builder" && (
                    <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 text-xs shadow-2xs">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-2xs ${
                      msg.sender === "user"
                        ? "bg-blue-600 text-white rounded-br-xs"
                        : "bg-slate-50 border border-slate-200/80 text-slate-800 rounded-bl-xs"
                    }`}
                  >
                    <p className="whitespace-pre-line">{msg.text}</p>
                  </div>

                  {msg.sender === "user" && (
                    <div className="w-7 h-7 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 text-xs shadow-2xs">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>

                {/* Generated Spec Preview Card */}
                {msg.spec && (
                  <div className="ml-10 rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
                    <div className="px-3.5 py-2.5 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileCode2 className="w-3.5 h-3.5 text-blue-600" />
                        <span className="text-xs font-semibold text-slate-800">
                          Spesifikasi Agent (Tersimpan di DB: {msg.spec.id ? msg.spec.id.substring(0, 8) + '...' : 'Draft'})
                        </span>
                      </div>
                      <button
                        onClick={() => setShowSpecDetails(!showSpecDetails)}
                        className="text-slate-400 hover:text-slate-600 text-xs flex items-center gap-1"
                      >
                        {showSpecDetails ? (
                          <ChevronDown className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronRight className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>

                    {showSpecDetails && (
                      <div className="p-3.5 space-y-2.5 text-xs">
                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Nama Agent
                          </div>
                          <input
                            value={msg.spec.name}
                            onChange={(e) => handleSpecChange(msg.id, "name", e.target.value)}
                            className="font-semibold text-slate-900 mt-0.5 bg-transparent border-b border-dashed border-slate-300 hover:border-slate-400 focus:border-blue-500 outline-hidden w-full transition-colors"
                          />
                        </div>

                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Deskripsi
                          </div>
                          <textarea
                            value={msg.spec.description || ""}
                            onChange={(e) => handleSpecChange(msg.id, "description", e.target.value)}
                            className="text-slate-600 mt-0.5 bg-transparent border-b border-dashed border-slate-300 hover:border-slate-400 focus:border-blue-500 outline-hidden w-full resize-none transition-colors"
                            rows={2}
                          />
                        </div>

                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Instruksi (System Prompt)
                          </div>
                          <textarea
                            value={msg.spec.instructions || ""}
                            onChange={(e) => handleSpecChange(msg.id, "instructions", e.target.value)}
                            className="text-slate-600 mt-0.5 bg-transparent border border-dashed border-slate-300 hover:border-slate-400 focus:border-blue-500 outline-hidden w-full p-2 rounded-md text-[10px] font-mono h-24 resize-y transition-colors"
                          />
                        </div>

                        <div>
                          <div className="flex items-center justify-between">
                            <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                              <Wrench className="w-3 h-3 text-blue-600" />
                              <span>Tools dari Database ({msg.spec.tools ? msg.spec.tools.length : 0})</span>
                            </div>
                            <span className="text-[9px] text-slate-400">
                              Katalog Database
                            </span>
                          </div>

                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {msg.spec.tools && msg.spec.tools.length > 0 ? (
                              msg.spec.tools.map((tool) => (
                                <span
                                  key={tool}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200/60 font-mono text-[11px]"
                                >
                                  <span>{tool}()</span>
                                  <button
                                    type="button"
                                    onClick={() => handleToggleTool(msg.id, tool)}
                                    className="text-blue-400 hover:text-rose-600 font-bold ml-0.5 cursor-pointer"
                                    title="Hapus tool ini dari agent"
                                  >
                                    ✕
                                  </button>
                                </span>
                              ))
                            ) : (
                              <span className="text-slate-400 text-[11px] italic">
                                Belum ada tool dipilih dari database.
                              </span>
                            )}
                          </div>

                          {/* Opsi penambahan tools aktif yang tersedia dari database */}
                          {dbTools.length > 0 && (
                            <div className="mt-2 pt-2 border-t border-slate-100">
                              <span className="text-[10px] text-slate-400 block mb-1">
                                Tools aktif di database (klik untuk tambah / hapus):
                              </span>
                              <div className="flex flex-wrap gap-1">
                                {dbTools.map((dbTool) => {
                                  const isSelected = msg.spec?.tools?.includes(dbTool.name);
                                  return (
                                    <button
                                      key={dbTool.id || dbTool.name}
                                      type="button"
                                      onClick={() => handleToggleTool(msg.id, dbTool.name)}
                                      className={`px-2 py-0.5 rounded text-[10px] font-mono border transition-all cursor-pointer ${
                                        isSelected
                                          ? "bg-blue-600 text-white border-blue-600 font-semibold shadow-2xs"
                                          : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
                                      }`}
                                      title={dbTool.description || dbTool.name}
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

                        <div className="flex items-center justify-between pt-1">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-400">Harness:</span>
                            <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-medium">
                              {msg.spec.harness}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-slate-400">Model:</span>
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono">
                              {msg.spec.model}
                            </span>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-slate-100 flex items-center justify-end gap-2">
                          <button
                            type="button"
                            onClick={() => handleExportYaml(msg.spec!)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors shadow-2xs cursor-pointer"
                            title="Unduh berkas spesifikasi deklaratif .yaml"
                          >
                            <FileCode2 className="w-3.5 h-3.5" />
                            Export .YAML
                          </button>
                          <button
                            onClick={() => handleSaveSpec(msg.spec!)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition-colors shadow-2xs cursor-pointer"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Simpan Perubahan Agent
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {isBuilding && (
              <div className="flex items-center gap-2 text-xs text-blue-600 pl-10 py-2">
                <div className="w-3.5 h-3.5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span>Backend sedang memproses prompt dan menyimpan Agent ke database...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Input Bar */}
      <div className="p-4 bg-white shrink-0">
        <form
          onSubmit={handleSend}
          className="relative flex items-center border border-slate-200 rounded-2xl px-3 py-2 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-2xs"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ketik instruksi untuk membuat/memperbarui agent..."
            className="flex-1 text-xs text-slate-900 placeholder:text-slate-400 outline-hidden bg-transparent pr-20 pl-1"
          />

          <div className="absolute right-2 flex items-center gap-1.5">
            <button
              type="button"
              title="Attach File/Context"
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <Paperclip className="w-4 h-4" />
            </button>

            <button
              type="submit"
              disabled={!input.trim() || isBuilding}
              title="Send"
              className="w-7 h-7 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white flex items-center justify-center transition-all shadow-2xs"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
