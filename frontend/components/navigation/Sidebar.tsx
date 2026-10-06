"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ChevronsLeft,
  ChevronsRight,
  Plus,
  Bot,
  GitBranch,
  Wrench,
  Rocket,
  CheckCircle2,
  Settings,
  HelpCircle,
  Sparkles,
} from "lucide-react";

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function Sidebar({ collapsed = false, onToggleCollapse }: SidebarProps) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(collapsed);
  const [showWorkflowToast, setShowWorkflowToast] = useState(false);

  const handleToggle = () => {
    setIsCollapsed(!isCollapsed);
    onToggleCollapse?.();
  };

  const navItems = [
    {
      name: "Agents",
      href: "/agents",
      icon: Bot,
      count: 6,
      active: pathname === "/agents" || pathname === "/",
    },
    {
      name: "Workflows",
      href: "#",
      icon: GitBranch,
      count: 6,
      isTestOnly: true,
      active: false,
    },
    {
      name: "Tools",
      href: "/registry",
      icon: Wrench,
      count: 8,
      active: pathname === "/registry",
    },
    {
      name: "Deployments",
      href: "/deployments",
      icon: Rocket,
      count: 4,
      active: pathname === "/deployments",
    },
    {
      name: "Evaluations & Tests",
      href: "/evaluation",
      icon: CheckCircle2,
      count: null,
      active: pathname === "/evaluation",
    },
  ];

  const recentAgents: { name: string; tag?: string; isDot?: boolean }[] = [];

  return (
    <aside
      className={`relative flex flex-col h-screen border-r border-slate-200/90 bg-[#fafbfe] transition-all duration-200 select-none ${isCollapsed ? "w-[68px]" : "w-[260px]"
        }`}
    >
      {/* Header: Logo & Collapse Button */}
      <div className="flex items-center justify-between px-4 h-14 border-b border-slate-200/80">
        {!isCollapsed && (
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-xs">
              <Sparkles className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold tracking-wider text-slate-800 uppercase">
              Agent Studio
            </span>
          </div>
        )}

        <button
          onClick={handleToggle}
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors mx-auto"
        >
          {isCollapsed ? (
            <ChevronsRight className="w-4 h-4" />
          ) : (
            <ChevronsLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Primary Action: New Agent Button */}
      <div className="p-3">
        <Link
          href="/?new=true"
          className={`flex items-center justify-center gap-2 w-full py-2 px-3 rounded-full border border-blue-200 bg-white hover:bg-blue-50/70 text-blue-600 font-medium text-sm transition-all shadow-2xs hover:shadow-xs group`}
        >
          <Plus className="w-4 h-4 text-blue-600 group-hover:rotate-90 transition-transform duration-200" />
          {!isCollapsed && <span>New Agent</span>}
        </Link>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={(e) => {
                  if ((item as any).isTestOnly) {
                    e.preventDefault();
                    setShowWorkflowToast(true);
                    setTimeout(() => setShowWorkflowToast(false), 2500);
                  }
                }}
                className={`flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-colors ${item.active
                  ? "bg-blue-50/80 text-blue-700 font-semibold"
                  : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900"
                  }`}
                title={isCollapsed ? item.name : undefined}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${item.active ? "text-blue-600" : "text-slate-500"
                      }`}
                  />
                  {!isCollapsed && <span className="truncate">{item.name}</span>}
                </div>
                {!isCollapsed && item.count !== null && (
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${item.active
                      ? "bg-blue-600 text-white"
                      : "bg-slate-200/70 text-slate-700"
                      }`}
                  >
                    {item.count}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Section: RECENT AGENTS */}
        {!isCollapsed && (
          <div className="pt-5 pb-2">
            <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-slate-400 uppercase">
              Recent Agents
            </div>
            {recentAgents.length > 0 ? (
              <div className="space-y-0.5">
                {recentAgents.map((agent) => (
                  <button
                    key={agent.name}
                    className="flex items-center justify-between w-full px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors text-left group"
                  >
                    <div className="flex items-center gap-2 truncate">
                      {agent.isDot ? (
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
                      )}
                      <span className="truncate text-slate-700 group-hover:text-slate-900">
                        {agent.name}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="px-3 py-1 text-[11px] text-slate-400">
                Belum ada agent terbaru
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Profile / Workspace */}
      <div className="p-3 border-t border-slate-200/80 bg-white/50">
        {!isCollapsed ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-sky-500 to-blue-600 flex items-center justify-center text-white text-xs font-bold">
                AS
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-slate-800 leading-tight">
                  Studio Workspace
                </span>
              </div>
            </div>
            <button
              title="Settings"
              className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            >
              <Settings className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
              AS
            </div>
          </div>
        )}
      </div>

      {/* Toast Feedback for Workflow testing */}
      {showWorkflowToast && (
        <div className="absolute bottom-16 left-3 right-3 p-2.5 rounded-xl bg-slate-900 text-white text-[11px] shadow-lg flex items-center justify-between z-50 animate-in fade-in duration-200">
          <span>Workflow: Mode Test (Fase 4)</span>
          <span className="text-[10px] text-blue-400 font-medium">Tetap di halaman</span>
        </div>
      )}
    </aside>
  );
}
