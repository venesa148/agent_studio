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
} from "lucide-react";

interface Message {
  id: string;
  sender: "user" | "builder";
  text: string;
  spec?: {
    name: string;
    description: string;
    instructions: string;
    model: string;
    tools: string[];
    mcp_servers: string[];
    harness: string;
  };
  time?: string;
}

interface BuildAgentChatPaneProps {
  onAgentCreated?: (agentSpec: any) => void;
}

export function BuildAgentChatPane({ onAgentCreated }: BuildAgentChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [showSpecDetails, setShowSpecDetails] = useState(true);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isBuilding) return;

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

    // Simulate builder agent response (aligns with PRD requirements)
    setTimeout(() => {
      const isBPJS =
        currentInput.toLowerCase().includes("bpjs") ||
        currentInput.toLowerCase().includes("rs") ||
        currentInput.toLowerCase().includes("rumah sakit");

      const generatedSpec = {
        name: isBPJS ? "BPJS Customer Service Agent" : "Custom AI Assistant",
        description: isBPJS
          ? "Agent cerdas untuk pencarian RS rekanan BPJS, cek rujukan pasien, dan eskalasi ke staf human."
          : "Agent yang dikonfigurasi berdasarkan kebutuhan Anda.",
        instructions: isBPJS
          ? "Bantu pasien mencari rumah sakit terdekat, verifikasi status BPJS, periksa status rujukan RJ, dan eskalasi jika data tidak ditemukan sesuai aturan harness."
          : "Jalankan instruksi pengguna dengan aman dan akurat berbasis tools yang tersedia.",
        model: "openai/gpt-4o-mini",
        tools: isBPJS
          ? [
              "search_hospital",
              "get_hospital_detail",
              "check_bpjs",
              "find_specialist",
              "get_referral_status",
            ]
          : ["search_knowledge", "web_search"],
        mcp_servers: isBPJS ? ["hospital-mcp"] : [],
        harness: "default-safe-v1",
      };

      const builderResponse: Message = {
        id: (Date.now() + 1).toString(),
        sender: "builder",
        text: `Saya telah menyusun spesifikasi Agent berdasarkan kebutuhan Anda: "${currentInput}". Spec telah divalidasi dan tools telah dicocokkan dengan Registry.`,
        spec: generatedSpec,
        time: "Baru saja",
      };

      setMessages((prev) => [...prev, builderResponse]);
      setIsBuilding(false);
    }, 1200);
  };

  const handleReset = () => {
    setMessages([]);
    setInput("");
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
          <span className="text-slate-400 font-normal">0. Prompt</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400">
            {messages.length > 0 ? "Aktif" : "3 minutes ago"}
          </span>
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

      {/* Main Conversation & Empty State Area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-6">
            <div className="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center text-blue-600 mb-3 shadow-2xs">
              <Sparkles className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-500">
              Send a message to start building your agent.
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
                    <p>{msg.text}</p>
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
                          Spesifikasi Agent (Valid Pydantic)
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
                          <div className="font-semibold text-slate-900 mt-0.5">
                            {msg.spec.name}
                          </div>
                        </div>

                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Deskripsi
                          </div>
                          <div className="text-slate-600 mt-0.5">
                            {msg.spec.description}
                          </div>
                        </div>

                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                            Tools Terpilih ({msg.spec.tools.length})
                          </div>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {msg.spec.tools.map((tool) => (
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
                            onClick={() => onAgentCreated?.(msg.spec)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium transition-colors shadow-2xs"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Simpan Agent (Draft)
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
                <span>Builder sedang membaca Registry dan menyusun spesifikasi agent...</span>
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
            placeholder="Build your agent..."
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
