"use client";

import React, { useState } from "react";
import {
  X,
  Server,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronDown,
} from "lucide-react";

interface SuggestedServer {
  name: string;
  badge?: "no key" | "oauth";
  description: string;
  defaultUrl: string;
  authDefault: "No credential" | "Bearer token" | "API Key";
}

const SUGGESTED_SERVERS: SuggestedServer[] = [
  {
    name: "Cloudflare Docs",
    badge: "no key",
    description:
      "Search Cloudflare's product documentation. No account or key — the easiest first connection.",
    defaultUrl: "https://docs.cloudflare.com/mcp",
    authDefault: "No credential",
  },
  {
    name: "Exa Search",
    description:
      "Web search and page extraction built for agents. Works without a key at low rate limits.",
    defaultUrl: "https://api.exa.ai/mcp",
    authDefault: "No credential",
  },
  {
    name: "Context7",
    description:
      "Current documentation for thousands of libraries — stops agents inventing APIs.",
    defaultUrl: "https://context7.com/mcp",
    authDefault: "No credential",
  },
  {
    name: "GitHub",
    description:
      "Repositories, issues, pull requests, code search and Actions runs.",
    defaultUrl: "https://api.github.com/mcp",
    authDefault: "Bearer token",
  },
  {
    name: "Linear",
    description: "Issues, projects and cycles — read and write.",
    defaultUrl: "https://api.linear.app/mcp",
    authDefault: "API Key",
  },
  {
    name: "Stripe",
    description:
      "Customers, payments and subscriptions, plus Stripe's own docs.",
    defaultUrl: "https://mcp.stripe.com",
    authDefault: "API Key",
  },
  {
    name: "Neon Postgres",
    description: "Query and branch serverless Postgres databases.",
    defaultUrl: "https://console.neon.tech/mcp",
    authDefault: "API Key",
  },
  {
    name: "Supabase",
    description:
      "Project management and Postgres access. Add ?project_ref=<id>&read_only=true to scope it.",
    defaultUrl: "https://api.supabase.com/mcp",
    authDefault: "API Key",
  },
  {
    name: "Hugging Face",
    description:
      "Search models, datasets and Spaces; run Gradio apps as tools.",
    defaultUrl: "https://huggingface.co/mcp",
    authDefault: "Bearer token",
  },
  {
    name: "Tavily",
    description: "Search, extract and crawl the web with citations.",
    defaultUrl: "https://api.tavily.com/mcp",
    authDefault: "API Key",
  },
  {
    name: "Notion",
    badge: "oauth",
    description: "Pages, databases and search across a Notion workspace.",
    defaultUrl: "https://api.notion.com/mcp",
    authDefault: "Bearer token",
  },
  {
    name: "Sentry",
    badge: "oauth",
    description: "Issues, traces and Seer analysis for your projects.",
    defaultUrl: "https://sentry.io/mcp",
    authDefault: "Bearer token",
  },
  {
    name: "Atlassian (Jira & Confluence)",
    badge: "oauth",
    description: "Jira issues and Confluence pages through Rovo.",
    defaultUrl: "https://api.atlassian.com/mcp",
    authDefault: "Bearer token",
  },
];

const AVAILABLE_SECRETS = [
  "HOSPITAL_API_KEY",
  "BPJS_SERVICE_SECRET",
  "OPENROUTER_SECRET",
  "GITHUB_PERSONAL_TOKEN",
  "STRIPE_LIVE_KEY",
];

interface RegisterMcpModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaveServer: (serverData: any) => Promise<void>;
}

export function RegisterMcpModal({
  isOpen,
  onClose,
  onSaveServer,
}: RegisterMcpModalProps) {
  const [name, setName] = useState("");
  const [endpointUrl, setEndpointUrl] = useState("");
  const [transport, setTransport] = useState("Streamable HTTP");
  const [auth, setAuth] = useState<"No credential" | "Bearer token" | "API Key">(
    "No credential"
  );
  const [secretName, setSecretName] = useState(AVAILABLE_SECRETS[0]);
  const [docs, setDocs] = useState("");

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSelectSuggested = (server: SuggestedServer) => {
    setName(server.name.toLowerCase().replace(/[^a-z0-9]/g, "-"));
    setEndpointUrl(server.defaultUrl);
    setAuth(server.authDefault);
    setDiscoveryError(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !endpointUrl.trim()) return;

    setIsDiscovering(true);
    setDiscoveryError(null);

    try {
      const serverPayload = {
        name: name.trim(),
        endpointUrl: endpointUrl.trim(),
      };
      await onSaveServer(serverPayload);
      onClose();
    } catch (error) {
      setDiscoveryError(error instanceof Error ? error.message : "Gagal mendaftarkan MCP server.");
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-3xl w-full my-8 max-h-[90vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-blue-600" />
              <h3 className="text-base font-bold text-slate-900 tracking-tight">
                Register MCP server
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-1 max-w-xl leading-relaxed">
              On save the daemon runs a discovery pass — you get the tool list back immediately. The registry is the allowlist.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
          {/* Section: Suggested servers */}
          <div>
            <h4 className="text-xs font-bold text-slate-800 mb-2">
              Suggested servers
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-52 overflow-y-auto pr-1">
              {SUGGESTED_SERVERS.map((server) => (
                <button
                  key={server.name}
                  type="button"
                  onClick={() => handleSelectSuggested(server)}
                  className="text-left p-3 rounded-xl border border-slate-200 hover:border-blue-400 hover:bg-blue-50/30 transition-all group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                        {server.name}
                      </span>
                      {server.badge && (
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded font-mono font-medium ${
                            server.badge === "no key"
                              ? "bg-slate-100 text-slate-600"
                              : "bg-amber-50 text-amber-700 border border-amber-200/60"
                          }`}
                        >
                          {server.badge}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 leading-relaxed line-clamp-2">
                      {server.description}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Form Fields */}
          <form id="mcp-register-form" onSubmit={handleSave} className="space-y-4 pt-3 border-t border-slate-100">
            {/* Field: Name */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="hospital-mcp"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs font-mono"
                required
              />
              <p className="text-[11px] text-slate-400 mt-0.5">
                Wajib dan unik (digunakan sebagai ID server, tanpa spasi).
              </p>
            </div>

            {/* Field: Endpoint URL */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Endpoint URL <span className="text-rose-500">*</span>
              </label>
              <input
                type="url"
                value={endpointUrl}
                onChange={(e) => setEndpointUrl(e.target.value)}
                placeholder="https://host.example/mcp"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 font-mono text-slate-800 text-xs"
                required
              />
            </div>

            {/* Field: Transport */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Transport
              </label>
              <div className="relative">
                <select
                  value={transport}
                  onChange={(e) => setTransport(e.target.value)}
                  className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs"
                >
                  <option value="Streamable HTTP">Streamable HTTP (Direkomendasikan untuk MVP)</option>
                  <option value="SSE" disabled>SSE (Fase berikutnya)</option>
                  <option value="stdio" disabled>stdio (Berisiko keamanan)</option>
                </select>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Di MVP cukup Streamable HTTP untuk keamanan dan stabilitas service.
              </p>
            </div>

            {/* Field: Auth & Secret Name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-800 mb-1">
                  Auth
                </label>
                <div className="relative">
                  <select
                    value={auth}
                    onChange={(e) =>
                      setAuth(e.target.value as "No credential" | "Bearer token" | "API Key")
                    }
                    className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs"
                  >
                    <option value="No credential">No credential</option>
                    <option value="Bearer token">Bearer token</option>
                    <option value="API Key">API Key</option>
                  </select>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                </div>
              </div>

              {auth !== "No credential" && (
                <div>
                  <label className="block font-semibold text-slate-800 mb-1">
                    Secret Name
                  </label>
                  <div className="relative">
                    <select
                      value={secretName}
                      onChange={(e) => setSecretName(e.target.value)}
                      className="w-full appearance-none px-3.5 py-2 rounded-xl border border-slate-200 bg-white focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs font-mono"
                    >
                      {AVAILABLE_SECRETS.map((sec) => (
                        <option key={sec} value={sec}>
                          {sec}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Nilai rahasia tersimpan aman di server Admin.
                  </p>
                </div>
              )}
            </div>

            {/* Field: Docs */}
            <div>
              <label className="block font-semibold text-slate-800 mb-1">
                Docs (markdown, optional)
              </label>
              <textarea
                rows={2}
                value={docs}
                onChange={(e) => setDocs(e.target.value)}
                placeholder="What this server does, what its tools expect…"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 focus:outline-hidden focus:border-blue-500 focus:ring-2 focus:ring-blue-100 text-slate-800 text-xs resize-y"
              />
            </div>

            {/* Discovery Error Alert */}
            {discoveryError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 flex items-start gap-2 text-rose-700">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{discoveryError}</span>
              </div>
            )}
          </form>
        </div>

        {/* Modal Footer */}
        <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between shrink-0">
          <div className="text-[11px] text-slate-500">
            {isDiscovering && (
              <span className="inline-flex items-center gap-1.5 text-blue-600 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Menjalankan discovery pass (tools/list)...
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isDiscovering}
              className="px-4 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 text-xs font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="mcp-register-form"
              disabled={isDiscovering || !name.trim() || !endpointUrl.trim()}
              className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-semibold transition-colors shadow-2xs inline-flex items-center gap-1.5"
            >
              {isDiscovering ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Discovering...</span>
                </>
              ) : (
                <span>Register</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
