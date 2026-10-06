"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import { RegisterMcpModal } from "@/features/tools/RegisterMcpModal";
import { ImportOpenApiModal } from "@/features/tools/ImportOpenApiModal";
import { EditToolModal } from "@/features/tools/EditToolModal";
import { CustomToolModal } from "@/features/tools/CustomToolModal";
import {
  Plus,
  ChevronDown,
  Server,
  Wrench,
  Globe,
  RefreshCw,
  Pencil,
  Trash2,
} from "lucide-react";

export type ToolsTab = "all_tools" | "mcp_servers";
const API_URL = "http://localhost:8000/api/v1";

export default function ToolsRegistryPage() {
  const [activeTab, setActiveTab] = useState<ToolsTab>("all_tools");
  const [showNewToolMenu, setShowNewToolMenu] = useState(false);

  // Modal visibility states
  const [showRegisterMcpModal, setShowRegisterMcpModal] = useState(false);
  const [showImportOpenApiModal, setShowImportOpenApiModal] = useState(false);
  const [showCustomToolModal, setShowCustomToolModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingTool, setEditingTool] = useState<any | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Unified tables state
  const [tools, setTools] = useState<any[]>([]);
  const [mcpServers, setMcpServers] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch Tools and MCP servers on mount or tab change
  const fetchData = async () => {
    setIsLoading(true);
    try {
      if (activeTab === "all_tools") {
        const res = await fetch(`${API_URL}/tools`);
        if (res.ok) {
          const data = await res.json();
          setTools(data);
        }
      } else if (activeTab === "mcp_servers") {
        const res = await fetch(`${API_URL}/mcp`);
        if (res.ok) {
          const data = await res.json();
          setMcpServers(data);
        }
      }
    } catch (err) {
      console.warn("Failed to fetch data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  // Handlers for adding newly registered items
  const readError = async (res: Response) => {
    const payload = await res.json().catch(() => ({}));
    return payload.detail || "Permintaan tidak dapat diproses.";
  };

  const handleSaveMcpServer = async (serverData: any) => {
    const res = await fetch(`${API_URL}/mcp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: serverData.name, url: serverData.endpointUrl }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const server = await res.json();
    setMcpServers((previous) => [server, ...previous]);
    setActiveTab("mcp_servers");
  };

  const handleSaveOpenApiTools = async (sourceData: any) => {
    const res = await fetch(`${API_URL}/tools/import-openapi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec_url: sourceData.specUrl, name_prefix: sourceData.prefix || null }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const importedTools = await res.json();
    setTools((previous) => [...importedTools, ...previous]);
    setActiveTab("all_tools");
  };

  const handleSaveCustomTool = async (toolData: any) => {
    const properties = Object.fromEntries(
      toolData.parameters.filter((parameter: any) => parameter.name.trim()).map((parameter: any) => [
        parameter.name.trim(),
        { type: parameter.type, description: parameter.description || undefined },
      ])
    );
    const input_schema = {
      type: "object",
      properties,
      required: toolData.parameters.filter((parameter: any) => parameter.required && parameter.name.trim()).map((parameter: any) => parameter.name.trim()),
    };
    const res = await fetch(`${API_URL}/tools`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: toolData.name, description: toolData.description, source_type: "builtin", input_schema }),
    });
    if (!res.ok) throw new Error(await readError(res));
    const tool = await res.json();
    setTools((previous) => [tool, ...previous]);
    setActiveTab("all_tools");
  };

  const handleUpdateTool = async (toolId: string, updatedData: { name: string; description: string }) => {
    const res = await fetch(`${API_URL}/tools/${toolId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updatedData),
    });
    if (!res.ok) throw new Error(await readError(res));
    const updatedTool = await res.json();
    setTools((prev) => prev.map((t) => (t.id === toolId ? updatedTool : t)));
  };

  const handleDeleteTool = async (toolId: string, toolName: string) => {
    if (!confirm(`Apakah Anda yakin ingin menghapus tool '${toolName}'?`)) return;
    setDeletingId(toolId);
    try {
      const res = await fetch(`${API_URL}/tools/${toolId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await readError(res));
      setTools((prev) => prev.filter((t) => t.id !== toolId));
    } catch (err: any) {
      alert(err.message || "Gagal menghapus tool.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDeleteMcpServer = async (serverId: string, serverName: string) => {
    if (!confirm(`Apakah Anda yakin ingin menghapus MCP server '${serverName}'? Tools yang terhubung juga akan dihapus.`)) return;
    setDeletingId(serverId);
    try {
      const res = await fetch(`${API_URL}/mcp/${serverId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await readError(res));
      setMcpServers((prev) => prev.filter((s) => s.id !== serverId));
    } catch (err: any) {
      alert(err.message || "Gagal menghapus MCP server.");
    } finally {
      setDeletingId(null);
    }
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
                Tools Registry
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                Katalog global seluruh tools — MCP, HTTP, OpenAPI-imported, built-in — dengan status keandalan dan otoritas akses.
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
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors cursor-pointer"
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
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors cursor-pointer"
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
                      className="w-full text-left px-3.5 py-2 text-slate-700 hover:bg-slate-50 flex items-center gap-2.5 transition-colors cursor-pointer"
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
                      <th className="py-3 px-6 min-w-[100px] text-right">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {isLoading ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400">
                          <div className="flex items-center justify-center gap-2">
                            <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                            <span>Loading tools...</span>
                          </div>
                        </td>
                      </tr>
                    ) : tools.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-16 text-center">
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
                        <tr key={tool.id || tool.name} className="hover:bg-slate-50/60 transition-colors">
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
                                (tool.source_type || tool.source) === "mcp" || (tool.source_type || tool.source) === "MCP"
                                  ? "bg-blue-50 text-blue-700 border-blue-200/60"
                                  : (tool.source_type || tool.source) === "openapi" || (tool.source_type || tool.source) === "OPENAPI"
                                  ? "bg-indigo-50 text-indigo-700 border-indigo-200/60"
                                  : "bg-slate-100 text-slate-600 border-slate-200/60"
                              }`}
                            >
                              {tool.source_type || tool.source || "builtin"}
                            </span>
                          </td>
                          <td className="py-3.5 px-6 text-slate-500 font-mono text-[11px]">
                            {tool.auth_custody || tool.auth || "none"}
                          </td>
                          <td className="py-3.5 px-6">
                            <span
                              className={`inline-flex items-center gap-1.5 font-medium text-xs ${
                                (tool.health_status || tool.health) === "ok"
                                  ? "text-emerald-600"
                                  : "text-amber-600"
                              }`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${
                                  (tool.health_status || tool.health) === "ok"
                                    ? "bg-emerald-500"
                                    : "bg-amber-500"
                                }`}
                              />
                              {tool.health_status || tool.health || "ok"}
                            </span>
                          </td>
                          <td className="py-3.5 px-6 text-slate-500 text-xs">
                            {tool.used_by || tool.usedBy || "0 agents"}
                          </td>
                          <td className="py-3.5 px-6 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <button
                                type="button"
                                title="Edit tool"
                                onClick={() => {
                                  setEditingTool(tool);
                                  setShowEditModal(true);
                                }}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer"
                              >
                                <Pencil className="w-3.5 h-3.5" />
                              </button>
                              <button
                                type="button"
                                title="Hapus tool"
                                disabled={deletingId === tool.id}
                                onClick={() => handleDeleteTool(tool.id, tool.name)}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 disabled:opacity-50 transition-colors cursor-pointer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
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
                      <th className="py-3 px-4 min-w-[130px]">STATUS</th>
                      <th className="py-3 px-4 min-w-[110px]">CREATED AT</th>
                      <th className="py-3 px-4 min-w-[80px] text-right">ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-xs">
                    {isLoading ? (
                      <tr>
                        <td colSpan={4} className="py-12 text-center text-slate-400">
                          <div className="flex items-center justify-center gap-2">
                            <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                            <span>Loading MCP Servers...</span>
                          </div>
                        </td>
                      </tr>
                    ) : mcpServers.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-16 text-center">
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
                        <tr key={server.id || server.name} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-3.5 px-6 font-semibold text-slate-900">
                            <div className="flex items-center gap-2">
                              <Server className="w-4 h-4 text-blue-600 shrink-0" />
                              <span>{server.name}</span>
                            </div>
                          </td>
                          <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">
                            {server.url || server.endpointUrl}
                          </td>
                          <td className="py-3.5 px-4">
                            <span className="inline-flex items-center gap-1.5 text-emerald-600 font-medium text-xs">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              {server.status || "active"}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                            {server.created_at ? new Date(server.created_at).toLocaleDateString() : "-"}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <button
                              type="button"
                              title="Hapus MCP Server"
                              disabled={deletingId === server.id}
                              onClick={() => handleDeleteMcpServer(server.id, server.name)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 disabled:opacity-50 transition-colors cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
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

      {/* 6. Modal 4: Edit Tool */}
      <EditToolModal
        isOpen={showEditModal}
        tool={editingTool}
        onClose={() => {
          setShowEditModal(false);
          setEditingTool(null);
        }}
        onSaveTool={handleUpdateTool}
      />
    </div>
  );
}
