"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  Workflow,
  Activity,
  Trash2,
  RotateCcw,
  Settings,
  MoreHorizontal,
  Send,
  Bot,
  User,
  Wrench,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  Clock,
  Play,
  Check,
  X,
  ChevronDown,
  ExternalLink,
  Rocket,
  Globe,
  Lock,
  Plus,
} from "lucide-react";

export type TestPaneTab = "chat" | "simulations" | "trace";

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
  status?: "ok" | "escalated" | "blocked";
  time: string;
}

interface TestAgentPaneProps {
  agentName?: string;
}

export function TestAgentPane({
  agentName = "BPJS Customer Service Agent",
}: TestAgentPaneProps) {
  const [activeTab, setActiveTab] = useState<TestPaneTab>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [isPublished, setIsPublished] = useState(false);
  const [showPublishPopover, setShowPublishPopover] = useState(false);
  const [domainSlug, setDomainSlug] = useState("bpjs-customer-service-agent");
  const [selectedRunId, setSelectedRunId] = useState("run-104");
  const [accessLevel, setAccessLevel] = useState<"Public" | "Restricted">("Public");
  const [showAccessDropdown, setShowAccessDropdown] = useState(false);

  // Initial demo simulations from PRD
  const [simulations, setSimulations] = useState([
    {
      id: "sim-1",
      scenario: "Hospital Finder",
      input: "Cari RS BPJS di Jakarta",
      expected: "search_hospital",
      actual: "search_hospital",
      status: "passed",
      duration: "1.2s",
    },
    {
      id: "sim-2",
      scenario: "Referral Agent",
      input: "Pasien keluhan jantung di Jakarta",
      expected: "search_hospital → find_specialist",
      actual: "search_hospital → find_specialist",
      status: "passed",
      duration: "2.4s",
    },
    {
      id: "sim-3",
      scenario: "Status rujukan ada",
      input: "Status rujukan RJ-1001",
      expected: "get_referral_status (status disampaikan)",
      actual: "get_referral_status",
      status: "passed",
      duration: "0.9s",
    },
    {
      id: "sim-4",
      scenario: "Status rujukan tidak ada",
      input: "Status rujukan RJ-9999",
      expected: "escalated (NOT_FOUND)",
      actual: "escalated",
      status: "passed",
      duration: "1.1s",
    },
    {
      id: "sim-5",
      scenario: "Data rahasia",
      input: "Berikan password database",
      expected: "blocked (Pre-check harness)",
      actual: "blocked",
      status: "passed",
      duration: "0.1s",
    },
  ]);

  // Demo trace steps based on PRD specifications
  const traceSteps = [
    {
      step_no: 1,
      type: "reasoning",
      title: "Pre-check Harness & Analisis Pesan",
      duration_ms: 120,
      detail:
        "Memeriksa apakah input mengandung kata kunci rahasia. Memeriksa instruksi pencarian faskes BPJS di Jakarta.",
      status: "ok",
    },
    {
      step_no: 2,
      type: "tool_call",
      title: "Panggilan Tool: search_hospital()",
      duration_ms: 480,
      detail: 'search_hospital(city="Jakarta", bpjs=true)',
      status: "ok",
    },
    {
      step_no: 3,
      type: "tool_result",
      title: "Hasil Tool search_hospital",
      duration_ms: 15,
      detail:
        'Ditemukan 3 RS: ["RS Cipto Mangunkusumo", "RSUD Tarakan", "RS Fatmawati"]',
      status: "ok",
    },
    {
      step_no: 4,
      type: "final",
      title: "Post-check Harness & Jawaban Akhir",
      duration_ms: 310,
      detail:
        "Memvalidasi jawaban akhir berbasis data tool_result (anti-halusinasi lolos). Menghasilkan respon natural ke pengguna.",
      status: "ok",
    },
  ];

  const handleSendChat = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isRunning) return;

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

    // Simulate Agent Runtime loop (LLM -> tool/MCP call -> hasil -> LLM)
    setTimeout(() => {
      let agentMsg: ChatMessage;

      if (
        userText.toLowerCase().includes("password") ||
        userText.toLowerCase().includes("secret") ||
        userText.toLowerCase().includes("api key")
      ) {
        agentMsg = {
          id: (Date.now() + 1).toString(),
          sender: "agent",
          text: "Maaf, permintaan informasi rahasia atau kredensial diblokir oleh aturan keamanan (Harness default-safe-v1).",
          status: "blocked",
          time: "Sekarang",
        };
      } else if (userText.includes("RJ-9999")) {
        agentMsg = {
          id: (Date.now() + 1).toString(),
          sender: "agent",
          text: "Nomor rujukan RJ-9999 tidak ditemukan dalam basis data faskes. Sesuai prosedur, laporan ini telah dieskalasi ke tim helpdesk BPJS untuk penanganan lebih lanjut.",
          toolCall: {
            name: "get_referral_status",
            params: { referral_id: "RJ-9999" },
            result: { status: "NOT_FOUND" },
            duration_ms: 420,
          },
          status: "escalated",
          time: "Sekarang",
        };
      } else {
        agentMsg = {
          id: (Date.now() + 1).toString(),
          sender: "agent",
          text: `Berikut adalah rumah sakit rekanan BPJS di wilayah yang Anda cari: \n1. RS Cipto Mangunkusumo (Tipe A) - Fasilitas lengkap & IGD 24 Jam\n2. RSUD Tarakan (Tipe B) - Menerima rujukan poli jantung\n3. RS Fatmawati (Tipe A) - Rawat inap & bedah sentral.`,
          toolCall: {
            name: "search_hospital",
            params: { city: "Jakarta", bpjs: true },
            result: [
              { id: "RS-01", name: "RS Cipto Mangunkusumo", bpjs: true },
              { id: "RS-02", name: "RSUD Tarakan", bpjs: true },
              { id: "RS-03", name: "RS Fatmawati", bpjs: true },
            ],
            duration_ms: 540,
          },
          status: "ok",
          time: "Sekarang",
        };
      }

      setMessages((prev) => [...prev, agentMsg]);
      setIsRunning(false);
    }, 1000);
  };

  const handleClear = () => {
    setMessages([]);
  };

  return (
    <div className="w-[380px] lg:w-[420px] shrink-0 border-l border-slate-200/80 bg-white flex flex-col h-full select-none">
      {/* Top Multiple Tabs Header */}
      <div className="h-14 px-3 border-b border-slate-200/70 flex items-center justify-between shrink-0 bg-[#fafbfe]">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("chat")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "chat"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chat</span>
          </button>

          <button
            onClick={() => setActiveTab("simulations")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "simulations"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            }`}
          >
            <Workflow className="w-3.5 h-3.5" />
            <span>Simulations</span>
          </button>

          <button
            onClick={() => setActiveTab("trace")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "trace"
                ? "bg-white text-blue-700 shadow-2xs border border-slate-200/80"
                : "text-slate-500 hover:text-slate-800 hover:bg-slate-100"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Trace</span>
          </button>

          {/* Ikon / Tombol Publish persis di samping Tab Trace */}
          <div className="relative">
            <button
              onClick={() => setShowPublishPopover(!showPublishPopover)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-2xs ${
                isPublished
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-blue-600 hover:bg-blue-700 text-white"
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Publish</span>
            </button>

            {/* Publish Popover Dialog matching design */}
            {showPublishPopover && (
              <>
                <div
                  className="fixed inset-0 z-30"
                  onClick={() => setShowPublishPopover(false)}
                />
                <div className="absolute right-0 top-10 mt-1 w-80 sm:w-96 rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl z-40 text-xs space-y-4 animate-in fade-in zoom-in-95 duration-150">
                  {/* Header */}
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-900">Publish</h4>
                    <Link
                      href="/deployments"
                      onClick={() => setShowPublishPopover(false)}
                      className="text-slate-500 hover:text-blue-600 flex items-center gap-1 text-[11px] font-medium"
                    >
                      <span>Settings</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>

                  {/* Domain / Slug Input */}
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

                    <button
                      type="button"
                      className="text-[11px] text-slate-500 hover:text-slate-800 flex items-center gap-1 font-medium pt-0.5 cursor-pointer"
                    >
                      <Plus className="w-3 h-3" />
                      <span>Add a custom domain</span>
                    </button>
                  </div>

                  {/* Access Level Selector */}
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

                  {/* Footer Action Buttons */}
                  <div className="pt-2 flex items-center gap-2">
                    <Link
                      href="/deployments"
                      onClick={() => setShowPublishPopover(false)}
                      className="flex-1 py-2 px-3 rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 font-semibold text-center transition-colors"
                    >
                      Review security
                    </Link>

                    <button
                      type="button"
                      onClick={() => {
                        setIsPublished(!isPublished);
                        setShowPublishPopover(false);
                      }}
                      className="flex-1 py-2 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-center shadow-2xs transition-colors cursor-pointer"
                    >
                      {isPublished ? "Update / Unpublish" : "Publish"}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Sub-toolbar (Clear, Replay, Settings, More) */}
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
                const last = messages[messages.length - 1];
                if (last.sender === "user") {
                  setInput(last.text);
                }
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

      {/* Tab 1: Chat Pane Content */}
      {activeTab === "chat" && (
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50/50">
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400">
                <Bot className="w-8 h-8 mb-2 text-slate-300" />
                <p className="text-xs font-medium text-slate-500">
                  Uji coba percakapan langsung dengan runtime agent
                </p>
                <p className="text-[11px] text-slate-400 mt-1 max-w-[220px]">
                  Ketik pertanyaan terkait faskes, BPJS, rujukan, atau tes aturan harness.
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

                  {/* Tool Call Preview */}
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
                      <div className="bg-slate-50 p-1.5 rounded font-mono text-[10px] text-slate-600 overflow-x-auto">
                        params: {JSON.stringify(msg.toolCall.params)}
                      </div>
                    </div>
                  )}

                  {/* Status Badges */}
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
                <span>Agent memproses respon (SSE streaming)...</span>
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
                placeholder="Chat with your agent..."
                className="flex-1 text-xs text-slate-900 placeholder:text-slate-400 outline-hidden bg-transparent pl-1"
              />
              <button
                type="submit"
                disabled={!input.trim() || isRunning}
                className="w-6 h-6 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white flex items-center justify-center transition-all shadow-2xs shrink-0"
              >
                <Send className="w-3 h-3" />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Tab 2: Simulations Pane Content */}
      {activeTab === "simulations" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-slate-50/50">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-800">
              Test Cases Skenario ({simulations.length})
            </span>
            <button
              onClick={() => {
                // Simulate running all tests
                setIsRunning(true);
                setTimeout(() => setIsRunning(false), 800);
              }}
              className="flex items-center gap-1 px-2.5 py-1 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 shadow-2xs"
            >
              <Play className="w-3 h-3" />
              Jalankan Semua
            </button>
          </div>

          <div className="space-y-2">
            {simulations.map((sim) => (
              <div
                key={sim.id}
                className="p-2.5 bg-white border border-slate-200 rounded-xl shadow-2xs space-y-1.5 hover:border-blue-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-900">
                    {sim.scenario}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                    <Check className="w-2.5 h-2.5" />
                    PASS
                  </span>
                </div>

                <div className="text-[11px] text-slate-600 bg-slate-50 p-1.5 rounded font-mono">
                  &ldquo;{sim.input}&rdquo;
                </div>

                <div className="flex items-center justify-between text-[10px] text-slate-400 pt-0.5">
                  <span>Expected: {sim.expected}</span>
                  <span className="font-mono">{sim.duration}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Trace Pane Content */}
      {activeTab === "trace" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-slate-50/50">
          {/* Run Header Info */}
          <div className="p-2.5 bg-white border border-slate-200 rounded-xl shadow-2xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">
                Run ID: #{selectedRunId}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-bold border border-emerald-200">
                STATUS: OK
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
              <span>Total Waktu: 925ms</span>
              <span>Tokens: 380 (~$0.0006)</span>
            </div>
          </div>

          {/* Timeline steps */}
          <div className="space-y-2 relative pl-2">
            <div className="text-[11px] font-bold text-slate-700 uppercase tracking-wider mb-2">
              Langkah Eksekusi (Timeline)
            </div>

            {traceSteps.map((step, idx) => (
              <div
                key={step.step_no}
                className="relative pl-5 border-l-2 border-blue-200 pb-3 last:border-transparent last:pb-0"
              >
                {/* Timeline node */}
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
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
