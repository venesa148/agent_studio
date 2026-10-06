"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Activity,
  Trash2,
  RotateCcw,
  Settings,
  MoreHorizontal,
  Send,
  Bot,
  User,
  Wrench,
  AlertTriangle,
  ShieldAlert,
  Check,
  ChevronDown,
  AlertCircle,
  Database,
  ExternalLink,
  Globe,
  Plus,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";

export type TestPaneTab = "chat" | "trace";

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  toolCall?: {
    name: string;
    params: Record<string, any>;
    result: any;
    duration_ms: number;
  };
  status?: "ok" | "escalated" | "blocked" | "error";
  time: string;
}

interface TestAgentPaneProps {
  activeAgent: AgentSpecData | null;
  agents: AgentSpecData[];
  onSelectAgent?: (agent: AgentSpecData) => void;
  isLoadingAgents?: boolean;
}

export function TestAgentPane({
  activeAgent,
  agents = [],
  onSelectAgent,
  isLoadingAgents = false,
}: TestAgentPaneProps) {
  const [activeTab, setActiveTab] = useState<TestPaneTab>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [traceSteps, setTraceSteps] = useState<any[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Publish popover states (from latest pull)
  const [isPublished, setIsPublished] = useState(false);
  const [showPublishPopover, setShowPublishPopover] = useState(false);
  const [domainSlug, setDomainSlug] = useState("");
  const [accessLevel, setAccessLevel] = useState<"Public" | "Restricted">("Public");
  const [showAccessDropdown, setShowAccessDropdown] = useState(false);

  // Clear messages when activeAgent changes
  useEffect(() => {
    setMessages([]);
    setTraceSteps([]);
    setErrorMessage(null);
    if (activeAgent?.name) {
      setDomainSlug(activeAgent.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
    }
  }, [activeAgent?.id]);

  const handleSendChat = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isRunning) return;

    if (!activeAgent || !activeAgent.id) {
      setErrorMessage("Belum ada Agent yang dipilih/dibuat. Silakan buat Agent terlebih dahulu via chat utama.");
      return;
    }

    setErrorMessage(null);
    const userText = input;
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: userText,
      time: "Sekarang",
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsRunning(true);

    try {
      const res = await fetch("http://localhost:8000/api/v1/agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          agent_id: activeAgent.id,
          message: userText,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP Error ${res.status}: Gagal memproses pesan.`);
      }

      const data = await res.json();

      const agentMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "agent",
        text: data.response,
        status: data.status || "ok",
        time: "Sekarang",
      };

      setMessages((prev) => [...prev, agentMsg]);

      if (data.trace_steps && Array.isArray(data.trace_steps)) {
        setTraceSteps(data.trace_steps);
      }
    } catch (error: any) {
      console.warn("Error testing agent:", error);
      const errTxt = error.message || "Maaf, terjadi kesalahan saat menghubungi Agent Backend.";
      setErrorMessage(errTxt);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "agent",
          text: `⚠️ Gagal Eksekusi: ${errTxt}`,
          status: "error",
          time: "Sekarang",
        },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    setTraceSteps([]);
    setErrorMessage(null);
  };

  return (
    <div className="w-[380px] lg:w-[420px] shrink-0 border-l border-slate-200/80 bg-white flex flex-col h-full select-none">
      {/* Agent Selector Header */}
      <div className="px-3 py-2 border-b border-slate-200/70 bg-[#fafbfe] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Database className="w-4 h-4 text-blue-600 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Testing Agent Active
            </div>
            {agents.length > 0 ? (
              <div className="relative inline-block w-full">
                <select
                  value={activeAgent?.id || ""}
                  onChange={(e) => {
                    const sel = agents.find((a) => a.id === e.target.value);
                    if (sel && onSelectAgent) onSelectAgent(sel);
                  }}
                  className="w-full text-xs font-bold text-slate-800 bg-transparent pr-4 truncate outline-hidden cursor-pointer"
                >
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} ({agent.id.substring(0, 6)}...)
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <span className="text-xs font-medium text-slate-400 italic">
                {isLoadingAgents ? "Memuat agents..." : "Belum ada agent"}
              </span>
            )}
          </div>
        </div>

        {activeAgent && (
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200 shrink-0">
            ONLINE
          </span>
        )}
      </div>

      {/* Top Multiple Tabs Header */}
      <div className="h-12 px-3 border-b border-slate-200/70 flex items-center justify-between shrink-0 bg-[#fafbfe]">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "chat"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Test Chat</span>
          </button>

          <button
            onClick={() => setActiveTab("trace")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "trace"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Trace ({traceSteps.length})</span>
          </button>

          {/* Tombol Publish persis di samping Tab Trace */}
          <div className="relative ml-1">
            <button
              onClick={() => setShowPublishPopover(!showPublishPopover)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-2xs ${
                isPublished
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>{isPublished ? "Live" : "Publish"}</span>
            </button>

            {/* Publish Popover Dialog */}
            {showPublishPopover && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setShowPublishPopover(false)}
                />
                <div className="absolute right-0 top-10 mt-1 w-80 sm:w-96 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl z-40 text-xs space-y-4 animate-in fade-in zoom-in-95 duration-150">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-900">Publish Agent</h4>
                    <Link
                      href="/deployments"
                      onClick={() => setShowPublishPopover(false)}
                      className="text-slate-500 hover:text-blue-600 flex items-center gap-1 text-[11px] font-medium"
                    >
                      <span>Settings</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <label className="font-semibold text-slate-700">Domain / Slug</label>
                      <span className="text-emerald-600 font-semibold flex items-center gap-1">
                        <Check className="w-3 h-3 stroke-[2.5]" />
                        Available
                      </span>
                    </div>

                    <div className="flex items-center border border-slate-200 rounded-xl overflow-hidden bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100">
                      <input
                        type="text"
                        value={domainSlug}
                        onChange={(e) => setDomainSlug(e.target.value)}
                        className="flex-1 px-3 py-2 text-xs font-mono text-slate-800 outline-hidden bg-transparent min-w-0"
                      />
                      <span className="px-3 py-2 bg-slate-50 border-l border-slate-200 text-slate-500 font-mono text-[11px] shrink-0">
                        .agentstudio.app
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="font-semibold text-slate-700 text-[11px]">
                      Who can access your app
                    </label>

                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => setShowAccessDropdown(!showAccessDropdown)}
                        className="w-full p-2.5 rounded-xl border border-slate-200 bg-slate-50/60 hover:bg-slate-50 flex items-center justify-between text-left transition-colors"
                      >
                        <div className="flex items-center gap-2.5">
                          <Globe className="w-4 h-4 text-slate-600 shrink-0" />
                          <div>
                            <div className="font-semibold text-slate-900">{accessLevel}</div>
                            <div className="text-[10px] text-slate-400">
                              {accessLevel === "Public"
                                ? "Anyone on the internet with the URL"
                                : "Only authorized API Key / workspace"}
                            </div>
                          </div>
                        </div>
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      </button>

                      {showAccessDropdown && (
                        <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-50">
                          <button
                            type="button"
                            onClick={() => {
                              setAccessLevel("Public");
                              setShowAccessDropdown(false);
                            }}
                            className="w-full px-3 py-2 text-left hover:bg-slate-50 flex flex-col"
                          >
                            <span className="font-semibold text-slate-900">Public</span>
                            <span className="text-[10px] text-slate-400">
                              Anyone on the internet with the URL
                            </span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setAccessLevel("Restricted");
                              setShowAccessDropdown(false);
                            }}
                            className="w-full px-3 py-2 text-left hover:bg-slate-50 flex flex-col border-t border-slate-100"
                          >
                            <span className="font-semibold text-slate-900">Restricted</span>
                            <span className="text-[10px] text-slate-400">
                              Requires valid Authorization Bearer key
                            </span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="pt-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={async () => {
                        if (!isPublished) {
                          try {
                            const res = await fetch("http://localhost:8000/api/v1/deployments", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                agent: activeAgent?.name || "Unknown Agent",
                                environment: "production",
                                path: `/api/agents/${domainSlug || activeAgent?.id}/run`,
                                status: "Ready"
                              }),
                            });
                            if (res.ok) {
                              setIsPublished(true);
                            } else {
                              alert("Failed to publish agent");
                            }
                          } catch (err) {
                            console.error(err);
                            alert("Error publishing agent");
                          }
                        } else {
                          setIsPublished(false);
                        }
                        setShowPublishPopover(false);
                      }}
                      className="w-full py-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-center shadow-2xs transition-colors cursor-pointer text-xs"
                    >
                      {isPublished ? "Unpublish" : "Publish Agent"}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Sub-toolbar */}
      <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between bg-white text-xs text-slate-500 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={handleClear}
            className="flex items-center gap-1 text-slate-500 hover:text-rose-600 transition-colors"
            title="Clear Chat"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span className="text-[11px] font-medium">Clear</span>
          </button>

          <button
            onClick={() => {
              if (messages.length > 0) {
                const lastUserMsg = messages.slice().reverse().find((m) => m.sender === "user");
                if (lastUserMsg) setInput(lastUserMsg.text);
              }
            }}
            className="flex items-center gap-1 text-slate-500 hover:text-blue-600 transition-colors"
            title="Replay Execution"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="text-[11px] font-medium">Replay</span>
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            title="Configuration"
            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          >
            <Settings className="w-3.5 h-3.5" />
          </button>
          <button
            title="More Options"
            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          >
            <MoreHorizontal className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Error Alert Banner */}
      {errorMessage && (
        <div className="mx-3 mt-2 p-2.5 bg-rose-50 border border-rose-200 text-rose-700 text-[11px] rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-rose-500 font-bold hover:text-rose-700 ml-1">
            ✕
          </button>
        </div>
      )}

      {/* Tab 1: Chat Pane Content */}
      {activeTab === "chat" && (
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/50">
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {!activeAgent ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <Bot className="w-8 h-8 mb-2 text-slate-300" />
                <p className="text-xs font-semibold text-slate-600">
                  Belum ada Agent yang aktif
                </p>
                <p className="text-[11px] text-slate-400 mt-1 max-w-[220px]">
                  Buat Agent terlebih dahulu dengan mengirim prompt pada chat utama di sebelah kiri.
                </p>
              </div>
            ) : messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <Bot className="w-8 h-8 mb-2 text-emerald-500" />
                <p className="text-xs font-semibold text-slate-700">
                  Uji coba percakapan dengan Agent: &ldquo;{activeAgent.name}&rdquo;
                </p>
                <p className="text-[11px] text-slate-400 mt-1 max-w-[240px]">
                  Instruksi aktif tersimpan di database: &ldquo;{activeAgent.instructions?.substring(0, 60)}...&rdquo;
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className="space-y-1.5">
                  <div
                    className={`flex gap-2 ${
                      msg.sender === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    {msg.sender === "agent" && (
                      <div className="w-6 h-6 rounded-md bg-emerald-600 text-white flex items-center justify-center shrink-0 text-[10px] mt-0.5">
                        <Bot className="w-3.5 h-3.5" />
                      </div>
                    )}

                    <div
                      className={`max-w-[85%] rounded-xl p-2.5 text-xs shadow-2xs leading-relaxed ${
                        msg.sender === "user"
                          ? "bg-blue-600 text-white rounded-br-xs"
                          : msg.status === "error"
                          ? "bg-rose-50 border border-rose-200 text-rose-800 rounded-bl-xs"
                          : "bg-white border border-slate-200/80 text-slate-800 rounded-bl-xs"
                      }`}
                    >
                      <p className="whitespace-pre-line">{msg.text}</p>
                    </div>

                    {msg.sender === "user" && (
                      <div className="w-6 h-6 rounded-md bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 text-[10px] mt-0.5">
                        <User className="w-3.5 h-3.5" />
                      </div>
                    )}
                  </div>

                  {msg.toolCall && (
                    <div className="ml-8 rounded-lg border border-slate-200 bg-white p-2 text-[11px] shadow-2xs space-y-1">
                      <div className="flex items-center justify-between text-slate-500">
                        <div className="flex items-center gap-1.5 font-mono text-blue-700 font-semibold">
                          <Wrench className="w-3 h-3 text-blue-600" />
                          <span>{msg.toolCall.name}()</span>
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {msg.toolCall.duration_ms}ms
                        </span>
                      </div>
                    </div>
                  )}

                  {msg.status && msg.status !== "ok" && (
                    <div className="ml-8 flex items-center gap-1.5">
                      {msg.status === "escalated" && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          <AlertTriangle className="w-3 h-3" />
                          Status: ESCALATED ke Human
                        </span>
                      )}
                      {msg.status === "blocked" && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                          <ShieldAlert className="w-3 h-3" />
                          Status: BLOCKED oleh Harness
                        </span>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}

            {isRunning && (
              <div className="flex items-center gap-2 text-xs text-blue-600 pl-8 py-1">
                <div className="w-3 h-3 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span>Backend memuat Agent dari DB dan memproses respon...</span>
              </div>
            )}
          </div>

          {/* Test Chat Input Bar */}
          <div className="p-3 bg-white border-t border-slate-200/70 shrink-0">
            <form
              onSubmit={handleSendChat}
              className="flex items-center gap-2 border border-slate-200 rounded-xl px-2.5 py-1.5 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-2xs"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!activeAgent || isRunning}
                placeholder={activeAgent ? `Chat with ${activeAgent.name}...` : "Buat Agent terlebih dahulu..."}
                className="flex-1 text-xs text-slate-900 placeholder:text-slate-400 outline-hidden bg-transparent pl-1 disabled:bg-transparent disabled:text-slate-400"
              />
              <button
                type="submit"
                disabled={!input.trim() || !activeAgent || isRunning}
                className="w-6 h-6 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white flex items-center justify-center transition-all shadow-2xs shrink-0"
              >
                <Send className="w-3 h-3" />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Tab 3: Trace Pane Content */}
      {activeTab === "trace" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-slate-50/50">
          <div className="p-2.5 bg-white border border-slate-200 rounded-xl shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">
                Agent Active ID: {activeAgent?.id || "N/A"}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                STATUS: OK
              </span>
            </div>
          </div>

          <div className="space-y-2 relative pl-2">
            <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-2">
              Langkah Eksekusi Backend (Timeline)
            </div>

            {traceSteps.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-400 italic bg-white rounded-xl border border-slate-200">
                Belum ada trace eksekusi. Kirim pesan pada chat testing untuk melihat jejak eksekusi backend.
              </div>
            ) : (
              traceSteps.map((step) => (
                <div
                  key={step.step_no}
                  className="relative pl-5 border-l-2 border-blue-200 pb-3 last:border-transparent last:pb-0"
                >
                  <span className="absolute -left-[5px] top-0.5 w-2 h-2 rounded-full bg-blue-600 ring-4 ring-white" />

                  <div className="bg-white border border-slate-200 rounded-xl p-2.5 shadow-2xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-800">
                        {step.step_no}. {step.title}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {step.duration_ms}ms
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 font-mono bg-slate-50 p-1.5 rounded">
                      {step.detail}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
