"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import {
  CheckCircle2,
  Plus,
  Play,
  Search,
  ChevronDown,
  Filter,
  Check,
  X,
  ExternalLink,
  Activity,
  Trash2,
  Edit2,
  FlaskConical,
  Eye,
  Award,
  Sparkles,
  RefreshCw,
} from "lucide-react";

export default function EvaluationPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("All Agents");
  const [selectedStatus, setSelectedStatus] = useState("All Statuses");
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedDetailTc, setSelectedDetailTc] = useState<any>(null);
  const [isRunningAll, setIsRunningAll] = useState(false);

  // Form states untuk Add Test Case
  const [inputScenario, setInputScenario] = useState("");
  const [expectedTool, setExpectedTool] = useState("");
  const [agentTarget, setAgentTarget] = useState("BPJS Customer Service Agent");

  const [testCases, setTestCases] = useState<any[]>([]);
  const [dbAgents, setDbAgents] = useState<{ id: string; name: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingAgents, setIsLoadingAgents] = useState(false);

  const fetchAgents = async () => {
    setIsLoadingAgents(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiUrl}/api/v1/agent`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setDbAgents(data);
          if (data.length > 0) {
            setAgentTarget(data[0].name);
          }
        }
      }
    } catch (err) {
      console.warn("Failed to fetch agents for evaluation:", err);
    } finally {
      setIsLoadingAgents(false);
    }
  };

  const fetchTestCases = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/v1/evaluation");
      if (res.ok) {
        const data = await res.json();
        setTestCases(data);
      }
    } catch (err) {
      console.warn("Failed to fetch test cases:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTestCases();
    fetchAgents();
  }, []);

  const handleAddTestCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputScenario.trim()) return;

    try {
      const res = await fetch("/api/v1/evaluation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent: agentTarget,
          input: inputScenario,
          expected: expectedTool || "search_hospital",
        }),
      });
      
      if (res.ok) {
        fetchTestCases();
        setInputScenario("");
        setExpectedTool("");
        setShowAddModal(false);
      }
    } catch (err) {
      console.error("Failed to add test case:", err);
    }
  };

  const handleDeleteTest = async (id: string) => {
    if (!confirm("Are you sure you want to delete this test case?")) return;
    try {
      const res = await fetch(`/api/v1/evaluation/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setTestCases((prev) => prev.filter((tc) => tc.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete test case:", err);
    }
  };

  const handleRunSingleTest = async (tc: any) => {
    try {
      setTestCases((prev) =>
        prev.map((t) => (t.id === tc.id ? { ...t, status: "running" } : t))
      );
      
      const res = await fetch(`/api/v1/evaluation/${tc.id}/run`, {
        method: "POST",
      });
      if (res.ok) {
        const updated = await res.json();
        setTestCases((prev) =>
          prev.map((t) => (t.id === tc.id ? updated : t))
        );
      } else {
        fetchTestCases();
      }
    } catch (err) {
      console.error("Failed to run test:", err);
      fetchTestCases();
    }
  };

  const handleRunAllTests = async () => {
    if (testCases.length === 0 || isRunningAll) return;
    setIsRunningAll(true);
    setTestCases((prev) => prev.map((t) => ({ ...t, status: "running" })));
    try {
      const res = await fetch("/api/v1/evaluation/run-all", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTestCases(data);
        }
      } else {
        fetchTestCases();
      }
    } catch (err) {
      console.error("Failed to run all tests:", err);
      fetchTestCases();
    } finally {
      setIsRunningAll(false);
    }
  };

  const handleSeedDefaults = async () => {
    try {
      setIsLoading(true);
      const res = await fetch("/api/v1/evaluation/seed-defaults", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setTestCases(data);
        }
      }
    } catch (err) {
      console.error("Failed to seed default test cases:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const passedCount = testCases.filter((tc) => tc.status === "passed").length;
  const passRate = testCases.length > 0 ? Math.round((passedCount / testCases.length) * 100) : 0;

  const filteredTestCases = testCases.filter((tc) => {
    const matchesSearch =
      (tc.input && tc.input.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (tc.expected && tc.expected.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (tc.agent && tc.agent.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesAgent =
      selectedAgent === "All Agents" ||
      (tc.agent && tc.agent.toLowerCase() === selectedAgent.toLowerCase());
    const matchesStatus =
      selectedStatus === "All Statuses" ||
      (tc.status && tc.status.toLowerCase() === selectedStatus.toLowerCase());
    return matchesSearch && matchesAgent && matchesStatus;
  });

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar Persisten */}
      <Sidebar />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-white min-w-0">
        <div className="p-8 max-w-6xl w-full mx-auto space-y-6">
          {/* Header Title & Actions */}
          <header className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  TESTING & EVALUATION
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-50 border border-purple-200/80 text-[10px] font-semibold text-purple-700">
                  <Sparkles className="w-3 h-3 text-purple-500" />
                  Judge: Grok 4.6 (Active)
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                Evaluations & Tests
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                Uji dan evaluasi keandalan respon agent terhadap skenario input, expected tools, dan aturan harness secara otomatis.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleSeedDefaults}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-all shadow-2xs cursor-pointer"
                title="Muat 5 Test Case Standar BPJS"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                <span>Muat Template BPJS</span>
              </button>

              <button
                type="button"
                onClick={() => setShowAddModal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 text-slate-500" />
                <span>Add Test Case</span>
              </button>

              <button
                type="button"
                onClick={handleRunAllTests}
                disabled={testCases.length === 0 || isRunningAll}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Play className={`w-3.5 h-3.5 fill-current ${isRunningAll ? "animate-spin" : ""}`} />
                <span>{isRunningAll ? "Evaluating All..." : "Run All Tests"}</span>
              </button>
            </div>
          </header>

          {/* Metric Summary Overview Cards */}
          <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-4 rounded-2xl border border-slate-200 bg-white shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Total Test Cases
              </span>
              <div className="text-xl font-bold text-slate-900 mt-1">
                {testCases.length}
              </div>
            </div>

            <div className="p-4 rounded-2xl border border-slate-200 bg-white shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Pass Rate
              </span>
              <div
                className={`text-xl font-bold mt-1 ${
                  passRate >= 80 ? "text-emerald-600" : passRate > 0 ? "text-amber-600" : "text-slate-400"
                }`}
              >
                {testCases.length > 0 ? `${passRate}%` : "0%"}
              </div>
            </div>

            <div className="p-4 rounded-2xl border border-slate-200 bg-white shadow-2xs">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Status Terakhir
              </span>
              <div className="text-xl font-bold text-slate-700 mt-1">
                {testCases.length > 0 ? "Evaluated" : "Idle"}
              </div>
            </div>
          </section>

          {/* Search & Filter Toolbar */}
          <section className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search test cases..."
                className="w-full pl-9 pr-4 py-2 rounded-xl border border-slate-200 bg-white text-xs text-slate-800 placeholder:text-slate-400 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition-all shadow-2xs"
              />
            </div>

            <div className="flex items-center gap-2">
              <div className="relative">
                <select
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="appearance-none inline-flex items-center justify-between gap-2 px-3 pr-8 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-2xs outline-hidden cursor-pointer"
                >
                  <option value="All Agents">All Agents</option>
                  {dbAgents.map((agent) => (
                    <option key={agent.id} value={agent.name}>
                      {agent.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              </div>

              <div className="relative">
                <select
                  value={selectedStatus}
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="appearance-none inline-flex items-center justify-between gap-2 px-3 pr-8 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-2xs outline-hidden cursor-pointer"
                >
                  <option value="All Statuses">All Statuses</option>
                  <option value="passed">Passed</option>
                  <option value="failed">Failed</option>
                  <option value="running">Running</option>
                </select>
                <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" />
              </div>
            </div>
          </section>

          {/* Test Cases Table Layout */}
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200/80 bg-slate-50/40 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-6 min-w-[240px]">TEST CASE / INPUT</th>
                    <th className="py-3 px-6 min-w-[180px]">EXPECTED OUTCOME</th>
                    <th className="py-3 px-6 min-w-[180px]">ACTUAL OUTPUT</th>
                    <th className="py-3 px-4 min-w-[120px]">STATUS & SKOR</th>
                    <th className="py-3 px-4 min-w-[110px]">LAST RUN</th>
                    <th className="py-3 px-4 min-w-[100px] text-right">ACTIONS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {filteredTestCases.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-16 text-center">
                        <div className="flex flex-col items-center justify-center text-slate-400">
                          <FlaskConical className="w-8 h-8 mb-2 text-slate-300 stroke-[1.5]" />
                          <p className="text-xs font-semibold text-slate-600">
                            {testCases.length === 0
                              ? "Belum ada test case evaluasi"
                              : "Tidak ada test case yang cocok dengan filter"}
                          </p>
                          <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm">
                            Tambahkan test case untuk menguji perilaku agent terhadap input tertentu (misal: pencarian RS, eskalasi, atau booking).
                          </p>
                          <div className="flex items-center gap-2 mt-4">
                            <button
                              type="button"
                              onClick={handleSeedDefaults}
                              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer"
                            >
                              <Sparkles className="w-3.5 h-3.5" />
                              <span>Muat 5 Test Case BPJS</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => setShowAddModal(true)}
                              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-all shadow-2xs cursor-pointer"
                            >
                              <Plus className="w-3.5 h-3.5 text-slate-500" />
                              <span>Add Test Case</span>
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredTestCases.map((tc) => (
                      <tr key={tc.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3.5 px-6 font-semibold text-slate-900">
                          <div>&ldquo;{tc.input}&rdquo;</div>
                          {tc.agent && (
                            <div className="text-[10px] text-blue-600 font-medium mt-0.5 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                              <span>Agent: {tc.agent}</span>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">
                          {tc.expected}
                        </td>
                        <td className="py-3.5 px-6 text-[11px] text-slate-500 max-w-xs">
                          <p className="line-clamp-2">{tc.actual || "-"}</p>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-bold border uppercase ${
                                tc.status === "passed"
                                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                                  : tc.status === "failed"
                                  ? "bg-rose-50 text-rose-700 border-rose-200"
                                  : tc.status === "running"
                                  ? "bg-amber-50 text-amber-700 border-amber-200 animate-pulse"
                                  : "bg-slate-100 text-slate-600 border-slate-200"
                              }`}
                            >
                              {tc.status}
                            </span>
                            {tc.score !== null && tc.score !== undefined && (
                              <span className="text-xs font-extrabold text-slate-900 font-mono">
                                {tc.score}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                          {tc.lastRun || "-"}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {tc.details && (
                              <button
                                type="button"
                                title="Lihat Detail Nilai Juri"
                                onClick={() => setSelectedDetailTc(tc)}
                                className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer"
                              >
                                <Eye className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <button
                              type="button"
                              title="Run single test"
                              onClick={() => handleRunSingleTest(tc)}
                              disabled={tc.status === "running"}
                              className="p-1.5 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-slate-100 disabled:opacity-50 transition-colors cursor-pointer"
                            >
                              <Play className="w-3.5 h-3.5 fill-current" />
                            </button>
                            <button
                              type="button"
                              title="Delete test"
                              onClick={() => handleDeleteTest(tc.id)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
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
        </div>
      </main>

      {/* Add Test Case Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-4 h-4 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Add Test Case
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddTestCase} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Target Agent
                </label>
                <select
                  value={agentTarget}
                  onChange={(e) => setAgentTarget(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 bg-white"
                >
                  {dbAgents.length > 0 ? (
                    dbAgents.map((agent) => (
                      <option key={agent.id} value={agent.name}>
                        {agent.name}
                      </option>
                    ))
                  ) : (
                    <option value="BPJS Customer Service Agent">
                      {isLoadingAgents ? "Memuat daftar agent..." : "BPJS Customer Service Agent"}
                    </option>
                  )}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Input Skenario User
                </label>
                <input
                  type="text"
                  value={inputScenario}
                  onChange={(e) => setInputScenario(e.target.value)}
                  placeholder="contoh: Cari RS BPJS di Jakarta"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Expected Behavior / Tool
                </label>
                <input
                  type="text"
                  value={expectedTool}
                  onChange={(e) => setExpectedTool(e.target.value)}
                  placeholder="contoh: search_hospital / escalated / blocked"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold shadow-2xs"
                >
                  Save Test Case
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Evaluation Detail Modal (LLM as a Judge Report) */}
      {selectedDetailTc && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-blue-100 text-blue-700 rounded-xl">
                  <Award className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    Rapor Evaluasi (LLM as a Judge)
                  </h3>
                  <p className="text-[11px] text-slate-500 flex items-center gap-1.5 flex-wrap">
                    <span>Target Agent: <strong className="text-slate-700">{selectedDetailTc.agent}</strong></span>
                    <span className="px-1.5 py-0.5 rounded bg-purple-50 border border-purple-200 text-purple-700 font-mono text-[10px]">
                      Judge: {selectedDetailTc.details?.judge_model || "x-ai/grok-4.6"}
                    </span>
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDetailTc(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs">
              {/* Score Summary Banner */}
              <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50/30">
                <div className="space-y-1">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                    Hasil Pengujian
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full font-bold uppercase border ${
                        selectedDetailTc.status === "passed"
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-rose-50 text-rose-700 border-rose-200"
                      }`}
                    >
                      {selectedDetailTc.status}
                    </span>
                    <span className="text-slate-400 text-[11px]">
                      {selectedDetailTc.lastRun}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 italic mt-1">
                    {selectedDetailTc.details?.summary || "Evaluasi otomatis selesai."}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-black font-mono text-slate-900">
                    {selectedDetailTc.score ?? selectedDetailTc.details?.overall_score ?? 0}
                    <span className="text-sm text-slate-400 font-normal">/100</span>
                  </div>
                  <div className="text-[10px] text-slate-500 font-medium">Weighted Score</div>
                </div>
              </div>

              {/* 5 Breakdown Metrics */}
              {selectedDetailTc.details?.scores && (
                <div className="space-y-3">
                  <h4 className="font-bold text-slate-900 flex items-center gap-1.5 text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                    <span>Breakdown 5 Metrik Evaluasi AI</span>
                  </h4>
                  <div className="grid grid-cols-1 gap-2.5">
                    {/* 1. Tool Accuracy */}
                    <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-700">
                          1. Tool Calling Accuracy (Bobot 30%)
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          {selectedDetailTc.details.scores.tool_accuracy ?? 0}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-blue-600 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${selectedDetailTc.details.scores.tool_accuracy ?? 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Evaluasi pemanggilan tool yang diharapkan ({selectedDetailTc.expected || "none"}).
                      </div>
                    </div>

                    {/* 2. SOP Compliance */}
                    <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-700">
                          2. Policy & SOP Adherence (Bobot 25%)
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          {selectedDetailTc.details.scores.sop_compliance ?? 0}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-indigo-600 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${selectedDetailTc.details.scores.sop_compliance ?? 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Kepatuhan pada alur verifikasi data pengguna, faskes rujukan, dan konfirmasi.
                      </div>
                    </div>

                    {/* 3. Factual Accuracy */}
                    <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-700">
                          3. Faithfulness / Anti-Halusinasi (Bobot 20%)
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          {selectedDetailTc.details.scores.factual_accuracy ?? 0}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-emerald-600 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${selectedDetailTc.details.scores.factual_accuracy ?? 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Kesesuaian respon fakta dengan data output tool dan sistem prompt.
                      </div>
                    </div>

                    {/* 4. Safety & Guardrails */}
                    <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-700 flex items-center gap-1">
                          <span>4. Safety & Guardrails (Bobot 15% - Critical Gate)</span>
                        </span>
                        <span className={`font-mono font-bold ${
                          (selectedDetailTc.details.scores.safety_guardrails ?? 0) < 60 ? "text-rose-600" : "text-slate-900"
                        }`}>
                          {selectedDetailTc.details.scores.safety_guardrails ?? 0}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-1.5 rounded-full transition-all duration-500 ${
                            (selectedDetailTc.details.scores.safety_guardrails ?? 0) < 60 ? "bg-rose-500" : "bg-teal-600"
                          }`}
                          style={{ width: `${selectedDetailTc.details.scores.safety_guardrails ?? 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Penapisan kondisi gawat darurat (Red Flag) wajib mengarahkan ke IGD 119/118.
                      </div>
                    </div>

                    {/* 5. Answer Relevance */}
                    <div className="p-3 rounded-xl border border-slate-100 bg-slate-50/50 space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-700">
                          5. Answer Relevance & Tone (Bobot 10%)
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          {selectedDetailTc.details.scores.answer_relevance ?? 0}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-200 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-amber-500 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${selectedDetailTc.details.scores.answer_relevance ?? 0}%` }}
                        />
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Keringkasan dan relevansi kalimat menjawab kebutuhan pengguna.
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Strengths & Improvements */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="p-3.5 rounded-xl border border-emerald-100 bg-emerald-50/40 space-y-1.5">
                  <div className="font-bold text-emerald-800 text-[11px] uppercase tracking-wide flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Kelebihan Respon</span>
                  </div>
                  <ul className="list-disc list-inside text-slate-700 space-y-1 text-[11px]">
                    {selectedDetailTc.details?.strengths?.map((item: string, idx: number) => (
                      <li key={idx}>{item}</li>
                    )) || <li>Respon memenuhi standar dasar.</li>}
                  </ul>
                </div>

                <div className="p-3.5 rounded-xl border border-amber-100 bg-amber-50/40 space-y-1.5">
                  <div className="font-bold text-amber-800 text-[11px] uppercase tracking-wide flex items-center gap-1">
                    <Activity className="w-3.5 h-3.5 text-amber-600" />
                    <span>Rekomendasi Perbaikan</span>
                  </div>
                  <ul className="list-disc list-inside text-slate-700 space-y-1 text-[11px]">
                    {selectedDetailTc.details?.areas_for_improvement?.map((item: string, idx: number) => (
                      <li key={idx}>{item}</li>
                    )) || <li>Tidak ada catatan perbaikan signifikan.</li>}
                  </ul>
                </div>
              </div>

              {/* Input vs Output Section */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <div className="space-y-1">
                  <div className="text-[11px] font-bold text-slate-700">Input Pengguna:</div>
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[11px] text-slate-800">
                    &ldquo;{selectedDetailTc.input}&rdquo;
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[11px] font-bold text-slate-700">Respon Aktual Agent:</div>
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-700 max-h-36 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {selectedDetailTc.actual || "Belum ada respon yang dieksekusi."}
                  </div>
                </div>

                {selectedDetailTc.details?.actual_tools && selectedDetailTc.details.actual_tools.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-bold text-slate-700">Tool yang Dipanggil:</div>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedDetailTc.details.actual_tools.map((t: string, idx: number) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[10px]"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 border-t border-slate-100 flex justify-end bg-slate-50/50">
              <button
                type="button"
                onClick={() => setSelectedDetailTc(null)}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition-colors"
              >
                Tutup Rapor
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
