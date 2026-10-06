"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import { RegisterMcpModal } from "@/features/tools/RegisterMcpModal";
import { ImportOpenApiModal } from "@/features/tools/ImportOpenApiModal";
import { CustomToolModal } from "@/features/tools/CustomToolModal";
import {
  Plus,
  ChevronDown,
  Server,
  Wrench,
  Globe,
  RefreshCw,
  Trash2,
  ExternalLink,
  Code2,
} from "lucide-react";

export type ToolsTab = "all_tools" | "mcp_servers";

export default function ToolsRegistryPage() {
  const [activeTab, setActiveTab] = useState<ToolsTab>("all_tools");
  const [showNewToolMenu, setShowNewToolMenu] = useState(false);

  // Modal visibility states
  const [showRegisterMcpModal, setShowRegisterMcpModal] = useState(false);
  const [showImportOpenApiModal, setShowImportOpenApiModal] = useState(false);
  const [showCustomToolModal, setShowCustomToolModal] = useState(false);

  // Unified tables state
  const [tools, setTools] = useState<any[]>([]);
  const [mcpServers, setMcpServers] = useState<any[]>([]);

  // Handlers for adding newly registered items
  const handleSaveMcpServer = (serverData: any, discoveredTools: any[]) => {
    setMcpServers((prev) => [serverData, ...prev]);
    setTools((prev) => [...discoveredTools, ...prev]);
    setActiveTab("mcp_servers");
  };

  const handleSaveOpenApiTools = (sourceData: any, importedTools: any[]) => {
    setTools((prev) => [...importedTools, ...prev]);
    setActiveTab("all_tools");
  };

  const handleSaveCustomTool = (toolData: any) => {
    setTools((prev) => [toolData, ...prev]);
    setActiveTab("all_tools");
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar Persisten */}
      <Sidebar />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-white min-w-0">
        <div className="p-8 max-w-6xl w-full mx-auto space-y-6">
          {/* Header Title & + New Tool Dropdown */}
          <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                Tools
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                One catalog of everything callable — MCP, HTTP, OpenAPI-imported, built-in — with source, auth custody and health. The registry is the allowlist.
              </p>
            </div>

            {/* + New Tool Dropdown */}
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setShowNewToolMenu(!showNewToolMenu)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>New tool</span>
                <ChevronDown className="w-3.5 h-3.5 ml-0.5 text-slate-400" />
              </button>

              {/* Dropdown Menu Options */}
              {showNewToolMenu && (
                <>
                  <div
                    className="fixed inset-0 z-20"
                    onClick={() => setShowNewToolMenu(false)}
                  />
                  <div className="absolute right-0 mt-1.5 w-52 rounded-xl border border-slate-200 bg-white shadow-lg py-1.5 z-30 text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        setShowNewToolMenu(false);
                        setShowRegisterMcpModal(true);
                      }}
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                    >
                      <Server className="w-4 h-4 text-blue-600 shrink-0" />
                      <div>
                        <div className="font-semibold text-slate-900">Register MCP server</div>
                        <div className="text-[10px] text-slate-400">Streamable HTTP & Discovery</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setShowNewToolMenu(false);
                        setShowImportOpenApiModal(true);
                      }}
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                    >
                      <Globe className="w-4 h-4 text-indigo-600 shrink-0" />
                      <div>
                        <div className="font-semibold text-slate-900">Import OpenAPI</div>
                        <div className="text-[10px] text-slate-400">Swagger / OpenAPI endpoints</div>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setShowNewToolMenu(false);
                        setShowCustomToolModal(true);
                      }}
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors"
                    >
                      <Wrench className="w-4 h-4 text-emerald-600 shrink-0" />
                      <div>
                        <div className="font-semibold text-slate-900">Custom Built-in Tool</div>
                        <div className="text-[10px] text-slate-400">FastAPI Function & Live Test</div>
                      </div>
                    </button>
                  </div>
                </>
              )}
            </div>
          </header>

          {/* Navigation Tabs (All tools / MCP servers) */}
          <nav className="flex items-center gap-6 border-b border-slate-200 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab("all_tools")}
              className={`pb-2.5 transition-colors relative cursor-pointer ${
                activeTab === "all_tools"
                  ? "text-slate-900 font-bold border-b-2 border-slate-900"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              All tools
              {tools.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] font-semibold text-slate-600">
                  {tools.length}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("mcp_servers")}
              className={`pb-2.5 transition-colors relative cursor-pointer ${
                activeTab === "mcp_servers"
                  ? "text-slate-900 font-bold border-b-2 border-slate-900"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              MCP servers
              {mcpServers.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full bg-slate-100 text-[10px] font-semibold text-slate-600">
                  {mcpServers.length}
                </span>
              )}
            </button>
          </nav>

          {/* Tab 1: All Tools View (Satu tabel katalog untuk semuanya) */}
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
                              Pilih menu &ldquo;New tool&rdquo; untuk mendaftarkan MCP Server, Import OpenAPI, atau Custom Built-in Tool.
                            </p>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      tools.map((tool: any) => (
                        <tr key={tool.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3.5 px-6 font-semibold text-slate-900">
                            <div className="font-mono">{tool.name}</div>
                            {tool.description && (
                              <div className="text-[11px] font-normal text-slate-500 mt-0.5 line-clamp-1">
                                {tool.description}
                              </div>
                            )}
                          </td>
                          <td className="py-3.5 px-6">
                            <span
                              className={`px-2 py-0.5 rounded-full font-bold text-[10px] uppercase tracking-wider border ${
                                tool.source === "MCP"
                                  ? "bg-blue-50 text-blue-700 border-blue-200/60"
                                  : tool.source === "OPENAPI"
                                  ? "bg-indigo-50 text-indigo-700 border-indigo-200/60"
                                  : "bg-slate-100 text-slate-600 border-slate-200/60"
                              }`}
                            >
                              {tool.source}
                            </span>
                          </td>
                          <td className="py-3.5 px-6 text-slate-500 font-mono text-[11px]">
                            {tool.auth}
                          </td>
                          <td className="py-3.5 px-6">
                            <span
                              className={`inline-flex items-center gap-1.5 font-medium text-xs ${
                                tool.health === "ok"
                                  ? "text-emerald-600"
                                  : "text-amber-600"
                              }`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  tool.health === "ok"
                                    ? "bg-emerald-500"
                                    : "bg-amber-500"
                                }`}
                              />
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
            <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200/80 bg-slate-50/40 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-6 min-w-[180px]">SERVER NAME</th>
                      <th className="py-3 px-6 min-w-[220px]">ENDPOINT URL</th>
                      <th className="py-3 px-4 min-w-[130px]">TRANSPORT</th>
                      <th className="py-3 px-4 min-w-[120px]">AUTH SECRET</th>
                      <th className="py-3 px-4 min-w-[120px]">TOOLS DISCOVERED</th>
                      <th className="py-3 px-4 min-w-[100px]">STATUS</th>
                      <th className="py-3 px-4 min-w-[110px]">LAST SYNCED</th>
                      <th className="py-3 px-4 min-w-[80px] text-right">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {mcpServers.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-16 text-center">
                          <div className="flex flex-col items-center justify-center text-slate-400">
                            <Server className="w-8 h-8 mb-2 text-slate-300 stroke-[1.5]" />
                            <p className="text-xs font-semibold text-slate-600">
                              No MCP servers registered
                            </p>
                            <p className="text-[11px] text-slate-400 mt-0.5 max-w-md">
                              The registry is the allowlist — agents can only call what is listed here.
                            </p>
                            <button
                              type="button"
                              onClick={() => setShowRegisterMcpModal(true)}
                              className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-all shadow-2xs cursor-pointer"
                            >
                              <Plus className="w-3.5 h-3.5 text-slate-500" />
                              <span>Register server</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      mcpServers.map((server: any) => (
                        <tr key={server.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3.5 px-6 font-semibold text-slate-900">
                            <div className="flex items-center gap-2">
                              <Server className="w-4 h-4 text-blue-600 shrink-0" />
                              <span>{server.name}</span>
                            </div>
                          </td>
                          <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">
                            {server.endpointUrl}
                          </td>
                          <td className="py-3.5 px-4 text-slate-600">
                            {server.transport}
                          </td>
                          <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                            {server.secretName || server.auth}
                          </td>
                          <td className="py-3.5 px-4 font-mono text-slate-600">
                            {server.toolsCount} tools
                          </td>
                          <td className="py-3.5 px-4">
                            <span className="inline-flex items-center gap-1.5 text-emerald-600 font-medium text-xs">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              {server.status}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                            {server.lastSynced}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <button
                              type="button"
                              title="Sync Tools"
                              className="p-1 rounded text-slate-400 hover:text-blue-600"
                            >
                              <RefreshCw className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </main>

      {/* 3. Modal 1: Register MCP Server */}
      <RegisterMcpModal
        isOpen={showRegisterMcpModal}
        onClose={() => setShowRegisterMcpModal(false)}
        onSaveServer={handleSaveMcpServer}
      />

      {/* 4. Modal 2: Import OpenAPI */}
      <ImportOpenApiModal
        isOpen={showImportOpenApiModal}
        onClose={() => setShowImportOpenApiModal(false)}
        onSaveTools={handleSaveOpenApiTools}
      />

      {/* 5. Modal 3: Custom Built-in Tool */}
      <CustomToolModal
        isOpen={showCustomToolModal}
        onClose={() => setShowCustomToolModal(false)}
        onSaveTool={handleSaveCustomTool}
      />
    </div>
  );
}
