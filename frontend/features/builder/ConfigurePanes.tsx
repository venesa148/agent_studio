"use client";

import React, { useState, useEffect } from "react";
import {
  Wrench,
  ShieldCheck,
  Smartphone,
  AtSign,
  SlidersHorizontal,
  BookOpen,
  MessageSquareCode,
  Plus,
  Check,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Sparkles,
  Cpu,
  Zap,
  Lock,
  RefreshCw,
  FileText,
  Sliders,
  ChevronRight,
  UserCheck,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";

interface ConfigurePanesProps {
  activeTab: string;
  activeAgent: AgentSpecData | null;
  onUpdateAgent: (updated: AgentSpecData) => void;
  onSwitchToGhostwriter: (initialPrompt?: string) => void;
}

export function ConfigurePanes({
  activeTab,
  activeAgent,
  onUpdateAgent,
  onSwitchToGhostwriter,
}: ConfigurePanesProps) {
  const [allDbTools, setAllDbTools] = useState<any[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);
  const [saveToast, setSaveToast] = useState<string | null>(null);

  // Guardrails local state (defaults to false for fresh agents, or loads from DB)
  const [topicBlock, setTopicBlock] = useState(Boolean(activeAgent?.guardrails?.topic_block));
  const [piiMask, setPiiMask] = useState(Boolean(activeAgent?.guardrails?.pii_mask));
  const [mutationConfirm, setMutationConfirm] = useState(Boolean(activeAgent?.guardrails?.mutation_confirm));
  const [humanHandoff, setHumanHandoff] = useState(Boolean(activeAgent?.guardrails?.human_handoff));

  // Model local state
  const [selectedModel, setSelectedModel] = useState(activeAgent?.model || "z-ai/glm-5.3");
  const [temperature, setTemperature] = useState(activeAgent?.guardrails?.temperature ?? 0.3);

  // Limits local state (loads from DB or default)
  const [maxCalls, setMaxCalls] = useState(activeAgent?.guardrails?.max_calls ?? 5);
  const [timeoutSec, setTimeoutSec] = useState(activeAgent?.guardrails?.timeout_sec ?? 30);

  // Knowledge local state (from database)
  const [knowledgeList, setKnowledgeList] = useState<string[]>([]);
  const [isLoadingKnowledge, setIsLoadingKnowledge] = useState(false);
  const [newKnowledgeTitle, setNewKnowledgeTitle] = useState("");

  // Journeys local state (from database)
  const [journeysList, setJourneysList] = useState<any[]>([]);
  const [isLoadingJourneys, setIsLoadingJourneys] = useState(false);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

  // Fetch all tools from DB
  useEffect(() => {
    const fetchTools = async () => {
      try {
        setIsLoadingTools(true);
        const res = await fetch(`${apiUrl}/api/v1/tools`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) setAllDbTools(data);
        }
      } catch (e) {
        console.warn("Failed to fetch tools catalog:", e);
      } finally {
        setIsLoadingTools(false);
      }
    };
    fetchTools();
  }, [apiUrl]);

  useEffect(() => {
    if (activeAgent?.guardrails) {
      const g = activeAgent.guardrails;
      setTopicBlock(Boolean(g.topic_block));
      setPiiMask(Boolean(g.pii_mask));
      setMutationConfirm(Boolean(g.mutation_confirm));
      setHumanHandoff(Boolean(g.human_handoff));
      if (g.max_calls) setMaxCalls(Number(g.max_calls));
      if (g.timeout_sec) setTimeoutSec(Number(g.timeout_sec));
      if (g.temperature !== undefined) setTemperature(Number(g.temperature));
    } else {
      setTopicBlock(false);
      setPiiMask(false);
      setMutationConfirm(false);
      setHumanHandoff(false);
      setMaxCalls(5);
      setTimeoutSec(30);
    }
    if (activeAgent?.model) {
      setSelectedModel(activeAgent.model);
    }
  }, [activeAgent?.id, activeAgent?.guardrails, activeAgent?.model]);

  const handleUpdateGuardrail = (key: string, value: any) => {
    const currentGuardrails = activeAgent?.guardrails || {
      topic_block: topicBlock,
      pii_mask: piiMask,
      mutation_confirm: mutationConfirm,
      human_handoff: humanHandoff,
      max_calls: maxCalls,
      timeout_sec: timeoutSec,
      temperature: temperature,
    };
    const updated = {
      ...currentGuardrails,
      [key]: value,
    };
    if (activeAgent) {
      onUpdateAgent({
        ...activeAgent,
        guardrails: updated,
      });
    }
  };

  // Fetch knowledge documents from DB or agent spec
  useEffect(() => {
    const fetchKnowledge = async () => {
      if (!activeAgent?.id) {
        if (activeAgent?.knowledge_sources && Array.isArray(activeAgent.knowledge_sources)) {
          setKnowledgeList(
            activeAgent.knowledge_sources.map((k: any) =>
              typeof k === "string" ? k : k.title || "Dokumen"
            )
          );
        } else {
          setKnowledgeList([]);
        }
        return;
      }
      try {
        setIsLoadingKnowledge(true);
        const res = await fetch(`${apiUrl}/api/v1/knowledge?agent_id=${activeAgent.id}`);
        if (res.ok) {
          const docs = await res.json();
          if (Array.isArray(docs)) {
            setKnowledgeList(docs.map((d: any) => d.title || d.name || "Dokumen"));
          }
        }
      } catch (e) {
        console.warn("Failed to fetch knowledge docs:", e);
      } finally {
        setIsLoadingKnowledge(false);
      }
    };
    fetchKnowledge();
  }, [activeAgent?.id, activeAgent?.knowledge_sources, apiUrl]);

  // Fetch test journeys (evaluations) from DB
  useEffect(() => {
    const fetchJourneys = async () => {
      try {
        setIsLoadingJourneys(true);
        const res = await fetch(`${apiUrl}/api/v1/evaluation`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            const filtered = activeAgent?.name
              ? data.filter(
                  (d: any) =>
                    !d.agent ||
                    d.agent === activeAgent.name ||
                    d.agent === "Custom Agent" ||
                    d.agent === "All"
                )
              : data;
            setJourneysList(filtered);
          }
        }
      } catch (e) {
        console.warn("Failed to fetch evaluation journeys:", e);
      } finally {
        setIsLoadingJourneys(false);
      }
    };
    if (activeTab === "journeys") {
      fetchJourneys();
    }
  }, [activeTab, activeAgent?.name, apiUrl]);

  const triggerToast = (msg: string) => {
    setSaveToast(msg);
    setTimeout(() => setSaveToast(null), 2500);
  };

  const handleToggleTool = (toolName: string) => {
    if (!activeAgent) {
      triggerToast("Pilih atau buat agent terlebih dahulu.");
      return;
    }
    const currentTools = activeAgent.tools || [];
    const updatedTools = currentTools.includes(toolName)
      ? currentTools.filter((t) => t !== toolName)
      : [...currentTools, toolName];

    const updated = { ...activeAgent, tools: updatedTools };
    onUpdateAgent(updated);
    triggerToast(
      currentTools.includes(toolName)
        ? `Tool '${toolName}' dilepas dari agent.`
        : `Tool '${toolName}' ditambahkan ke agent.`
    );
  };

  const handlePublishTool = async (toolName: string) => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/tools/${toolName}/publish`, {
        method: "POST",
      });
      if (res.ok) {
        setAllDbTools((prev) =>
          prev.map((t) => (t.name === toolName ? { ...t, status: "published" } : t))
        );
        triggerToast(`Tool '${toolName}' berhasil diterbitkan (Published)!`);
      }
    } catch {
      triggerToast("Gagal menerbitkan tool.");
    }
  };

  const handleSaveModel = (newModel: string) => {
    setSelectedModel(newModel);
    if (activeAgent) {
      onUpdateAgent({ ...activeAgent, model: newModel });
      triggerToast(`Model diubah ke ${newModel}`);
    }
  };

  const handleAddKnowledge = async (e: React.FormEvent) => {
    e.preventDefault();
    const title = newKnowledgeTitle.trim();
    if (!title) return;

    if (activeAgent?.id) {
      try {
        await fetch(`${apiUrl}/api/v1/knowledge`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title,
            source_type: "text",
            text_content: `Dokumen rujukan resmi: ${title}`,
            agent_id: activeAgent.id,
          }),
        });
      } catch (err) {
        console.warn("Failed to persist knowledge document:", err);
      }
    }
    setKnowledgeList((prev) => [...prev, title]);
    setNewKnowledgeTitle("");
    triggerToast("Dokumen rujukan berhasil ditambahkan.");
  };

  // Render sesuai tab aktif
  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50/50 overflow-y-auto min-w-0">
      {/* Toast Notification */}
      {saveToast && (
        <div className="fixed top-5 right-5 z-50 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-semibold shadow-lg animate-in fade-in slide-in-from-top-2 duration-200 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{saveToast}</span>
        </div>
      )}

      {/* 1. TAB: TOOLS */}
      {activeTab === "tools" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200/80">
            <div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center">
                  <Wrench className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-900">
                    Konfigurasi Tools (C3 &amp; C4)
                  </h2>
                  <p className="text-xs text-slate-500">
                    Kelola alat dan endpoint yang boleh diakses oleh agent{" "}
                    <strong>{activeAgent?.name || "Agent Ini"}</strong>.
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={() => onSwitchToGhostwriter("Rancang tool baru untuk kebutuhan:")}
              className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-2xs flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Rancang Tool via AI</span>
            </button>
          </div>

          {/* Active Tools Summary */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">
                Tools Terikat ({activeAgent?.tools?.length || 0} Aktif)
              </span>
              <span className="text-[11px] text-slate-400">
                Centang untuk menghubungkan tool ke agent
              </span>
            </div>

            {isLoadingTools ? (
              <div className="py-8 text-center text-xs text-slate-400">
                Memuat katalog tools...
              </div>
            ) : allDbTools.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                Belum ada tools di database. Gunakan Ghostwriter untuk merancang tool baru.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {allDbTools.map((t) => {
                  const isAttached = activeAgent?.tools?.includes(t.name);
                  const isPublished = t.status === "published";
                  const isWrite = t.effect === "write";

                  return (
                    <div
                      key={t.name}
                      className={`p-3.5 rounded-xl border transition-all flex flex-col justify-between gap-2.5 ${
                        isAttached
                          ? "bg-blue-50/40 border-blue-200 shadow-2xs"
                          : "bg-white border-slate-200/80 hover:border-slate-300"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs font-bold text-slate-900 truncate">
                            {t.name}()
                          </span>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span
                              className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase ${
                                isWrite
                                  ? "bg-rose-100 text-rose-800"
                                  : "bg-cyan-100 text-cyan-800"
                              }`}
                            >
                              {t.effect || "read"}
                            </span>
                            <span
                              className={`text-[9px] font-bold px-1.5 py-0.2 rounded uppercase border ${
                                isPublished
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : "bg-amber-50 text-amber-700 border-amber-200"
                              }`}
                            >
                              {isPublished ? "Terbit" : "Draf"}
                            </span>
                          </div>
                        </div>

                        <p className="text-[11px] text-slate-600 line-clamp-2">
                          {t.description || "Tidak ada deskripsi."}
                        </p>
                      </div>

                      <div className="flex items-center justify-between pt-1 border-t border-slate-100">
                        {!isPublished ? (
                          <button
                            type="button"
                            onClick={() => handlePublishTool(t.name)}
                            className="text-[10px] font-semibold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 cursor-pointer"
                          >
                            <Check className="w-3 h-3" />
                            <span>Terbitkan Tool</span>
                          </button>
                        ) : (
                          <span className="text-[10px] text-slate-400">Siap di Runner</span>
                        )}

                        <button
                          type="button"
                          onClick={() => handleToggleTool(t.name)}
                          className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                            isAttached
                              ? "bg-blue-600 text-white shadow-2xs"
                              : "bg-slate-100 hover:bg-slate-200 text-slate-700"
                          }`}
                        >
                          {isAttached ? "✓ Terhubung" : "+ Hubungkan"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. TAB: GUARDRAILS */}
      {activeTab === "guardrails" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center gap-2 pb-4 border-b border-slate-200/80">
            <div className="w-8 h-8 rounded-xl bg-emerald-600/10 text-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Safety Guardrails &amp; Batasan (C5, C6, C9, C10)
              </h2>
              <p className="text-xs text-slate-500">
                Menjaga batasan topik, penyensoran data sensitif, dan proteksi mutasi data.
              </p>
            </div>
          </div>

          <div className="space-y-3.5">
            {/* Guardrail 1: Topic Blocking */}
            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">
                    Batas Topik &amp; Larangan (C5)
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-blue-100 text-blue-800">
                    SOP Compliance
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Agen menolak dengan sopan permintaan yang berada di luar cakupan tugasnya (misal: pertanyaan politik, saran medis terlarang, atau transaksi ilegal).
                </p>
              </div>
              <input
                type="checkbox"
                checked={topicBlock}
                onChange={(e) => {
                  const val = e.target.checked;
                  setTopicBlock(val);
                  handleUpdateGuardrail("topic_block", val);
                  triggerToast(`Pengaturan Topic Guardrail ${val ? "diaktifkan" : "dinonaktifkan"}.`);
                }}
                className="w-4 h-4 mt-1 accent-blue-600 cursor-pointer"
              />
            </div>

            {/* Guardrail 2: PII Data Masking */}
            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">
                    Sensor Data Sensitif / PII Masking (C9)
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-purple-100 text-purple-800">
                    Privacy
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Menyamarkan nomor KTP, NIK, nomor rekening bank, kata sandi, dan data pribadi di log audit sebelum dikirimkan ke model AI eksternal.
                </p>
              </div>
              <input
                type="checkbox"
                checked={piiMask}
                onChange={(e) => {
                  const val = e.target.checked;
                  setPiiMask(val);
                  handleUpdateGuardrail("pii_mask", val);
                  triggerToast(`Pengaturan PII Masking ${val ? "diaktifkan" : "dinonaktifkan"}.`);
                }}
                className="w-4 h-4 mt-1 accent-blue-600 cursor-pointer"
              />
            </div>

            {/* Guardrail 3: Mutation Confirmation */}
            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">
                    Konfirmasi Aksi Mutasi Data (C4)
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-amber-100 text-amber-800">
                    Human-in-the-Loop
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Untuk tool berefek <code>write</code> (booking, pemesanan, pembatalan), agen wajib meminta konfirmasi persetujuan tegas dari pengguna sebelum mengeksekusi.
                </p>
              </div>
              <input
                type="checkbox"
                checked={mutationConfirm}
                onChange={(e) => {
                  const val = e.target.checked;
                  setMutationConfirm(val);
                  handleUpdateGuardrail("mutation_confirm", val);
                  triggerToast(`Pengaturan Konfirmasi Mutasi ${val ? "diaktifkan" : "dinonaktifkan"}.`);
                }}
                className="w-4 h-4 mt-1 accent-blue-600 cursor-pointer"
              />
            </div>

            {/* Guardrail 4: Human Handoff */}
            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-800">
                    Serah ke Operator Manusia / Handoff (C10)
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.2 rounded-full bg-emerald-100 text-emerald-800">
                    Escalation
                  </span>
                </div>
                <p className="text-xs text-slate-600">
                  Jika pengguna meminta bicara dengan petugas manusia atau sistem mengalami kegagalan 2 kali berturut-turut, percakapan otomatis dialihkan ke antrean staf.
                </p>
              </div>
              <input
                type="checkbox"
                checked={humanHandoff}
                onChange={(e) => {
                  const val = e.target.checked;
                  setHumanHandoff(val);
                  handleUpdateGuardrail("human_handoff", val);
                  triggerToast(`Pengaturan Human Handoff ${val ? "diaktifkan" : "dinonaktifkan"}.`);
                }}
                className="w-4 h-4 mt-1 accent-blue-600 cursor-pointer"
              />
            </div>
          </div>
        </div>
      )}

      {/* 3. TAB: KNOWLEDGE */}
      {activeTab === "knowledge" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200/80">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-indigo-600/10 text-indigo-600 flex items-center justify-center">
                <Smartphone className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Dokumen Acuan &amp; Knowledge Base (C12)
                </h2>
                <p className="text-xs text-slate-500">
                  Rujukan aturan, dokumen SOP, dan pedoman FAQ yang wajib dipatuhi agen.
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-2xs space-y-4">
            <span className="text-xs font-bold text-slate-800 block">
              Daftar Dokumen Rujukan Terlampir
            </span>

            {isLoadingKnowledge ? (
              <p className="text-xs text-slate-400 py-4 text-center">Memuat dokumen dari database...</p>
            ) : knowledgeList.length === 0 ? (
              <div className="py-8 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50 space-y-1.5">
                <FileText className="w-7 h-7 text-slate-300 mx-auto" />
                <p className="text-xs font-semibold text-slate-600">Belum ada dokumen rujukan di database</p>
                <p className="text-[11px] text-slate-400">Tambahkan judul dokumen atau SOP baru di bawah untuk membekali agent.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {knowledgeList.map((doc, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-slate-200/70 bg-slate-50/50 flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                      <span className="font-medium text-slate-800 truncate">{doc}</span>
                    </div>
                    <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200 shrink-0">
                      Aktif
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Form Tambah Dokumen */}
            <form onSubmit={handleAddKnowledge} className="pt-2 flex items-center gap-2">
              <input
                type="text"
                value={newKnowledgeTitle}
                onChange={(e) => setNewKnowledgeTitle(e.target.value)}
                placeholder="Tambah judul dokumen atau SOP baru..."
                className="flex-1 px-3 py-2 text-xs rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
              <button
                type="submit"
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-black text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Tambah</span>
              </button>
            </form>
          </div>
        </div>
      )}

      {/* 4. TAB: MODEL */}
      {activeTab === "model" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center gap-2 pb-4 border-b border-slate-200/80">
            <div className="w-8 h-8 rounded-xl bg-sky-600/10 text-sky-600 flex items-center justify-center">
              <AtSign className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Konfigurasi Model LLM &amp; Harness
              </h2>
              <p className="text-xs text-slate-500">
                Pilih model kecerdasan buatan, suhu kreativitas, dan pengaman runtime.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              {
                id: "z-ai/glm-5.3",
                name: "GLM 5.3",
                provider: "Zhipu AI via OpenRouter",
                desc: "Model universal seimbang dengan penalaran tajam dan latensi sangat cepat.",
                recommended: true,
              },
              {
                id: "openai/gpt-4o",
                name: "GPT-4o",
                provider: "OpenAI",
                desc: "Model penalaran multimodal standar industri untuk alur kerja rumit.",
                recommended: false,
              },
              {
                id: "x-ai/grok-4.6",
                name: "Grok 4.6",
                provider: "xAI",
                desc: "Model penalaran mendalam yang digunakan pada evaluator juri independen.",
                recommended: false,
              },
              {
                id: "meta-llama/llama-3-70b-instruct",
                name: "Llama 3 70B",
                provider: "Meta via OpenRouter",
                desc: "Model open-weights performa tinggi untuk kepatuhan instruksi ketat.",
                recommended: false,
              },
            ].map((m) => (
              <div
                key={m.id}
                onClick={() => handleSaveModel(m.id)}
                className={`p-4 rounded-2xl border transition-all cursor-pointer space-y-2 ${
                  selectedModel === m.id
                    ? "border-blue-500 bg-blue-50/50 shadow-xs ring-2 ring-blue-200"
                    : "border-slate-200 bg-white hover:border-slate-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-blue-600" />
                    <span className="font-bold text-xs text-slate-900">{m.name}</span>
                  </div>
                  {m.recommended && (
                    <span className="text-[10px] font-bold px-2 py-0.2 rounded-full bg-blue-600 text-white">
                      Rekomendasi
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-400 font-medium">{m.provider}</p>
                <p className="text-xs text-slate-600">{m.desc}</p>
              </div>
            ))}
          </div>

          {/* Temperature slider */}
          <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-800">Kreativitas / Temperature</span>
              <span className="font-mono font-bold text-blue-700">{temperature}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={temperature}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setTemperature(val);
                handleUpdateGuardrail("temperature", val);
              }}
              className="w-full accent-blue-600 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0.0 (Presisi &amp; Deterministik)</span>
              <span>1.0 (Kreatif &amp; Bervariasi)</span>
            </div>
          </div>
        </div>
      )}

      {/* 5. TAB: LIMITS */}
      {activeTab === "limits" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center gap-2 pb-4 border-b border-slate-200/80">
            <div className="w-8 h-8 rounded-xl bg-amber-600/10 text-amber-600 flex items-center justify-center">
              <SlidersHorizontal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Batas Pemakaian &amp; Kuota (C8)
              </h2>
              <p className="text-xs text-slate-500">
                Cegah loop pemanggilan tak berujung dan batasi konsumsi komputasi.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs space-y-3">
              <label className="block text-xs font-bold text-slate-800">
                Maksimal Panggilan Tool per Giliran Obrolan (Max Tool Calls)
              </label>
              <div className="flex items-center gap-2">
                {[3, 5, 10, 20].map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => {
                      setMaxCalls(num);
                      handleUpdateGuardrail("max_calls", num);
                      triggerToast(`Batas panggilan diset ke ${num} calls.`);
                    }}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                      maxCalls === num
                        ? "bg-slate-900 text-white border-slate-900 shadow-2xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {num} Panggilan
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-slate-500">
                Standar rekomendasi SKILL.md: 5 panggilan tool per giliran.
              </p>
            </div>

            <div className="p-4 rounded-2xl border border-slate-200/80 bg-white shadow-2xs space-y-3">
              <label className="block text-xs font-bold text-slate-800">
                Batas Waktu Eksekusi Tool (Timeout Proteksi)
              </label>
              <div className="flex items-center gap-2">
                {[15, 30, 60, 90].map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => {
                      setTimeoutSec(sec);
                      handleUpdateGuardrail("timeout_sec", sec);
                      triggerToast(`Timeout diset ke ${sec} detik.`);
                    }}
                    className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                      timeoutSec === sec
                        ? "bg-slate-900 text-white border-slate-900 shadow-2xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    {sec} Detik
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 6. TAB: JOURNEYS */}
      {activeTab === "journeys" && (
        <div className="p-6 max-w-4xl w-full mx-auto space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200/80">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-indigo-600/10 text-indigo-600 flex items-center justify-center">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">
                  Perjalanan Percakapan &amp; Skenario Uji (C11)
                </h2>
                <p className="text-xs text-slate-500">
                  Contoh percakapan benar: 1 kasus normal dan 1 kasus penolakan/fallback.
                </p>
              </div>
            </div>

            <button
              onClick={() => onSwitchToGhostwriter("Uji contoh percakapan:")}
              className="px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-2xs flex items-center gap-1.5 transition-all cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Simulasi Percakapan</span>
            </button>
          </div>

          <div className="space-y-4">
            {isLoadingJourneys ? (
              <p className="text-xs text-slate-400 py-8 text-center">Memuat skenario uji dari database...</p>
            ) : journeysList.length === 0 ? (
              <div className="py-12 text-center border border-dashed border-slate-200 rounded-2xl bg-white p-6 space-y-2">
                <BookOpen className="w-8 h-8 text-slate-300 mx-auto" />
                <h3 className="text-xs font-bold text-slate-700">Belum Ada Skenario Perjalanan di Database</h3>
                <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
                  Belum ada test case percakapan yang tersimpan di tabel evaluasi. Anda dapat membuat skenario dari modul Evaluator atau melakukan simulasi percakapan.
                </p>
              </div>
            ) : (
              journeysList.map((j: any, idx: number) => {
                const isGuardrail =
                  (j.expected || "").toLowerCase().includes("guardrail") ||
                  (j.expected || "").toLowerCase().includes("tolak") ||
                  (j.expected || "").toLowerCase().includes("penolakan") ||
                  (j.expected || "").toLowerCase().includes("safety");
                return (
                  <div
                    key={j.id || idx}
                    className={`p-4 rounded-2xl border space-y-2 ${
                      isGuardrail
                        ? "border-rose-200 bg-rose-50/40"
                        : "border-emerald-200 bg-emerald-50/40"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-xs font-bold ${
                          isGuardrail ? "text-rose-900" : "text-emerald-900"
                        }`}
                      >
                        Skenario {idx + 1}: {j.scenario || j.agent || "Skenario Uji"}{" "}
                        {isGuardrail ? "(Guardrail Path)" : "(Golden Path)"}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          j.status === "passed"
                            ? "bg-emerald-200 text-emerald-900"
                            : j.status === "failed"
                            ? "bg-rose-200 text-rose-900"
                            : "bg-slate-200 text-slate-800"
                        }`}
                      >
                        {j.status || "idle"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-700">
                      <strong>Input Pengguna:</strong> &ldquo;{j.input}&rdquo;
                    </p>
                    <p className="text-xs text-slate-700">
                      <strong>Perilaku Ideal:</strong> {j.expected}
                    </p>
                    {j.actual && j.actual !== "-" && (
                      <p className="text-xs text-slate-600 border-t border-slate-200/60 pt-1.5 mt-1.5">
                        <strong>Hasil Aktual:</strong> {j.actual}
                      </p>
                    )}
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
