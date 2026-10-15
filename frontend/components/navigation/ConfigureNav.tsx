"use client";

import React from "react";
import {
  ArrowLeft,
  MessageSquareCode,
  BookOpen,
  Smartphone,
  Wrench,
  ShieldCheck,
  AtSign,
  SlidersHorizontal,
} from "lucide-react";
import { AgentSpecData } from "@/app/page";

export type ConfigureTab =
  | "ghostwriter"
  | "journeys"
  | "knowledge"
  | "tools"
  | "guardrails"
  | "model"
  | "limits";

interface ConfigureNavProps {
  activeTab?: ConfigureTab;
  onSelectTab?: (tab: ConfigureTab) => void;
  onBack?: () => void;
  activeAgent?: AgentSpecData | null;
}

export function ConfigureNav({
  activeTab = "ghostwriter",
  onSelectTab,
  onBack,
  activeAgent,
}: ConfigureNavProps) {
  // Hitung jumlah dinamis berdasarkan activeAgent saat ini
  const toolsCount = activeAgent?.tools ? activeAgent.tools.length : 0;
  const knowledgeCount = activeAgent?.knowledge_sources ? activeAgent.knowledge_sources.length : ((activeAgent as any)?.knowledge?.length || 0);
  const journeysCount = (activeAgent as any)?.tests?.length || 0;
  
  // Guardrails dinamis dari DB
  const guardrailsConfig = activeAgent?.guardrails || null;
  const guardrailsCount = guardrailsConfig
    ? [
        guardrailsConfig.topic_block,
        guardrailsConfig.pii_mask,
        guardrailsConfig.mutation_confirm,
        guardrailsConfig.human_handoff,
      ].filter(Boolean).length
    : 0;

  // Model & Limits dinamis dari DB
  const modelShortName = activeAgent?.model
    ? activeAgent.model.includes("/")
      ? activeAgent.model.split("/")[1]
      : activeAgent.model
    : "GLM 5.3";

  const maxCallsValue = activeAgent?.guardrails?.max_calls || 5;
  const limitsBadgeText = `${maxCallsValue} Calls`;

  const items: {
    id: ConfigureTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    count?: number;
    badgeText?: string;
  }[] = [
    {
      id: "ghostwriter",
      label: "Ghostwriter",
      icon: MessageSquareCode,
    },
    {
      id: "journeys",
      label: "Journeys",
      icon: BookOpen,
      count: journeysCount,
    },
    {
      id: "knowledge",
      label: "Knowledge",
      icon: Smartphone,
      count: knowledgeCount,
    },
    {
      id: "tools",
      label: "Tools",
      icon: Wrench,
      count: toolsCount,
    },
    {
      id: "guardrails",
      label: "Guardrails",
      icon: ShieldCheck,
      count: guardrailsCount,
    },
    {
      id: "model",
      label: "Model",
      icon: AtSign,
      badgeText: modelShortName,
    },
    {
      id: "limits",
      label: "Limits",
      icon: SlidersHorizontal,
      badgeText: limitsBadgeText,
    },
  ];

  return (
    <div className="w-[200px] shrink-0 border-r border-slate-200/80 bg-white flex flex-col h-full select-none transition-all">
      {/* Top Header */}
      <div className="p-4 border-b border-slate-100">
        <button
          type="button"
          onClick={onBack}
          className="text-slate-400 hover:text-slate-800 transition-colors mb-2 inline-flex items-center gap-1 text-xs cursor-pointer group"
          title="Kembali ke semua agen / sesi baru"
        >
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          <span className="text-[10px] font-medium text-slate-500">Kembali</span>
        </button>

        <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
          BUILD
        </div>
        <h2 className="text-base font-bold text-slate-900 tracking-tight">
          Configure
        </h2>

        {/* Dynamic Active Agent context indicator */}
        <div className="mt-1.5 flex items-center gap-1.5 overflow-hidden">
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              activeAgent?.id && activeAgent.status !== "draft"
                ? "bg-emerald-500"
                : "bg-blue-500 animate-pulse"
            }`}
          />
          <span
            className="text-[11px] font-semibold text-slate-700 truncate"
            title={activeAgent?.name || "Agent Baru (Draf)"}
          >
            {activeAgent?.name || "Agent Baru"}
          </span>
          <span
            className={`text-[9px] px-1.5 py-0.2 rounded-full font-bold uppercase shrink-0 ${
              activeAgent?.id && activeAgent.status !== "draft"
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-blue-50 text-blue-700 border border-blue-200"
            }`}
          >
            {activeAgent?.id && activeAgent.status !== "draft" ? "DB" : "Draf"}
          </span>
        </div>
      </div>

      {/* Nav list */}
      <div className="p-2 space-y-1 overflow-y-auto flex-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectTab?.(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                isActive
                  ? "border border-blue-500 bg-blue-50/50 text-blue-700 font-semibold shadow-2xs"
                  : "border border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <Icon
                  className={`w-3.5 h-3.5 shrink-0 ${
                    isActive ? "text-blue-600" : "text-slate-400"
                  }`}
                />
                <span className="truncate">{item.label}</span>
              </div>

              {item.count !== undefined ? (
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full font-semibold transition-all ${
                    isActive
                      ? "bg-blue-200/70 text-blue-800"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {item.count}
                </span>
              ) : item.badgeText ? (
                <span
                  className={`text-[9px] px-1.5 py-0.2 rounded-md font-semibold truncate max-w-[55px] ${
                    isActive
                      ? "bg-blue-200/70 text-blue-800"
                      : "bg-slate-100 text-slate-500"
                  }`}
                  title={item.badgeText}
                >
                  {item.badgeText}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
