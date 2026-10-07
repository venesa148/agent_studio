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
  FileCode2,
  Loader2,
  Copy,
  Key,
  CheckCircle2,
  FileCode,
  Upload,
  FileText,
  ChevronUp,
  Sparkles,
  Layers,
  Code,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";

export type TestPaneTab = "chat" | "trace";

export interface ToolExecutionInfo {
  name: string;
  endpoint?: string;
  source?: string;
  params: Record<string, any>;
  result: any;
  duration_ms: number;
  status?: string;
}

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  toolCalls?: ToolExecutionInfo[];
  status?: "ok" | "escalated" | "blocked" | "error";
  time: string;
}

function ToolExecutionCard({ toolCall }: { toolCall: ToolExecutionInfo }) {
  const [expanded, setExpanded] = useState(false);
  const endpoint = toolCall.endpoint || "https://sisters-given-cloud-nerve.trycloudflare.com";
  const source = toolCall.source || "Database MySQL Web Teman (40 Data RS)";
  const isOk = toolCall.status !== "error";

  return (
    <div className="rounded-xl border border-blue-200/90 bg-gradient-to-r from-blue-50/70 via-indigo-50/40 to-white p-2.5 text-xs shadow-2xs space-y-2 mt-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 font-semibold text-slate-800">
          <Globe className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
          <span className="font-mono text-blue-700">{toolCall.name}()</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold border border-emerald-300">
            HTTP 200 OK
          </span>
        </div>
        <span className="text-[10px] font-mono text-slate-500 font-medium">
          ⏱️ {toolCall.duration_ms}ms
        </span>
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-600 bg-white/90 px-2 py-1.5 rounded-lg border border-slate-200/70 font-mono">
        <div className="flex items-center gap-1 truncate max-w-[260px]" title={endpoint}>
          <span className="text-slate-400 font-sans font-semibold">Hit:</span>
          <span className="text-blue-600 truncate">{endpoint}</span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] font-sans font-semibold text-blue-700 hover:text-blue-900 bg-blue-100/70 hover:bg-blue-100 px-2 py-0.5 rounded cursor-pointer transition-colors shrink-0 ml-1"
        >
          {expanded ? "Tutup Data" : "Lihat JSON"}
        </button>
      </div>

      {expanded && (
        <div className="space-y-1.5 pt-1 animate-in fade-in duration-150">
          <div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-0.5">
              Input Parameter
            </div>
            <pre className="text-[10px] text-slate-700 font-mono bg-white p-2 rounded-lg border border-slate-200 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(toolCall.params, null, 2)}
            </pre>
          </div>
          <div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-0.5 flex items-center justify-between">
              <span>Data MySQL dari Web Teman (Response)</span>
              <span className="text-[9px] text-emerald-600 font-normal">{source}</span>
            </div>
            <pre className="text-[10px] text-slate-700 font-mono bg-white p-2 rounded-lg border border-slate-200 overflow-x-auto max-h-40 whitespace-pre-wrap">
              {typeof toolCall.result === "object"
                ? JSON.stringify(toolCall.result, null, 2)
                : String(toolCall.result)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
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

  // Publish popover states
  const [isPublished, setIsPublished] = useState(false);
  const [showPublishPopover, setShowPublishPopover] = useState(false);
  const [domainSlug, setDomainSlug] = useState("");
  const [accessLevel, setAccessLevel] = useState<"Public" | "Restricted">("Public");
  const [showAccessDropdown, setShowAccessDropdown] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [deployedInfo, setDeployedInfo] = useState<any>(null);
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedEndpoint, setCopiedEndpoint] = useState(false);

  // Dynamic YAML Config Selector states
  const [configSource, setConfigSource] = useState<"chat_agent" | "server_yaml" | "upload_yaml">("chat_agent");
  const [serverYamlFiles, setServerYamlFiles] = useState<Array<{ filename: string; name: string; description: string; content: string }>>([]);
  const [selectedServerFile, setSelectedServerFile] = useState<string>("agent.yaml");
  const [customYamlContent, setCustomYamlContent] = useState<string>("");
  const [showYamlEditor, setShowYamlEditor] = useState<boolean>(false);
  const [uploadedFileName, setUploadedFileName] = useState<string>("");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Helper untuk memformat multiline text ke indentasi YAML yang valid
  const formatYamlBlock = (text: string, indentSpaces: number = 2): string => {
    const pad = " ".repeat(indentSpaces);
    const cleaned = (text || "").replace(/\r\n/g, "\n").trim();
    if (!cleaned) return `${pad}""`;
    return cleaned
      .split("\n")
      .map((line) => `${pad}${line}`)
      .join("\n");
  };

  // Helper untuk generate YAML dari activeAgent di chat
  const generateYamlFromAgent = (agent: AgentSpecData): string => {
    const agentId = agent.id || `agent-${Date.now()}`;
    const agentName = agent.name || "AI Assistant";
    const slugName = agentName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "custom-agent";
    const rawDesc = agent.description || "Agent dibuat melalui sesi chat Agent Studio";
    const rawInstructions = agent.instructions || "Kamu adalah asisten AI yang ramah, profesional, dan membantu.";
    const toolsList = agent.tools && agent.tools.length > 0
      ? agent.tools.map((t) => `  - "${t}"`).join("\n")
      : " []";

    const formattedDesc = formatYamlBlock(rawDesc, 4);
    const formattedInstructions = formatYamlBlock(rawInstructions, 2);

    return `spec_version: v1.0
metadata:
  id: "${agentId}"
  name: "${agentName}"
  slug: "${slugName}"
  description: >
${formattedDesc}
  version: 1
  status: "active"

configuration:
  model: "${agent.model || 'gpt-4o-mini'}"
  harness: "default-safe-v1"

tools:${toolsList.startsWith(" []") ? " []" : "\n" + toolsList}

instructions: |
${formattedInstructions}

flow:
  entry_node: "main_step"
  nodes:
    - id: "main_step"
      type: "llm_step"
      instruction: "Tanggapi pesan pengguna dengan jelas, solutif, dan ramah sesuai dengan instruksi peran agen."
      next: "selesai"
    - id: "selesai"
      type: "end"

tools_required: ${JSON.stringify(agent.tools || [])}
guardrails:
  max_turns: 15
  disallowed_behaviors: []
`;
  };

  // Ambil daftar file YAML dari backend
  const fetchYamlFiles = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/deployment/yaml-files`);
      if (res.ok) {
        const files = await res.json();
        setServerYamlFiles(files);
      }
    } catch (e) {
      console.warn("Gagal mengambil file YAML backend:", e);
    }
  };

  // Ambil status deployment dan daftar file YAML saat komponen dimuat
  useEffect(() => {
    fetch(`${apiUrl}/api/v1/deployment/status`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.status === "live") {
          setIsPublished(true);
          setDeployedInfo(data);
        }
      })
      .catch(() => {});

    fetchYamlFiles();
  }, [apiUrl]);

  // Set default YAML saat activeAgent tersedia
  useEffect(() => {
    if (activeAgent) {
      const generated = generateYamlFromAgent(activeAgent);
      if (configSource === "chat_agent") {
        setCustomYamlContent(generated);
      }
    }
  }, [activeAgent, configSource]);

  // Handler saat mengganti sumber YAML
  const handleSelectConfigSource = (source: "chat_agent" | "server_yaml" | "upload_yaml") => {
    setConfigSource(source);
    if (source === "chat_agent") {
      if (activeAgent) {
        setCustomYamlContent(generateYamlFromAgent(activeAgent));
        setDomainSlug(activeAgent.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
      } else {
        setCustomYamlContent("");
      }
    } else if (source === "server_yaml") {
      const file = serverYamlFiles.find((f) => f.filename === selectedServerFile) || serverYamlFiles[0];
      if (file) {
        setCustomYamlContent(file.content);
        setSelectedServerFile(file.filename);
        setDomainSlug(file.filename.replace(/\.ya?ml$/, ""));
      }
    } else if (source === "upload_yaml") {
      setCustomYamlContent("");
      setUploadedFileName("");
    }
  };

  const handleSelectServerFile = (filename: string) => {
    setSelectedServerFile(filename);
    const file = serverYamlFiles.find((f) => f.filename === filename);
    if (file) {
      setCustomYamlContent(file.content);
      setDomainSlug(file.filename.replace(/\.ya?ml$/, ""));
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFileName(file.name);
    const slugName = file.name.replace(/\.ya?ml$/i, "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
    setDomainSlug(slugName);

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = (event.target?.result as string) || "";
      setCustomYamlContent(content);
    };
    reader.readAsText(file);
  };

  const handlePublishAgent = async () => {
    setIsPublishing(true);
    setPublishError(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);

    try {
      const res = await fetch(`${apiUrl}/api/v1/deployment/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          slug: domainSlug || "agent",
          access_level: accessLevel,
          custom_yaml: customYamlContent.trim() ? customYamlContent : undefined,
        }),
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Gagal mempublikasikan agent");
      }

      const data = await res.json();
      setIsPublished(true);
      setDeployedInfo(data);

      // Sync ke tabel deployments (fitur rekan tim) jika endpoint tersedia
      try {
        await fetch(`${apiUrl}/api/v1/deployments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agent: activeAgent?.name || data.agent_name || "Unknown Agent",
            environment: "production",
            path: `/api/agents/${domainSlug || activeAgent?.id}/run`,
            status: "Ready",
          }),
        });
      } catch (err) {
        // Abaikan jika database/tabel deployments belum siap
      }
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (err.name === "AbortError") {
        setPublishError("Koneksi ke backend timeout. Pastikan backend aktif.");
      } else {
        setPublishError(err.message || "Gagal menghubungkan ke server deployment");
      }
    } finally {
      setIsPublishing(false);
    }
  };

  // Sync and load working memory history when activeAgent changes
  useEffect(() => {
    setTraceSteps([]);
    setErrorMessage(null);
    if (activeAgent?.name) {
      setDomainSlug(activeAgent.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
    }

    if (!activeAgent?.id) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/v1/agent/${activeAgent.id}/history`);
        if (res.ok) {
          const data = await res.json();
          if (isMounted && Array.isArray(data)) {
            const historyMsgs: ChatMessage[] = data.map((m: any) => ({
              id: m.id,
              sender: m.role === "user" ? "user" : "agent",
              text: m.content,
              time: m.created_at
                ? new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                : "Tersimpan",
            }));
            setMessages(historyMsgs);
          }
        }
      } catch (err) {
        console.warn("Gagal memuat riwayat chat agent:", err);
      }
    };

    fetchHistory();
    return () => {
      isMounted = false;
    };
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

    const chatController = new AbortController();
    const chatTimeoutId = setTimeout(() => chatController.abort(), 30000); // 30 detik timeout

    try {
      const res = await fetch(`${apiUrl}/api/v1/agent/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          agent_id: activeAgent.id,
          message: userText,
        }),
        signal: chatController.signal,
      });
      clearTimeout(chatTimeoutId);

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP Error ${res.status}: Gagal memproses pesan.`);
      }

      const data = await res.json();

      const rawTraceSteps = Array.isArray(data.trace_steps) ? data.trace_steps : [];
      const toolCalls: ToolExecutionInfo[] = rawTraceSteps
        .filter((s: any) => s.type === "tool_calling" || (s.tool_name && s.tool_name !== "pre_check_guardrail" && s.tool_name !== "post_check_escalation"))
        .map((s: any) => ({
          name: s.tool_name || s.title || "tool",
          endpoint: s.endpoint || s.result?._endpoint || "https://sisters-given-cloud-nerve.trycloudflare.com",
          source: s.source || s.result?._source || "Database MySQL Web Teman",
          params: s.params || {},
          result: s.result || {},
          duration_ms: s.duration_ms ?? 0,
          status: s.status || "ok",
        }));

      const agentMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "agent",
        text: data.response,
        toolCalls: toolCalls.length > 0 ? toolCalls : undefined,
        status: data.status || "ok",
        time: "Sekarang",
      };

      setMessages((prev) => [...prev, agentMsg]);

      if (rawTraceSteps.length > 0) {
        setTraceSteps(rawTraceSteps);
      }
    } catch (error: any) {
      clearTimeout(chatTimeoutId);
      console.warn("Error testing agent:", error);
      const errTxt =
        error.name === "AbortError"
          ? "⏱️ Request timeout (30 detik). Backend lambat atau LLM tidak merespons. Pastikan OPENAI_API_KEY sudah diset di backend/.env"
          : error.message || "Maaf, terjadi kesalahan saat menghubungi Agent Backend.";
      setErrorMessage(errTxt);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "agent",
          text: `⚠️ ${errTxt}`,
          status: "error",
          time: "Sekarang",
        },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleClear = async () => {
    setMessages([]);
    setTraceSteps([]);
    setErrorMessage(null);
    if (activeAgent?.id) {
      try {
        await fetch(`http://localhost:8000/api/v1/agent/${activeAgent.id}/history`, {
          method: "DELETE",
        });
      } catch (err) {
        console.warn("Gagal mereset sesi percakapan di database:", err);
      }
    }
  };

  const handleExportYaml = async () => {
    if (!activeAgent?.id) return;
    try {
      const res = await fetch(`http://localhost:8000/api/v1/agent/${activeAgent.id}/export-yaml?download=true`);
      if (!res.ok) throw new Error("Gagal mengunduh berkas YAML.");
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      const cleanSlug = (activeAgent.name || "agent").toLowerCase().replace(/[^a-z0-9]+/g, "_");
      a.download = `${cleanSlug}.yaml`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);
    } catch (err) {
      console.warn("Gagal mengekspor YAML:", err);
    }
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

          {/* Tombol Export YAML */}
          <button
            onClick={handleExportYaml}
            disabled={!activeAgent}
            title="Download Declarative Spec (.yaml)"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-all cursor-pointer shadow-2xs disabled:opacity-50 ml-1"
          >
            <FileCode2 className="w-3.5 h-3.5 text-slate-600" />
            <span>YAML</span>
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
                <div className="absolute right-0 top-10 mt-1 w-80 sm:w-[440px] max-h-[85vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl z-40 text-xs space-y-4 animate-in fade-in zoom-in-95 duration-150">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
                        <Globe className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">Publish Agent</h4>
                        <p className="text-[10px] text-slate-500">Deploy agent ke Dedicated AWS Runtime</p>
                      </div>
                    </div>
                    <Link
                      href="/deployments"
                      onClick={() => setShowPublishPopover(false)}
                      className="text-slate-500 hover:text-blue-600 flex items-center gap-1 text-[11px] font-medium"
                    >
                      <span>Settings</span>
                      <ExternalLink className="w-3 h-3" />
                    </Link>
                  </div>

                  {/* 1. Sumber Konfigurasi YAML (Dinamis) */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="font-semibold text-slate-700 text-[11px] flex items-center gap-1.5">
                        <FileCode className="w-3.5 h-3.5 text-blue-600" />
                        <span>Sumber Konfigurasi (.yaml)</span>
                      </label>
                      <span className="text-[10px] text-slate-400 font-medium">Pilih file deploy</span>
                    </div>

                    {/* 3 Tab Selector */}
                    <div className="grid grid-cols-3 gap-1 bg-slate-100 p-1 rounded-xl">
                      <button
                        type="button"
                        onClick={() => handleSelectConfigSource("chat_agent")}
                        className={`py-1.5 px-1.5 rounded-lg font-semibold text-[10.5px] transition-all flex items-center justify-center gap-1 ${
                          configSource === "chat_agent"
                            ? "bg-white text-blue-700 shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        <Sparkles className="w-3 h-3 text-amber-500 shrink-0" />
                        <span className="truncate">Sesi Chat</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleSelectConfigSource("server_yaml")}
                        className={`py-1.5 px-1.5 rounded-lg font-semibold text-[10.5px] transition-all flex items-center justify-center gap-1 ${
                          configSource === "server_yaml"
                            ? "bg-white text-blue-700 shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        <Layers className="w-3 h-3 text-indigo-500 shrink-0" />
                        <span className="truncate">File Server</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleSelectConfigSource("upload_yaml")}
                        className={`py-1.5 px-1.5 rounded-lg font-semibold text-[10.5px] transition-all flex items-center justify-center gap-1 ${
                          configSource === "upload_yaml"
                            ? "bg-white text-blue-700 shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        <Upload className="w-3 h-3 text-emerald-500 shrink-0" />
                        <span className="truncate">Upload</span>
                      </button>
                    </div>

                    {/* Konten detail sesuai sumber terpilih */}
                    {configSource === "chat_agent" && (
                      <div className="p-2.5 rounded-xl border border-blue-100 bg-blue-50/40 flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <Bot className="w-4 h-4 text-blue-600 shrink-0" />
                          <div className="min-w-0">
                            <div className="font-semibold text-slate-800 text-[11px] truncate">
                              {activeAgent?.name || "Agent Sesi Chat Saat Ini"}
                            </div>
                            <div className="text-[10px] text-slate-500 truncate">
                              {activeAgent?.description || "Dikonversi otomatis dari sesi chat builder"}
                            </div>
                          </div>
                        </div>
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 font-bold shrink-0 ml-2">
                          Auto-YAML
                        </span>
                      </div>
                    )}

                    {configSource === "server_yaml" && (
                      <div className="space-y-1.5">
                        <select
                          value={selectedServerFile}
                          onChange={(e) => handleSelectServerFile(e.target.value)}
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-slate-50/60 text-xs font-medium text-slate-800 outline-hidden focus:border-blue-500 focus:bg-white"
                        >
                          {serverYamlFiles.map((f) => (
                            <option key={f.filename} value={f.filename}>
                              📄 {f.name} ({f.filename})
                            </option>
                          ))}
                        </select>
                        <div className="text-[10px] text-slate-500 px-1">
                          {serverYamlFiles.find((f) => f.filename === selectedServerFile)?.description || "File konfigurasi YAML dari server backend"}
                        </div>
                      </div>
                    )}

                    {configSource === "upload_yaml" && (
                      <div>
                        <label className="flex flex-col items-center justify-center p-3 border-2 border-dashed border-slate-200 hover:border-blue-400 bg-slate-50/50 hover:bg-blue-50/20 rounded-xl cursor-pointer transition-all">
                          <Upload className="w-4 h-4 text-slate-400 mb-1" />
                          <span className="text-[11px] font-semibold text-slate-700">
                            {uploadedFileName ? `📄 ${uploadedFileName}` : "Pilih file .yaml dari komputer"}
                          </span>
                          <span className="text-[10px] text-slate-400">Klik untuk browse file YAML</span>
                          <input
                            type="file"
                            accept=".yaml,.yml"
                            onChange={handleFileUpload}
                            className="hidden"
                          />
                        </label>
                      </div>
                    )}

                    {/* Collapsible Preview & Edit YAML Code */}
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => setShowYamlEditor(!showYamlEditor)}
                        className="flex items-center justify-between w-full text-[11px] text-slate-600 hover:text-blue-600 font-medium py-1 transition-colors"
                      >
                        <span className="flex items-center gap-1.5">
                          <Code className="w-3.5 h-3.5 text-slate-500" />
                          <span>Preview / Edit YAML ({customYamlContent ? customYamlContent.split('\n').length : 0} baris)</span>
                        </span>
                        <span className="text-[10px] text-blue-600 font-semibold">
                          {showYamlEditor ? "Tutup" : "Buka"}
                        </span>
                      </button>

                      {showYamlEditor && (
                        <div className="mt-1.5 rounded-xl border border-slate-800 overflow-hidden bg-slate-950 text-slate-100 shadow-inner">
                          <div className="px-3 py-1 bg-slate-900 text-[10px] text-slate-400 font-mono flex items-center justify-between border-b border-slate-800">
                            <span>YAML Specification</span>
                            <span>Editable</span>
                          </div>
                          <textarea
                            value={customYamlContent}
                            onChange={(e) => setCustomYamlContent(e.target.value)}
                            rows={7}
                            className="w-full p-2.5 bg-slate-950 text-emerald-400 font-mono text-[10.5px] outline-hidden resize-y leading-relaxed"
                            placeholder="Ketik atau paste konfigurasi agent.yaml..."
                          />
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 2. Domain / Slug */}
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

                  {publishError && (
                    <div className="p-2.5 rounded-xl bg-red-50 border border-red-200 text-red-700 text-[11px] flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>{publishError}</span>
                    </div>
                  )}

                  {isPublished && deployedInfo && (
                    <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-[11px] space-y-2">
                      <div className="flex items-center justify-between text-emerald-800 font-bold">
                        <span className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          Agent Live & Aktif!
                        </span>
                        <span className="text-[10px] bg-emerald-200/60 px-1.5 py-0.5 rounded font-mono">
                          v{deployedInfo.version}
                        </span>
                      </div>

                      <div className="space-y-1">
                        <div className="text-[10px] text-emerald-700 font-semibold">Live Invoke Endpoint:</div>
                        <div className="flex items-center gap-1 bg-white p-1.5 rounded-lg border border-emerald-200 font-mono text-[10px] text-slate-800 overflow-x-auto">
                          <span className="truncate flex-1">{deployedInfo.endpoint}</span>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(deployedInfo.endpoint);
                              setCopiedEndpoint(true);
                              setTimeout(() => setCopiedEndpoint(false), 2000);
                            }}
                            className="p-1 hover:bg-slate-100 rounded text-slate-500"
                            title="Copy Endpoint"
                          >
                            {copiedEndpoint ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="text-[10px] text-emerald-700 font-semibold">API Key:</div>
                        <div className="flex items-center gap-1 bg-white p-1.5 rounded-lg border border-emerald-200 font-mono text-[10px] text-slate-800 overflow-x-auto">
                          <span className="truncate flex-1">{deployedInfo.api_key}</span>
                          <button
                            type="button"
                            onClick={() => {
                              navigator.clipboard.writeText(deployedInfo.api_key);
                              setCopiedKey(true);
                              setTimeout(() => setCopiedKey(false), 2000);
                            }}
                            className="p-1 hover:bg-slate-100 rounded text-slate-500"
                            title="Copy Key"
                          >
                            {copiedKey ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="pt-2 flex items-center gap-2">
                    <button
                      type="button"
                      disabled={isPublishing}
                      onClick={handlePublishAgent}
                      className="flex-1 py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold text-center shadow-2xs transition-colors cursor-pointer text-xs flex items-center justify-center gap-1.5"
                    >
                      {isPublishing ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Publishing ke Runtime...</span>
                        </>
                      ) : (
                        <span>{isPublished ? "Perbarui / Re-Publish" : "Publish Agent"}</span>
                      )}
                    </button>
                    {isPublished && (
                      <button
                        type="button"
                        disabled={isPublishing}
                        onClick={() => {
                          setIsPublished(false);
                          setShowPublishPopover(false);
                        }}
                        className="py-2.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-center transition-colors cursor-pointer text-xs"
                      >
                        Unpublish
                      </button>
                    )}
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

                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="ml-8 space-y-1.5">
                      {msg.toolCalls.map((tc, tcIdx) => (
                        <ToolExecutionCard key={tcIdx} toolCall={tc} />
                      ))}
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
              traceSteps.map((step, idx) => {
                const stepNum = step.step_no ?? step.step ?? idx + 1;
                const toolName = step.tool_name ?? step.title ?? "Eksekusi Tool";
                const isError = step.status === "error";
                const paramsStr = step.params
                  ? typeof step.params === "object"
                    ? JSON.stringify(step.params, null, 2)
                    : String(step.params)
                  : null;
                const resultStr = step.result
                  ? typeof step.result === "object"
                    ? JSON.stringify(step.result, null, 2)
                    : String(step.result)
                  : step.detail ?? null;

                return (
                  <div
                    key={stepNum}
                    className="relative pl-5 border-l-2 border-blue-200 pb-3 last:border-transparent last:pb-0"
                  >
                    <span
                      className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ring-4 ring-white ${
                        isError ? "bg-rose-500" : "bg-blue-600"
                      }`}
                    />

                    <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold text-slate-800">
                            Step {stepNum}:
                          </span>
                          <span className="px-2 py-0.5 text-[11px] font-mono font-semibold rounded bg-blue-50 text-blue-700 border border-blue-200">
                            {toolName}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {step.duration_ms !== undefined && (
                            <span className="text-[10px] font-mono text-slate-400">
                              {step.duration_ms}ms
                            </span>
                          )}
                          <span
                            className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                              isError
                                ? "bg-rose-50 text-rose-600 border border-rose-200"
                                : "bg-emerald-50 text-emerald-600 border border-emerald-200"
                            }`}
                          >
                            {isError ? "ERROR" : "OK"}
                          </span>
                        </div>
                      </div>

                      {step.endpoint && (
                        <div className="flex items-center gap-1.5 text-[10px] font-mono text-blue-700 bg-blue-50/80 px-2 py-1 rounded-lg border border-blue-200/80">
                          <Globe className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                          <span className="text-slate-500 font-sans font-bold">Hit:</span>
                          <span className="truncate text-blue-600 font-medium" title={step.endpoint}>
                            {step.endpoint}
                          </span>
                        </div>
                      )}

                      {paramsStr && (
                        <div>
                          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-0.5">
                            Parameter Input
                          </div>
                          <pre className="text-[11px] text-slate-700 font-mono bg-slate-50 p-2 rounded border border-slate-100 overflow-x-auto whitespace-pre-wrap">
                            {paramsStr}
                          </pre>
                        </div>
                      )}

                      {resultStr && (
                        <div>
                          <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-0.5">
                            Hasil Tool (Output)
                          </div>
                          <pre className="text-[11px] text-slate-700 font-mono bg-slate-50 p-2 rounded border border-slate-100 overflow-x-auto max-h-36 whitespace-pre-wrap">
                            {resultStr}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
