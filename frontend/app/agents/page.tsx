"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { Sidebar } from "@/components/navigation/Sidebar";
import {
  Activity,
  Plus,
  Search,
  ChevronDown,
  ArrowUpDown,
  Bot,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Edit,
  Trash2,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from "lucide-react";

import { EditAgentModal } from "./EditAgentModal";
import { getDrafts, deleteDraft, subscribeToDrafts, AgentDraft } from "@/lib/draftStore";

export default function AllAgentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("All Statuses");
  const [agents, setAgents] = useState<any[]>([]);
  const [drafts, setDrafts] = useState<AgentDraft[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Edit & Delete state
  const [editingAgent, setEditingAgent] = useState<any>(null);
  const [deletingAgent, setDeletingAgent] = useState<any>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    if (!deletingAgent) return;
    setIsDeleting(true);
    try {
      const res = await fetch(`/api/v1/agent/${deletingAgent.id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setAgents((prev) => prev.filter((a) => a.id !== deletingAgent.id));
        setDeletingAgent(null);
      } else {
        console.error("Failed to delete agent");
      }
    } catch (err) {
      console.error("Error deleting agent:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  const fetchAgents = async () => {
    try {
      setIsLoading(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiUrl}/api/v1/agent`);
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
      }
    } catch (e) {
      console.warn("Failed to load agents list:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
    setDrafts(getDrafts());
    const unsubscribe = subscribeToDrafts((updated) => setDrafts(updated));
    return () => unsubscribe();
  }, []);

  const filteredAgents = agents.filter((agent) => {
    const matchesSearch =
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (agent.description && agent.description.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus =
      selectedStatus === "All Statuses" ||
      agent.status?.toLowerCase() === selectedStatus.toLowerCase();
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar Persisten */}
      <Sidebar />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-white min-w-0">
        {/* Top Breadcrumb Bar */}
        <header className="h-14 px-8 border-b border-slate-100 flex items-center justify-between shrink-0 bg-white">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 font-medium text-slate-700">
              <Activity className="w-3.5 h-3.5 text-blue-600" />
              <span>Agent Studio</span>
            </div>
            <span className="text-slate-300">/</span>
            <span className="font-semibold text-slate-900">Agents</span>
          </nav>
          <button
            onClick={fetchAgents}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-blue-600 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
        </header>

        {/* Content Wrapper */}
        <div className="flex-1 p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Header Title & Action Button */}
          <section className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                AGENTS DATABASE
              </span>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-0.5">
                All Agents ({agents.length})
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                Daftar seluruh AI Agent yang telah dibuat dan tersimpan di database.
              </p>
            </div>

            <Link
              href="/?new=true"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs sm:text-sm transition-all shadow-xs hover:shadow-sm shrink-0"
            >
              <Plus className="w-4 h-4" />
              <span>Create Agent</span>
            </Link>
          </section>

          {/* Active Drafts Section (Belum Diterapkan ke DB) */}
          {drafts.length > 0 && (
            <section className="bg-gradient-to-r from-amber-50/80 to-amber-100/40 border border-amber-200/90 rounded-2xl p-5 space-y-3.5 shadow-2xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
                  <h2 className="text-sm font-bold text-amber-950 uppercase tracking-wider">
                    Draf Agen Aktif ({drafts.length})
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-200/80 text-amber-900 border border-amber-300">
                    Belum disimpan ke database
                  </span>
                </div>
                <p className="text-xs text-amber-800">
                  Agen sedang dirancang. Anda dapat melanjutkan pengeditan kapan saja.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {drafts.map((draft) => (
                  <div
                    key={draft.id}
                    className="bg-white border border-amber-200/80 rounded-xl p-4 flex flex-col justify-between shadow-2xs hover:shadow-xs transition-shadow"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-bold text-slate-900 line-clamp-1">
                          {draft.name || "Draf Agen Baru"}
                        </span>
                        <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-800 rounded shrink-0">
                          Draf
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 min-h-[32px]">
                        {draft.description || "Belum ada deskripsi."}
                      </p>
                      <div className="flex items-center gap-2 pt-1 text-[11px] text-slate-400">
                        <span className="font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 text-[10px]">
                          {draft.model || "gemini-2.5-flash"}
                        </span>
                        <span>•</span>
                        <span>{draft.tools?.length || 0} tools</span>
                        <span>•</span>
                        <span>
                          {draft.updated_at
                            ? new Date(draft.updated_at).toLocaleTimeString("id-ID", {
                                hour: "2-digit",
                                minute: "2-digit",
                              })
                            : "-"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between gap-2 pt-3 mt-3 border-t border-slate-100">
                      <button
                        onClick={() => deleteDraft(draft.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                        title="Hapus Draf"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      <Link
                        href={`/?draft_id=${draft.id}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-950 bg-amber-200/70 hover:bg-amber-300 rounded-lg transition-colors"
                      >
                        <span>Lanjutkan Rancang</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Search & Filter Toolbar */}
          <section className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search agents by name or description..."
                className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all shadow-2xs"
              />
            </div>

            {/* Filter Dropdown Buttons */}
            <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-2xs"
              >
                <span>{selectedStatus}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>
          </section>

          {/* Table Container */}
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200/80 bg-slate-50/60 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3.5 px-6 min-w-[200px]">ID / Name</th>
                    <th className="py-3.5 px-6 min-w-[280px]">Description</th>
                    <th className="py-3.5 px-4 min-w-[100px]">Status</th>
                    <th className="py-3.5 px-4 min-w-[100px]">Model</th>
                    <th className="py-3.5 px-4 min-w-[160px]">Tools</th>
                    <th className="py-3.5 px-6 min-w-[150px]">Created At</th>
                    <th className="py-3.5 px-6 min-w-[190px] text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {isLoading ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-400">
                        <div className="flex items-center justify-center gap-2 text-xs">
                          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                          <span>Loading agents from database...</span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredAgents.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-16 text-center">
                        <div className="flex flex-col items-center justify-center text-slate-400">
                          <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-400 mb-3">
                            <Bot className="w-6 h-6" />
                          </div>
                          <p className="text-sm font-semibold text-slate-700">
                            Belum ada agent yang ditemukan
                          </p>
                          <p className="text-xs text-slate-400 mt-1 max-w-sm">
                            Mulai buat agent baru dengan menekan tombol Create Agent.
                          </p>
                          <Link
                            href="/?new=true"
                            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-2xs"
                          >
                            <Plus className="w-4 h-4" />
                            <span>Create Agent</span>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredAgents.map((agent: any) => (
                      <tr key={agent.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-4 px-6 font-semibold text-slate-900">
                          <Link
                            href={`/?id=${agent.id}`}
                            className="group inline-flex items-center gap-1.5 hover:text-blue-600 transition-colors"
                          >
                            <span>{agent.name}</span>
                            <Sparkles className="w-3 h-3 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </Link>
                          <div className="text-[10px] font-mono text-slate-400 font-normal">
                            ID: {agent.id}
                          </div>
                        </td>
                        <td className="py-4 px-6 text-slate-600">
                          <p className="line-clamp-2">{agent.description || "-"}</p>
                        </td>
                        <td className="py-4 px-4">
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {agent.status || "active"}
                          </span>
                        </td>
                        <td className="py-4 px-4 font-mono text-[11px] text-slate-700">
                          {agent.model}
                        </td>
                        <td className="py-4 px-4">
                          <div className="flex flex-wrap gap-1">
                            {agent.tools && agent.tools.length > 0 ? (
                              agent.tools.map((t: string) => (
                                <span
                                  key={t}
                                  className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-mono border border-blue-200/60"
                                >
                                  {t}
                                </span>
                              ))
                            ) : (
                              <span className="text-slate-400 text-[10px] italic">No tools</span>
                            )}
                          </div>
                        </td>
                        <td className="py-4 px-6 text-slate-500 text-[11px]">
                          {agent.created_at
                            ? new Date(agent.created_at).toLocaleString("id-ID")
                            : "-"}
                        </td>
                        <td className="py-4 px-6 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Link
                              href={`/?id=${agent.id}`}
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                              title="Buka di Studio"
                            >
                              <Bot className="w-3.5 h-3.5" />
                              <span>Buka Studio</span>
                            </Link>
                            <button
                              onClick={() => setEditingAgent(agent)}
                              className="p-1.5 text-slate-600 hover:text-blue-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                              title="Edit Agent"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setDeletingAgent(agent)}
                              className="p-1.5 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                              title="Delete Agent"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-3 border-t border-slate-200/80 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
              <span>Showing {filteredAgents.length} of {agents.length} agents</span>
            </div>
          </section>
        </div>
      </main>

      {/* Edit Agent Modal */}
      <EditAgentModal
        agent={editingAgent}
        isOpen={!!editingAgent}
        onClose={() => setEditingAgent(null)}
        onSave={(updatedAgent) => {
          setAgents((prev) =>
            prev.map((a) => (a.id === updatedAgent.id ? updatedAgent : a))
          );
          setEditingAgent(null);
        }}
      />

      {/* Delete Confirmation Modal */}
      {deletingAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="p-6 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-rose-100 flex items-center justify-center mx-auto text-rose-600 mb-2">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">Delete Agent?</h3>
              <p className="text-sm text-slate-500">
                Are you sure you want to delete <span className="font-semibold text-slate-700">{deletingAgent.name}</span>? This action cannot be undone.
              </p>
            </div>
            <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-3">
              <button
                onClick={() => setDeletingAgent(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex items-center justify-center min-w-[80px] px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-xl transition-colors shadow-xs cursor-pointer"
              >
                {isDeleting ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  "Delete"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
