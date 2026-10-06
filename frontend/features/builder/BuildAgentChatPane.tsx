"use client";

import React, { useState } from "react";
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
}

export function BuildAgentChatPane({ activeAgent, onAgentCreated }: BuildAgentChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [showSpecDetails, setShowSpecDetails] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

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

    try {
      const res = await fetch("http://localhost:8000/api/v1/builder/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: currentInput, current_spec: currentSpec }),
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
      const res = await fetch("http://localhost:8000/api/v1/builder/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(spec),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Gagal menyimpan spesifikasi agent.");
      }

      const savedSpec: AgentSpecData = await res.json();
      onAgentCreated?.(savedSpec);
      setSaveSuccessMsg(`Agent '${savedSpec.name}' berhasil disimpan ke database.`);
      setTimeout(() => setSaveSuccessMsg(null), 4000);
    } catch (e: any) {
      console.warn("Error saving spec:", e);
      setErrorMessage(e.message || "Gagal menyimpan ke database.");
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
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Tools Terpilih ({msg.spec.tools ? msg.spec.tools.length : 0})
                          </div>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {msg.spec.tools && msg.spec.tools.map((tool) => (
                              <span
                                key={tool}
                                className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200/60 font-mono text-[11px]"
                              >
                                {tool}()
                              </span>
                            ))}
                          </div>
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

                        <div className="pt-2 border-t border-slate-100 flex justify-end">
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
