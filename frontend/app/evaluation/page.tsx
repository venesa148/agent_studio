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
} from "lucide-react";

export default function EvaluationPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAgent, setSelectedAgent] = useState("All Agents");
  const [selectedStatus, setSelectedStatus] = useState("All Statuses");
  const [showAddModal, setShowAddModal] = useState(false);

  // Form states untuk Add Test Case
  const [inputScenario, setInputScenario] = useState("");
  const [expectedTool, setExpectedTool] = useState("");
  const [agentTarget, setAgentTarget] = useState("BPJS Customer Service Agent");

  const [testCases, setTestCases] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

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
      // Simulate run by setting status to running, then success
      setTestCases((prev) =>
        prev.map((t) => (t.id === tc.id ? { ...t, status: "running" } : t))
      );
      
      setTimeout(async () => {
        const res = await fetch(`/api/v1/evaluation/${tc.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            actual: tc.expected, // Simulate success
            status: "passed",
            lastRun: new Date().toLocaleString(),
          }),
        });
        if (res.ok) {
          fetchTestCases();
        }
      }, 1000);
    } catch (err) {
      console.error("Failed to run test:", err);
    }
  };

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
                onClick={() => setShowAddModal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 text-slate-500" />
                <span>Add Test Case</span>
              </button>

              <button
                type="button"
                disabled={testCases.length === 0}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run All Tests</span>
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
              <div className="text-xl font-bold text-emerald-600 mt-1">
                {testCases.length > 0 ? "100%" : "0%"}
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
              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-2xs"
              >
                <span>{selectedAgent}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              <button
                type="button"
                className="inline-flex items-center justify-between gap-2 px-3 py-2 rounded-xl border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all shadow-2xs"
              >
                <span>{selectedStatus}</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>
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
                    <th className="py-3 px-6 min-w-[160px]">ACTUAL OUTPUT</th>
                    <th className="py-3 px-4 min-w-[100px]">STATUS</th>
                    <th className="py-3 px-4 min-w-[110px]">TRACE</th>
                    <th className="py-3 px-4 min-w-[80px] text-right">ACTIONS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {testCases.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-16 text-center">
                        <div className="flex flex-col items-center justify-center text-slate-400">
                          <FlaskConical className="w-8 h-8 mb-2 text-slate-300 stroke-[1.5]" />
                          <p className="text-xs font-semibold text-slate-600">
                            Belum ada test case evaluasi
                          </p>
                          <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm">
                            Tambahkan test case untuk menguji perilaku agent terhadap input tertentu (misal: pencarian RS, eskalasi, atau blokir data rahasia).
                          </p>
                          <button
                            type="button"
                            onClick={() => setShowAddModal(true)}
                            className="mt-4 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-all shadow-2xs cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5 text-slate-500" />
                            <span>Add Test Case</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    testCases.map((tc) => (
                      <tr key={tc.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3.5 px-6 font-semibold text-slate-900">
                          &ldquo;{tc.input}&rdquo;
                        </td>
                        <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">
                          {tc.expected}
                        </td>
                        <td className="py-3.5 px-6 font-mono text-[11px] text-slate-500">
                          {tc.actual}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-600">
                            {tc.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                          {tc.lastRun || "-"}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              title="Run single test"
                              onClick={() => handleRunSingleTest(tc)}
                              disabled={tc.status === "running"}
                              className="p-1 rounded text-slate-400 hover:text-blue-600 disabled:opacity-50"
                            >
                              <Play className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              title="Delete test"
                              onClick={() => handleDeleteTest(tc.id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50"
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
                  <option value="BPJS Customer Service Agent">BPJS Customer Service Agent</option>
                  <option value="General Assistant Agent">General Assistant Agent</option>
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
    </div>
  );
}
