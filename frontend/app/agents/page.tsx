"use client";

import React, { useState } from "react";
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
} from "lucide-react";

export default function AllAgentsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("All Statuses");
  const [selectedVersion, setSelectedVersion] = useState("All Versions");
  const [sortBy, setSortBy] = useState("Last Updated");

  // State agen murni frontend (tanpa data dummy, siap menerima data)
  const [agents, setAgents] = useState<any[]>([]);

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
        </header>

        {/* Content Wrapper */}
        <div className="flex-1 p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Header Title & Action Button */}
          <section className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                AGENTS
              </span>
              <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight mt-0.5">
                All Agents
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1">
                Manage and organize your AI agents. Create new agents or view details of existing ones.
              </p>
            </div>

            <Link
              href="/"
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs sm:text-sm transition-all shadow-xs hover:shadow-sm shrink-0"
            >
              <Plus className="w-4 h-4" />
              <span>Create Agent</span>
            </Link>
          </section>

          {/* Search & Filter Toolbar */}
          <section className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search agents..."
                className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all shadow-2xs"
              />
            </div>

            {/* Filter Dropdown Buttons */}
            <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
              {/* Status Filter */}
              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-2xs"
              >
                <span>{selectedStatus}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {/* Version Filter */}
              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-2xs"
              >
                <span>{selectedVersion}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {/* Sort Order */}
              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all shadow-2xs"
              >
                <span>{sortBy}</span>
                <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
              </button>
            </div>
          </section>

          {/* Table Container */}
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200/80 bg-slate-50/60 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    <th className="py-3.5 px-6 min-w-[240px]">Name</th>
                    <th className="py-3.5 px-6 min-w-[340px]">Description</th>
                    <th className="py-3.5 px-4 min-w-[110px]">Status</th>
                    <th className="py-3.5 px-4 min-w-[90px]">Version</th>
                    <th className="py-3.5 px-6 min-w-[150px]">Last Updated</th>
                    <th className="py-3.5 px-6 min-w-[130px]">Deployment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {agents.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-16 text-center">
                        <div className="flex flex-col items-center justify-center text-slate-400">
                          <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-200/80 flex items-center justify-center text-slate-400 mb-3">
                            <Bot className="w-6 h-6" />
                          </div>
                          <p className="text-sm font-semibold text-slate-700">
                            Belum ada agent yang dibuat
                          </p>
                          <p className="text-xs text-slate-400 mt-1 max-w-sm">
                            Mulai buat agent baru dengan menekan tombol Create Agent.
                          </p>
                          <Link
                            href="/"
                            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-2xs"
                          >
                            <Plus className="w-4 h-4" />
                            <span>Create Agent</span>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    agents.map((agent: any) => (
                      <tr key={agent.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-4 px-6">{agent.name}</td>
                        <td className="py-4 px-6">{agent.description}</td>
                        <td className="py-4 px-4">{agent.status}</td>
                        <td className="py-4 px-4">{agent.version}</td>
                        <td className="py-4 px-6">{agent.updatedAt}</td>
                        <td className="py-4 px-6">{agent.deployment}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Table Pagination / Footer Elements */}
            <div className="px-6 py-3 border-t border-slate-200/80 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
              <span>Showing {agents.length} of {agents.length} agents</span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  disabled
                  className="p-1 rounded-lg border border-slate-200 text-slate-300 disabled:opacity-40 cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  disabled
                  className="px-2.5 py-1 rounded-lg bg-blue-600/70 text-white font-medium text-xs shadow-2xs cursor-default"
                >
                  1
                </button>
                <button
                  type="button"
                  disabled
                  className="p-1 rounded-lg border border-slate-200 text-slate-300 disabled:opacity-40 cursor-not-allowed"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
