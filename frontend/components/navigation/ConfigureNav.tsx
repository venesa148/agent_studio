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
}

export function ConfigureNav({
  activeTab = "ghostwriter",
  onSelectTab,
  onBack,
}: ConfigureNavProps) {
  const items: {
    id: ConfigureTab;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    count?: number;
  }[] = [
    { id: "ghostwriter", label: "Ghostwriter", icon: MessageSquareCode },
    { id: "journeys", label: "Journeys", icon: BookOpen },
    { id: "knowledge", label: "Knowledge", icon: Smartphone, count: 3 },
    { id: "tools", label: "Tools", icon: Wrench, count: 4 },
    { id: "guardrails", label: "Guardrails", icon: ShieldCheck },
    { id: "model", label: "Model", icon: AtSign },
    { id: "limits", label: "Limits", icon: SlidersHorizontal },
  ];

  return (
    <div className="w-[190px] shrink-0 border-r border-slate-200/80 bg-white flex flex-col h-full select-none">
      {/* Top Header */}
      <div className="p-4 border-b border-slate-100">
        <button
          onClick={onBack}
          className="text-slate-400 hover:text-slate-700 transition-colors mb-2 inline-flex items-center gap-1 text-xs"
          title="Back to agents list"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
        </button>
        <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">
          BUILD
        </div>
        <h2 className="text-base font-bold text-slate-900 tracking-tight">
          Configure
        </h2>
      </div>

      {/* Nav list */}
      <div className="p-2 space-y-1 overflow-y-auto flex-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSelectTab?.(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all ${
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

              {item.count !== undefined && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full font-semibold bg-slate-100 text-slate-600">
                  {item.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
