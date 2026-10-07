"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import {
  Rocket,
  Copy,
  Check,
  Key,
  Globe,
  Terminal,
  Code2,
  RefreshCw,
  ExternalLink,
  Shield,
  Cloud,
  Trash2,
} from "lucide-react";

export default function DeploymentsPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [copiedKey, setCopiedKey] = useState(false);
  const [copiedEndpoint, setCopiedEndpoint] = useState(false);
  const [activeSnippetTab, setActiveSnippetTab] = useState<"curl" | "js" | "python">("curl");
  const [deployInfo, setDeployInfo] = useState<any>(null);

  const [deployments, setDeployments] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchDeployStatus = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/deployment/status`);
      if (res.ok) {
        const data = await res.json();
        setDeployInfo(data);
      }
    } catch (e) {
      console.warn("Gagal mengambil status deploy:", e);
    }
  };

  const fetchDeployments = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${apiUrl}/api/v1/deployments`);
      if (res.ok) {
        const data = await res.json();
        setDeployments(data);
      }
    } catch (err) {
      console.warn("Failed to fetch deployments:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDeployStatus();
    fetchDeployments();
  }, []);

  const handleCreateDeployment = async () => {
    try {
      const res = await fetch(`${apiUrl}/api/v1/deployments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent: "New Agent " + Math.floor(Math.random() * 1000),
          environment: "production",
          path: "/api/agents/new/run",
          status: "Ready",
        }),
      });
      if (res.ok) {
        fetchDeployments();
      }
    } catch (err) {
      console.error("Failed to create deployment:", err);
    }
  };

  const handleDeleteDeployment = async (id: string) => {
    if (!confirm("Are you sure you want to delete this deployment?")) return;
    try {
      const res = await fetch(`${apiUrl}/api/v1/deployments/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setDeployments((prev) => prev.filter((d) => d.id !== id));
      }
    } catch (err) {
      console.error("Failed to delete deployment:", err);
    }
  };

  const sampleEndpoint = deployInfo?.endpoint || "http://localhost:8080/invoke";
  const apiKey = deployInfo?.api_key || "agy_live_9f82a17b8c34e91204";

  const handleCopy = (text: string, type: "key" | "endpoint") => {
    navigator.clipboard.writeText(text);
    if (type === "key") {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    } else {
      setCopiedEndpoint(true);
      setTimeout(() => setCopiedEndpoint(false), 2000);
    }
  };

  const curlSnippet = `curl -X POST "${sampleEndpoint}" \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Cari RS BPJS di Jakarta", "session_id": "ses-101"}'`;

  const jsSnippet = `const response = await fetch("${sampleEndpoint}", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${apiKey}",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    message: "Cari RS BPJS di Jakarta",
    session_id: "ses-101"
  })
});
const data = await response.json();`;

  const pythonSnippet = `import requests

res = requests.post(
    "${sampleEndpoint}",
    headers={"Authorization": "Bearer ${apiKey}"},
    json={"message": "Cari RS BPJS di Jakarta", "session_id": "ses-101"}
)
print(res.json())`;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar Persisten */}
      <Sidebar />

      {/* 2. Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-y-auto bg-white min-w-0">
        <div className="p-8 max-w-6xl w-full mx-auto space-y-6">
          {/* Header Title */}
          <header>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                INTEGRATION & HOSTING
              </span>
            </div>
            <div className="flex items-center justify-between w-full">
              <div>
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                  Deployments
                </h1>
                <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl leading-relaxed">
                  Kelola endpoint publik terpublikasi, API key, dan panduan integrasi runtime agent ke sistem eksternal.
                </p>
              </div>
              <button
                onClick={handleCreateDeployment}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-all shadow-2xs cursor-pointer"
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Publish Agent</span>
              </button>
            </div>
          </header>

          {/* Section 1: Endpoint & API Key Management Cards */}
          <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Active Endpoint Card */}
            <div className="p-5 rounded-2xl border border-slate-200 bg-white shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-bold text-slate-900">
                    Public REST Endpoint
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200">
                  Ready
                </span>
              </div>

              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700 overflow-x-auto">
                <span className="text-blue-600 font-bold">POST</span>
                <span className="truncate flex-1">{sampleEndpoint}</span>
                <button
                  type="button"
                  onClick={() => handleCopy(sampleEndpoint, "endpoint")}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors shrink-0"
                  title="Copy Endpoint"
                >
                  {copiedEndpoint ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              <p className="text-[11px] text-slate-400">
                Format respon mendukung standard JSON & Server-Sent Events (SSE) streaming.
              </p>
            </div>

            {/* API Key Card */}
            <div className="p-5 rounded-2xl border border-slate-200 bg-white shadow-2xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4 text-amber-500" />
                  <span className="text-xs font-bold text-slate-900">
                    API Key Authentication
                  </span>
                </div>
                <button
                  type="button"
                  className="text-[11px] text-blue-600 hover:text-blue-700 font-semibold inline-flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  Regenerate
                </button>
              </div>

              <div className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-50 border border-slate-200 font-mono text-xs text-slate-700">
                <span className="truncate flex-1 font-mono">agy_live_••••••••••••••••</span>
                <button
                  type="button"
                  onClick={() => handleCopy(apiKey, "key")}
                  className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors shrink-0"
                  title="Copy Key"
                >
                  {copiedKey ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>

              <p className="text-[11px] text-slate-400">
                Kirim melalui header <code className="text-slate-600 font-mono">Authorization: Bearer &lt;KEY&gt;</code>.
              </p>
            </div>
          </section>

          {/* Section 2: Code Snippets Integrasi */}
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
            <div className="px-6 py-3 border-b border-slate-200/80 bg-slate-50/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Terminal className="w-4 h-4 text-slate-500" />
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setActiveSnippetTab("curl")}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      activeSnippetTab === "curl"
                        ? "bg-white text-slate-900 shadow-2xs border border-slate-200"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    cURL
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveSnippetTab("js")}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      activeSnippetTab === "js"
                        ? "bg-white text-slate-900 shadow-2xs border border-slate-200"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    JavaScript / Fetch
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveSnippetTab("python")}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                      activeSnippetTab === "python"
                        ? "bg-white text-slate-900 shadow-2xs border border-slate-200"
                        : "text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    Python (Requests)
                  </button>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  const text =
                    activeSnippetTab === "curl"
                      ? curlSnippet
                      : activeSnippetTab === "js"
                      ? jsSnippet
                      : pythonSnippet;
                  navigator.clipboard.writeText(text);
                }}
                className="text-[11px] text-slate-500 hover:text-slate-800 inline-flex items-center gap-1 font-medium"
              >
                <Copy className="w-3 h-3" />
                <span>Salin Kode</span>
              </button>
            </div>

            <div className="p-5 bg-slate-950 text-slate-200 font-mono text-xs overflow-x-auto">
              <pre className="leading-relaxed">
                {activeSnippetTab === "curl" && curlSnippet}
                {activeSnippetTab === "js" && jsSnippet}
                {activeSnippetTab === "python" && pythonSnippet}
              </pre>
            </div>
          </section>

          {/* Section 3: Deployments Status Table Layout */}
          <section className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200/80 bg-slate-50/40 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    <th className="py-3 px-6 min-w-[200px]">AGENT</th>
                    <th className="py-3 px-6 min-w-[140px]">ENVIRONMENT</th>
                    <th className="py-3 px-6 min-w-[240px]">ENDPOINT PATH</th>
                    <th className="py-3 px-4 min-w-[110px]">STATUS</th>
                    <th className="py-3 px-6 min-w-[140px]">DEPLOYED AT</th>
                    <th className="py-3 px-4 min-w-[80px] text-right">ACTIONS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-slate-400">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                          <span>Loading deployments...</span>
                        </div>
                      </td>
                    </tr>
                  ) : deployments.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-16 text-center">
                        <div className="flex flex-col items-center justify-center text-slate-400">
                          <Cloud className="w-8 h-8 mb-2 text-slate-300 stroke-[1.5]" />
                          <p className="text-xs font-semibold text-slate-600">
                            Belum ada riwayat deployment aktif
                          </p>
                          <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm">
                            Agent yang berstatus &ldquo;Published&rdquo; akan otomatis mendapatkan endpoint dan tampil di tabel ini.
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    deployments.map((dep) => (
                      <tr key={dep.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3.5 px-6 font-semibold text-slate-900">{dep.agent}</td>
                        <td className="py-3.5 px-6">{dep.environment}</td>
                        <td className="py-3.5 px-6 font-mono text-[11px] text-slate-600">{dep.path}</td>
                        <td className="py-3.5 px-4">{dep.status}</td>
                        <td className="py-3.5 px-6 text-slate-400">{new Date(dep.deployedAt).toLocaleDateString()}</td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            type="button"
                            onClick={() => handleDeleteDeployment(dep.id)}
                            className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
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
        </div>
      </main>
    </div>
  );
}
