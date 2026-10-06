"use client";

import React, { useState } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import { ConfigureNav, ConfigureTab } from "@/components/navigation/ConfigureNav";
import { BuildAgentChatPane } from "@/features/builder/BuildAgentChatPane";
import { TestAgentPane } from "@/features/chat/TestAgentPane";

export default function HomePage() {
  const [activeConfigureTab, setActiveConfigureTab] = useState<ConfigureTab>("ghostwriter");
  const [createdAgent, setCreatedAgent] = useState<{
    name: string;
    description: string;
  } | null>(null);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar (Persisten di setiap halaman) */}
      <Sidebar />

      {/* 2. Sub-panel Konfigurasi / Navigasi Build (Ghostwriter, Tools, Guardrails, dll) */}
      <ConfigureNav
        activeTab={activeConfigureTab}
        onSelectTab={(tab) => setActiveConfigureTab(tab)}
      />

      {/* 3. Pane Chat Build Agent (Tengah) */}
      <BuildAgentChatPane
        onAgentCreated={(spec) => {
          setCreatedAgent(spec);
        }}
      />

      {/* 4. Pane Chat Test Agent dengan multiple tabs: Chat, Simulation, dan Trace (Kanan) */}
      <TestAgentPane
        agentName={createdAgent?.name || "BPJS Customer Service Agent"}
      />
    </div>
  );
}
