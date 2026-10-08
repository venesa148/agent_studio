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
  Shield,
  Cpu,
  Globe,
  Terminal,
  Copy,
  Check,
  Clock,
  Sparkle,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";
import { AgentDraft, saveDraft, deleteDraft, getDraftById } from "@/lib/draftStore";

interface Message {
  id: string;
  sender: "user" | "builder";
  text: string;
  spec?: AgentSpecData;
  is_draft?: boolean;
  time?: string;
}

interface BuildAgentChatPaneProps {
  activeAgent?: AgentSpecData | null;
  activeDraftId?: string | null;
  onAgentCreated?: (agentSpec: AgentSpecData) => void;
  onClearActiveAgent?: () => void;
}

export function BuildAgentChatPane({
  activeAgent,
  activeDraftId,
  onAgentCreated,
  onClearActiveAgent,
}: BuildAgentChatPaneProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isBuilding, setIsBuilding] = useState(false);
  const [showSpecDetails, setShowSpecDetails] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [dbTools, setDbTools] = useState<any[]>([]);
  const [copiedPromptId, setCopiedPromptId] = useState<string | null>(null);
  const [activeDraft, setActiveDraft] = useState<AgentDraft | null>(null);

  const handleCopyPrompt = (promptText: string, id: string) => {
    if (!navigator?.clipboard) return;
    navigator.clipboard.writeText(promptText);
    setCopiedPromptId(id);
    setTimeout(() => setCopiedPromptId(null), 2000);
  };

  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const skipClearRef = React.useRef(false);
  const currentAgentIdRef = React.useRef<string | undefined>(undefined);
  const currentDraftIdRef = React.useRef<string | undefined>(undefined);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const getStorageKey = (agentId?: string) => `builder_chat_history_${agentId || "global"}`;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    scrollToBottom();
  }, [messages, isBuilding]);

  // Simpan riwayat chat builder ke localStorage setiap kali ada perubahan
  useEffect(() => {
    if (typeof window !== "undefined" && messages.length > 0) {
      try {
        localStorage.setItem(getStorageKey(currentAgentIdRef.current), JSON.stringify(messages));
      } catch (e) {
        console.warn("Gagal menyimpan riwayat chat builder ke localStorage:", e);
      }
    }
  }, [messages]);

  // Handle draft loading via activeDraftId
  useEffect(() => {
    if (activeDraftId) {
      const draft = getDraftById(activeDraftId);
      if (draft) {
        currentDraftIdRef.current = draft.id;
        setActiveDraft(draft);
        currentAgentIdRef.current = undefined;
        if (draft.messages && draft.messages.length > 0) {
          setMessages(draft.messages);
        } else {
          setMessages([
            {
              id: `draft-init-${draft.id}`,
              sender: "builder",
              text: `Draf '${draft.name}' berhasil dimuat dari penyimpanan lokal. Anda dapat melanjutkan instruksi ke builder untuk menyempurnakannya atau langsung menekan tombol 'Terapkan ke DB'.`,
              spec: draft as any,
              is_draft: true,
              time: "Draf Lokal",
            },
          ]);
        }
        setInput("");
        setErrorMessage(null);
        setSaveSuccessMsg(null);
        return;
      }
    } else if (!activeAgent) {
      currentDraftIdRef.current = undefined;
      setActiveDraft(null);
    }
  }, [activeDraftId]);

  useEffect(() => {
    if (activeDraftId) {
      return;
    }

    if (!activeAgent) {
      if (currentAgentIdRef.current !== undefined) {
        // Coba pulihkan riwayat chat sesi global/tanpa agen jika ada
        const saved = typeof window !== "undefined" ? localStorage.getItem(getStorageKey()) : null;
        if (saved) {
          try {
            setMessages(JSON.parse(saved));
          } catch {
            setMessages([]);
          }
        } else {
          setMessages([]);
        }
        setInput("");
        setErrorMessage(null);
        setSaveSuccessMsg(null);
      }
      currentAgentIdRef.current = undefined;
      return;
    }

    // Jika activeAgent adalah draft
    if (activeAgent.id && activeAgent.id.startsWith("draft_")) {
      const draft = getDraftById(activeAgent.id);
      if (draft) {
        currentDraftIdRef.current = draft.id;
        setActiveDraft(draft);
        currentAgentIdRef.current = undefined;
        if (draft.messages && draft.messages.length > 0) {
          setMessages(draft.messages);
          return;
        }
      }
    }

    if (currentAgentIdRef.current !== activeAgent.id) {
      currentDraftIdRef.current = undefined;
      setActiveDraft(null);
      if (!skipClearRef.current) {
        const loadHistory = async () => {
          try {
            const res = await fetch(`${apiUrl}/api/v1/builder/history/${activeAgent.id}`);
            if (res.ok) {
              const apiMessages = await res.json();
              if (apiMessages && apiMessages.length > 0) {
                const updated = apiMessages.map((m: any, idx: number) => {
                  if (idx === apiMessages.length - 1 && m.spec) {
                    return { ...m, spec: { ...m.spec, ...activeAgent } };
                  }
                  return m;
                });
                setMessages(updated);
                setInput("");
                setErrorMessage(null);
                setSaveSuccessMsg(null);
                return;
              }
            }
          } catch (e) {
            console.warn("Gagal memuat history builder dari backend:", e);
          }

          // Fallback to localStorage
          const saved = typeof window !== "undefined" ? localStorage.getItem(getStorageKey(activeAgent.id)) : null;
          let loadedMessages: Message[] = [];
          if (saved) {
            try {
              loadedMessages = JSON.parse(saved);
            } catch (e) {
              console.warn("Gagal mem-parsing cached messages:", e);
            }
          }

          if (loadedMessages.length > 0) {
            const updated = loadedMessages.map((m, idx) => {
              if (idx === loadedMessages.length - 1 && m.spec) {
                return { ...m, spec: { ...m.spec, ...activeAgent } };
              }
              return m;
            });
            setMessages(updated);
          } else {
            const initialMsgs: Message[] = [
              {
                id: `system-spec-${activeAgent.id}`,
                sender: "builder",
                text: `Berikut adalah konfigurasi aktif untuk Agent '${activeAgent.name}'. Anda dapat langsung mengubahnya melalui form di bawah ini, atau memberi instruksi perubahan melalui chat.`,
                spec: activeAgent,
                is_draft: false,
                time: "Sistem",
              }
            ];
            setMessages(initialMsgs);
            if (typeof window !== "undefined") {
              try {
                localStorage.setItem(getStorageKey(activeAgent.id), JSON.stringify(initialMsgs));
              } catch { }
            }
          }
          setInput("");
          setErrorMessage(null);
          setSaveSuccessMsg(null);
        };
        
        loadHistory();
      }
      currentAgentIdRef.current = activeAgent.id;
    }
  }, [activeAgent, apiUrl]);

  useEffect(() => {
    fetch("/api/v1/tools")
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


  const handleSend = async (customPrompt?: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const promptToSend = typeof customPrompt === "string" ? customPrompt : input;
    if (!promptToSend.trim() || isBuilding) return;

    setErrorMessage(null);
    setSaveSuccessMsg(null);

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: "user",
      text: promptToSend,
      time: "Baru saja",
    };

    setMessages((prev) => [...prev, userMsg]);
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
        body: JSON.stringify({ prompt: promptToSend, current_spec: currentSpec, history }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Gagal membangun agent dari backend.");
      }

      const data = await res.json();

      const builderResponse: Message = {
        id: (Date.now() + 1).toString(),
        sender: "builder",
        text: data.message || `Draf spesifikasi Agent telah diperbarui.`,
        spec: data.spec,
        is_draft: data.is_draft,
        time: "Baru saja",
      };

      const newMessages = [...messages, userMsg, builderResponse];
      setMessages(newMessages);

      // Simpan ke DRAFT STORE jika berstatus draft / belum disimpan di database
      if (data.is_draft !== false || !data.spec?.id) {
        if (!currentDraftIdRef.current) {
          currentDraftIdRef.current = `draft_${Date.now()}`;
        }
        const savedDraft = saveDraft({
          id: currentDraftIdRef.current,
          name: data.spec?.name || "Draf Agen Baru",
          description: data.spec?.description || "",
          instructions: data.spec?.instructions || "",
          model: data.spec?.model || "z-ai/glm-5.3",
          tools: data.spec?.tools || [],
          mcp_servers: data.spec?.mcp_servers || [],
          harness: data.spec?.harness || "default-safe-v1",
          messages: newMessages,
        });
        setActiveDraft(savedDraft);
        if (typeof window !== "undefined" && !window.location.search.includes("id=")) {
          window.history.replaceState({}, '', `/?draft_id=${savedDraft.id}`);
        }
      }

      // HANYA update activeAgent jika sudah committed / bukan draft
      if (data.spec && data.is_draft === false && data.spec.id) {
        if (currentDraftIdRef.current) {
          deleteDraft(currentDraftIdRef.current);
          currentDraftIdRef.current = undefined;
          setActiveDraft(null);
        }
        skipClearRef.current = true;
        currentAgentIdRef.current = data.spec.id;
        onAgentCreated?.(data.spec);
        setTimeout(() => {
          skipClearRef.current = false;
        }, 500);
        setSaveSuccessMsg(`Agent '${data.spec.name}' berhasil disimpan ke database!`);
        setTimeout(() => setSaveSuccessMsg(null), 4000);
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
    if (currentDraftIdRef.current) {
      deleteDraft(currentDraftIdRef.current);
      currentDraftIdRef.current = undefined;
      setActiveDraft(null);
    }
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem(getStorageKey(currentAgentIdRef.current));
      } catch { }
      window.history.replaceState({}, '', '/?new=true');
    }
    setMessages([]);
    setInput("");
    setErrorMessage(null);
    setSaveSuccessMsg(null);
    onClearActiveAgent?.();
  };

  const handleSpecChange = (msgId: string, field: string, value: any) => {
    setMessages((prev) => {
      const updated = prev.map((msg) => {
        if (msg.id === msgId && msg.spec) {
          return { ...msg, spec: { ...msg.spec, [field]: value } };
        }
        return msg;
      });

      if (currentDraftIdRef.current) {
        const lastSpec = updated.slice().reverse().find((m) => m.spec)?.spec;
        if (lastSpec) {
          const updatedDraft = saveDraft({
            id: currentDraftIdRef.current,
            name: lastSpec.name || "Draf Agen",
            description: lastSpec.description,
            instructions: lastSpec.instructions,
            model: lastSpec.model,
            tools: lastSpec.tools,
            mcp_servers: lastSpec.mcp_servers,
            harness: lastSpec.harness,
            messages: updated,
          });
          setActiveDraft(updatedDraft);
        }
      }

      return updated;
    });
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

      // Update local message status tanpa menghapus riwayat chat
      const updatedMessages = messages.map((m) =>
        m.spec ? { ...m, spec: savedSpec, is_draft: false } : m
      );
      setMessages(updatedMessages);

      if (typeof window !== "undefined") {
        try {
          localStorage.setItem(getStorageKey(savedSpec.id), JSON.stringify(updatedMessages));
        } catch { }
      }

      // Hapus dari draft store jika sebelumnya berstatus draf
      if (currentDraftIdRef.current) {
        deleteDraft(currentDraftIdRef.current);
        currentDraftIdRef.current = undefined;
        setActiveDraft(null);
      }

      // Save history to backend
      try {
        await fetch(`${apiUrl}/api/v1/builder/history/${savedSpec.id}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: updatedMessages }),
        });
      } catch (err) {
        console.warn("Gagal menyimpan history builder ke backend:", err);
      }

      skipClearRef.current = true;
      currentAgentIdRef.current = savedSpec.id;
      onAgentCreated?.(savedSpec);

      setTimeout(() => {
        skipClearRef.current = false;
      }, 1000);

      setSaveSuccessMsg(`Agent '${savedSpec.name}' berhasil disimpan ke database dan aktif untuk diuji!`);
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
      const res = await fetch(`/api/v1/agent/${spec.id}/export-yaml?download=true`);
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
          {activeDraft ? (
            <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 font-semibold border border-amber-200 flex items-center gap-1.5 shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              <span>Draf: {activeDraft.name}</span>
            </span>
          ) : activeAgent ? (
            <span className="text-[11px] px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-medium border border-blue-200">
              Active: {activeAgent.name}
            </span>
          ) : null}
          <button
            onClick={handleReset}
            title="Reset / Buat Agent Baru"
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
                  className={`flex gap-3 ${msg.sender === "user" ? "justify-end" : "justify-start"
                    }`}
                >
                  {msg.sender === "builder" && (
                    <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0 text-xs shadow-2xs">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-2xs ${msg.sender === "user"
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

                {/* Generated Spec Preview Card (Studio Bento Deck Layout) */}
                {msg.spec && (
                  <div className="ml-10 rounded-2xl border border-slate-200/90 bg-white shadow-xs overflow-hidden transition-all">
                    {/* Card Header Bar */}
                    <div className="px-4 py-3 bg-gradient-to-r from-slate-50 via-white to-blue-50/40 border-b border-slate-200/80 flex items-center justify-between">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-blue-600/10 text-blue-600 flex items-center justify-center shrink-0">
                          <Sparkles className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-xs font-bold text-slate-800 truncate">
                              {msg.spec.name || "Agent Tanpa Nama"}
                            </span>
                            {msg.spec.id && !msg.is_draft ? (
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/80">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                Tersimpan di DB
                              </span>
                            ) : msg.spec.id ? (
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-50 text-blue-700 border border-blue-200/80">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                                Draf Siap Uji
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200/80">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                                Draf Baru
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {msg.spec.id && (
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded-md">
                            DB: {msg.spec.id.substring(0, 8)}
                          </span>
                        )}
                        <button
                          onClick={() => setShowSpecDetails(!showSpecDetails)}
                          className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                          title={showSpecDetails ? "Sembunyikan spesifikasi" : "Lihat spesifikasi"}
                        >
                          {showSpecDetails ? (
                            <ChevronDown className="w-4 h-4" />
                          ) : (
                            <ChevronRight className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>

                    {showSpecDetails && (
                      <div className="p-4 space-y-3.5">
                        {/* 1. Agent Identity & Settings Bento Block */}
                        <div className="rounded-xl bg-slate-50/80 p-3.5 border border-slate-200/70 space-y-3">
                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                              Nama Agent
                            </label>
                            <input
                              type="text"
                              value={msg.spec.name}
                              onChange={(e) => handleSpecChange(msg.id, "name", e.target.value)}
                              placeholder="Nama agent..."
                              className="w-full text-xs font-semibold text-slate-900 bg-white px-3 py-2 rounded-lg border border-slate-200 shadow-2xs hover:border-slate-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-hidden transition-all"
                            />
                          </div>

                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                              Deskripsi Peran
                            </label>
                            <textarea
                              value={msg.spec.description || ""}
                              onChange={(e) => handleSpecChange(msg.id, "description", e.target.value)}
                              placeholder="Deskripsi peran dan cakupan agent..."
                              className="w-full text-xs text-slate-600 bg-white px-3 py-2 rounded-lg border border-slate-200 shadow-2xs hover:border-slate-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-hidden transition-all resize-none"
                              rows={2}
                            />
                          </div>

                          <div className="flex flex-wrap items-center gap-2 pt-0.5">
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200/70 text-[11px] font-medium shadow-2xs">
                              <Shield className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                              <span className="text-slate-500 text-[10px]">Harness:</span>
                              <span>{msg.spec.harness || "default-safe-v1"}</span>
                            </div>
                            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-800 border border-indigo-200/70 text-[11px] font-mono font-medium shadow-2xs">
                              <Cpu className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                              <span className="text-slate-500 text-[10px] font-sans">Model:</span>
                              <span>{msg.spec.model || "z-ai/glm-5.3"}</span>
                            </div>
                          </div>
                        </div>

                        {/* 2. System Prompt Deck */}
                        <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-2xs">
                          <div className="px-3.5 py-2 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                              <span className="text-[11px] font-semibold text-slate-200">
                                Instruksi Sistem (System Prompt)
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] font-mono text-slate-400">
                                {(msg.spec.instructions || "").length} karakter
                              </span>
                              <button
                                type="button"
                                onClick={() => handleCopyPrompt(msg.spec?.instructions || "", msg.id)}
                                className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700 transition-colors cursor-pointer"
                                title="Salin instruksi prompt ke clipboard"
                              >
                                {copiedPromptId === msg.id ? (
                                  <>
                                    <Check className="w-3 h-3 text-emerald-400" />
                                    <span className="text-emerald-400 font-medium">Tersalin</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3" />
                                    <span>Salin</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </div>
                          <textarea
                            value={msg.spec.instructions || ""}
                            onChange={(e) => handleSpecChange(msg.id, "instructions", e.target.value)}
                            placeholder="Tulis instruksi sistem untuk memandu respons dan batasan perilaku agent..."
                            className="w-full bg-slate-900 text-emerald-300 font-mono text-[11px] leading-relaxed p-3 focus:outline-hidden resize-y min-h-[96px] placeholder-slate-600 selection:bg-cyan-900 selection:text-white"
                            rows={4}
                          />
                        </div>

                        {/* 3. Capabilities & Tools Integration Hub */}
                        <div className="rounded-xl bg-slate-50/80 p-3.5 border border-slate-200/70 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="w-5 h-5 rounded-md bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                                <Wrench className="w-3 h-3" />
                              </div>
                              <span className="text-xs font-semibold text-slate-800">
                                Kapabilitas &amp; Tools Terpasang
                              </span>
                            </div>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700">
                              {msg.spec.tools?.length || 0} Tools
                            </span>
                          </div>

                          {/* Active Tools Badges */}
                          <div className="flex flex-wrap gap-1.5 min-h-[28px] items-center">
                            {msg.spec.tools && msg.spec.tools.length > 0 ? (
                              msg.spec.tools.map((tool) => {
                                const toolObj = dbTools.find((t) => t.name === tool);
                                const isMcp = toolObj?.source_type === "mcp";
                                const isApi = toolObj?.source_type === "api" || toolObj?.source_type === "web_api";
                                return (
                                  <span
                                    key={tool}
                                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-mono border shadow-2xs transition-all ${
                                      isMcp
                                        ? "bg-purple-50 text-purple-700 border-purple-200/80 hover:border-purple-300"
                                        : isApi
                                        ? "bg-cyan-50 text-cyan-800 border-cyan-200/80 hover:border-cyan-300"
                                        : "bg-blue-50 text-blue-700 border-blue-200/80 hover:border-blue-300"
                                    }`}
                                    title={toolObj?.description || tool}
                                  >
                                    <span className="text-[8px] uppercase px-1 py-0.2 rounded bg-black/5 font-sans font-bold">
                                      {toolObj?.source_type || "tool"}
                                    </span>
                                    <span className="font-semibold">{tool}()</span>
                                    <button
                                      type="button"
                                      onClick={() => handleToggleTool(msg.id, tool)}
                                      className="text-slate-400 hover:text-rose-600 font-bold ml-0.5 p-0.5 hover:bg-black/5 rounded transition-colors cursor-pointer"
                                      title="Hapus tool ini dari agent"
                                    >
                                      ✕
                                    </button>
                                  </span>
                                );
                              })
                            ) : (
                              <span className="text-slate-400 text-xs italic py-1">
                                Belum ada tool yang dipasang ke agent ini.
                              </span>
                            )}
                          </div>

                          {/* Available Tools Catalog from Database */}
                          {dbTools.length > 0 && (
                            <div className="pt-2 border-t border-slate-200/60 space-y-1.5">
                              <span className="text-[10px] text-slate-500 font-medium block">
                                Katalog Tools Database (Klik untuk pasang / lepas):
                              </span>
                              <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto pr-1">
                                {dbTools.map((dbTool) => {
                                  const isSelected = msg.spec?.tools?.includes(dbTool.name);
                                  const isMcp = dbTool.source_type === "mcp";
                                  const isApi = dbTool.source_type === "api" || dbTool.source_type === "web_api";
                                  return (
                                    <button
                                      key={dbTool.id || dbTool.name}
                                      type="button"
                                      onClick={() => handleToggleTool(msg.id, dbTool.name)}
                                      className={`px-2.5 py-1 rounded-lg text-[10px] font-mono border transition-all cursor-pointer flex items-center gap-1.5 ${
                                        isSelected
                                          ? isMcp
                                            ? "bg-purple-600 text-white border-purple-600 font-semibold shadow-2xs"
                                            : isApi
                                            ? "bg-cyan-600 text-white border-cyan-600 font-semibold shadow-2xs"
                                            : "bg-blue-600 text-white border-blue-600 font-semibold shadow-2xs"
                                          : "bg-white text-slate-600 border-slate-200/80 hover:bg-slate-100 hover:border-slate-300 shadow-2xs"
                                      }`}
                                      title={dbTool.description || dbTool.name}
                                    >
                                      <span className="font-bold text-xs">{isSelected ? "✓" : "+"}</span>
                                      {isMcp ? (
                                        <span className="text-[8px] px-1 rounded bg-black/10 uppercase font-sans">MCP</span>
                                      ) : isApi ? (
                                        <span className="text-[8px] px-1 rounded bg-black/10 uppercase font-sans">API</span>
                                      ) : null}
                                      <span>{dbTool.name}</span>
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* 4. Action Toolbar */}
                        <div className="pt-1 flex items-center justify-between gap-3">
                          <div className="text-xs">
                            {msg.spec.id && !msg.is_draft ? (
                              <span className="text-emerald-700 flex items-center gap-1.5 font-medium">
                                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                                Aktif &amp; tersinkronisasi di Test Chat
                              </span>
                            ) : msg.spec.id ? (
                              <span className="text-blue-700 flex items-center gap-1.5 font-medium text-xs">
                                <AlertCircle className="w-4 h-4 text-blue-600 shrink-0" />
                                Perubahan belum disimpan ke database
                              </span>
                            ) : (
                              <span className="text-amber-700 flex items-center gap-1.5 font-medium text-xs">
                                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                                Draf baru belum disimpan ke database
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {msg.spec.id && (
                              <button
                                type="button"
                                onClick={() => handleExportYaml(msg.spec!)}
                                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 shadow-2xs text-xs font-semibold transition-all cursor-pointer hover:border-slate-300"
                                title="Unduh berkas spesifikasi deklaratif .yaml"
                              >
                                <FileCode2 className="w-3.5 h-3.5 text-emerald-600" />
                                Export .YAML
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => handleSaveSpec(msg.spec!)}
                              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer ${
                                msg.spec.id && !msg.is_draft
                                  ? "bg-slate-800 hover:bg-slate-900"
                                  : "bg-blue-600 hover:bg-blue-700 ring-2 ring-blue-300 ring-offset-1"
                              }`}
                            >
                              <CheckCircle2 className="w-4 h-4" />
                              {msg.spec.id && !msg.is_draft
                                ? "Simpan Perubahan"
                                : msg.spec.id
                                  ? "Terapkan Perubahan ke DB"
                                  : "Terapkan & Simpan ke DB"}
                            </button>
                          </div>
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
                <span>Builder Agent sedang menganalisis &amp; merancang spesifikasi...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Input Bar */}
      <div className="p-4 bg-white shrink-0 border-t border-slate-100">
        {messages.length > 0 && !isBuilding && (
          <div className="flex items-center gap-1.5 overflow-x-auto pb-2.5 px-1 text-[11px] text-slate-500">
            <span className="text-[10px] text-slate-400 shrink-0 font-medium">Saran Balasan:</span>
            <button
              type="button"
              onClick={() => handleSend("Tolong buatkan draf spesifikasi lengkapnya sekarang")}
              className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors whitespace-nowrap cursor-pointer"
            >
              📝 Buatkan draf sekarang
            </button>
            <button
              type="button"
              onClick={() => handleSend("Tambahkan batasan keamanan dan SOP yang ketat")}
              className="px-2.5 py-1 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors whitespace-nowrap cursor-pointer"
            >
              🛡️ Tambah batasan SOP
            </button>
            <button
              type="button"
              onClick={() => handleSend("Sudah pas, tolong simpan agen ini ke database")}
              className="px-2.5 py-1 rounded-full bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 transition-colors whitespace-nowrap cursor-pointer font-medium"
            >
              ✅ Simpan sekarang
            </button>
          </div>
        )}

        <form
          onSubmit={(e) => handleSend(undefined, e)}
          className="relative flex items-center border border-slate-200 rounded-2xl px-3 py-2 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition-all shadow-2xs"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ketik kebutuhan atau jawaban Anda ke Builder Agent..."
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
