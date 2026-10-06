"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import {
  Plus,
  ChevronDown,
  Server,
  Wrench,
  Check,
  X,
  ExternalLink,
  RefreshCw,
  Globe,
  Sliders,
} from "lucide-react";

export type ToolsTab = "all_tools" | "mcp_servers";

export default function ToolsRegistryPage() {
  const [activeTab, setActiveTab] = useState<ToolsTab>("all_tools");
  const [showNewToolMenu, setShowNewToolMenu] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  // Form states untuk modal register MCP
  const [serverName, setServerName] = useState("");
  const [serverUrl, setServerUrl] = useState("");

  // State daftar tools & mcp servers (tanpa dummy data default)
  const [tools, setTools] = useState<any[]>([]);
  const [mcpServers, setMcpServers] = useState<any[]>([]);

  const handleRegisterServer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!serverName || !serverUrl) return;

    const newServer = {
      id: Date.now().toString(),
      name: serverName,
      url: serverUrl,
      status: "connected",
      toolsCount: 0,
    };

    setMcpServers((prev) => [...prev, newServer]);
    setServerName("");
    setServerUrl("");
    setShowRegisterModal(false);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar Persisten */}
      <Sidebar />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-white min-w-0">
        <div className="p-8 max-w-6xl w-full mx-auto space-y-6">
          {/* Header Title & Action Button */}
          <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                Tools
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                One catalog of everything callable — MCP, HTTP, OpenAPI-imported, built-in — with source, auth custody and health. The registry is the allowlist.
              </p>
            </div>

            {/* + New Tool Dropdown Button */}
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setShowNewToolMenu(!showNewToolMenu)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-all shadow-2xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New tool</span>
                <ChevronDown className="w-3.5 h-3.5 ml-0.5 text-slate-400" />
              </button>

              {/* Dropdown Menu Options */}
              {showNewToolMenu && (
                <div className="absolute right-0 mt-1.5 w-48 rounded-xl border border-slate-200 bg-white shadow-lg py-1 z-30 text-xs">
                  <button
                    type="button"
                    onClick={() => {
                      setShowNewToolMenu(false);
                      setActiveTab("mcp_servers");
                      setShowRegisterModal(true);
                    }}
                    className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <Server className="w-3.5 h-3.5 text-slate-400" />
                    <span>Register MCP server</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowNewToolMenu(false)}
                    className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <Globe className="w-3.5 h-3.5 text-slate-400" />
                    <span>Import OpenAPI</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowNewToolMenu(false)}
                    className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2"
                  >
                    <Wrench className="w-3.5 h-3.5 text-slate-400" />
                    <span>Custom Built-in Tool</span>
                  </button>
                </div>
              )}
            </div>
          </header>

          {/* Navigation Tabs (All tools / MCP servers) */}
          <nav className="flex items-center gap-6 border-b border-slate-200 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab("all_tools")}
              className={`pb-2.5 transition-colors relative ${
                activeTab === "all_tools"
                  ? "text-slate-900 font-bold border-b-2 border-slate-900"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              All tools
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("mcp_servers")}
              className={`pb-2.5 transition-colors relative ${
                activeTab === "mcp_servers"
                  ? "text-slate-900 font-bold border-b-2 border-slate-900"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              MCP servers
            </button>
          </nav>

          {/* Tab 1: All Tools View */}
          {activeTab === "all_tools" && (
            <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200/80 bg-slate-50/40 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-6 min-w-[200px]">TOOL</th>
                      <th className="py-3 px-6 min-w-[120px]">SOURCE</th>
                      <th className="py-3 px-6 min-w-[120px]">AUTH</th>
                      <th className="py-3 px-6 min-w-[120px]">HEALTH</th>
                      <th className="py-3 px-6 min-w-[120px]">USED BY</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {tools.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-16 text-center">
                          <div className="flex flex-col items-center justify-center text-slate-400">
                            <Wrench className="w-8 h-8 mb-2 text-slate-300" />
                            <p className="text-xs font-semibold text-slate-600">
                              No tools registered in catalog
                            </p>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                              Register an MCP server or built-in tool to populate the registry allowlist.
                            </p>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      tools.map((tool: any) => (
                        <tr key={tool.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3.5 px-6 font-semibold text-slate-900">
                            {tool.name}
                          </td>
                          <td className="py-3.5 px-6">
                            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-bold text-[10px] uppercase tracking-wider border border-slate-200/60">
                              {tool.source}
                            </span>
                          </td>
                          <td className="py-3.5 px-6 text-slate-500 font-mono text-[11px]">
                            {tool.auth}
                          </td>
                          <td className="py-3.5 px-6">
                            <span className="inline-flex items-center gap-1.5 text-emerald-600 font-medium text-xs">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              {tool.health}
                            </span>
                          </td>
                          <td className="py-3.5 px-6 text-slate-500 text-xs">
                            {tool.usedBy}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Tab 2: MCP Servers View */}
          {activeTab === "mcp_servers" && (
            <div>
              {mcpServers.length === 0 ? (
                /* Empty State Container persis seperti tangkapan layar */
                <div className="rounded-2xl border border-dashed border-slate-200/90 p-16 flex flex-col items-center justify-center text-center">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-slate-400 mb-3">
                    <Server className="w-6 h-6 stroke-[1.5]" />
                  </div>
                  <p className="text-xs text-slate-500 max-w-md leading-relaxed">
                    No MCP servers registered. The registry is the allowlist — agents can only call what is listed here.
                  </p>
                  <button
                    type="button"
                    onClick={() => setShowRegisterModal(true)}
                    className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-all shadow-2xs"
                  >
                    <Plus className="w-3.5 h-3.5 text-slate-500" />
                    <span>Register server</span>
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {mcpServers.map((server: any) => (
                    <div
                      key={server.id}
                      className="p-4 rounded-2xl border border-slate-200 bg-white shadow-2xs flex items-center justify-between"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                          <Server className="w-4 h-4" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-slate-900">{server.name}</h4>
                          <p className="text-[11px] text-slate-400 font-mono">{server.url}</p>
                        </div>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                        Connected
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* Register MCP Server Modal Element */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">Register MCP Server</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowRegisterModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleRegisterServer} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Server Name
                </label>
                <input
                  type="text"
                  value={serverName}
                  onChange={(e) => setServerName(e.target.value)}
                  placeholder="e.g. Hospital MCP"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Server URL / Endpoint
                </label>
                <input
                  type="text"
                  value={serverUrl}
                  onChange={(e) => setServerUrl(e.target.value)}
                  placeholder="e.g. http://localhost:8001/sse"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  className="px-3 py-1.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold shadow-2xs"
                >
                  Register Server
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
