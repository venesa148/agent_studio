"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/navigation/Sidebar";
import { ConfigureNav, ConfigureTab } from "@/components/navigation/ConfigureNav";
import { BuildAgentChatPane } from "@/features/builder/BuildAgentChatPane";
import { TestAgentPane } from "@/features/chat/TestAgentPane";

export interface AgentSpecData {
  id: string;
  name: string;
  description?: string;
  instructions?: string;
  model: string;
  tools: string[];
  mcp_servers: string[];
  harness: string;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export default function HomePage() {
  const [activeConfigureTab, setActiveConfigureTab] = useState<ConfigureTab>("ghostwriter");
  const [agents, setAgents] = useState<AgentSpecData[]>([]);
  const [activeAgent, setActiveAgent] = useState<AgentSpecData | null>(null);
  const [isLoadingAgents, setIsLoadingAgents] = useState(true);

  const fetchAgents = async () => {
    try {
      setIsLoadingAgents(true);
      const res = await fetch("http://localhost:8000/api/v1/agent");
      if (res.ok) {
        const data: AgentSpecData[] = await res.json();
        setAgents(data);
        if (data.length > 0) {
          setActiveAgent((prev) => {
            if (prev) {
              const updated = data.find((a) => a.id === prev.id);
              if (updated) return updated;
            }
            return data[0];
          });
        }
      }
    } catch (err) {
      console.warn("Failed to fetch agents:", err);
    } finally {
      setIsLoadingAgents(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleAgentCreatedOrUpdated = (agent: AgentSpecData) => {
    setAgents((prev) => {
      const idx = prev.findIndex((a) => a.id === agent.id);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = agent;
        return copy;
      }
      return [agent, ...prev];
    });
    setActiveAgent(agent);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#fafbfe]">
      {/* 1. Fixed Sidebar (Persisten di setiap halaman) */}
      <Sidebar />

      {/* 2. Sub-panel Konfigurasi / Navigasi Build */}
      <ConfigureNav
        activeTab={activeConfigureTab}
        onSelectTab={(tab) => setActiveConfigureTab(tab)}
      />

      {/* 3. Pane Chat Build Agent (Tengah) */}
      <BuildAgentChatPane
        activeAgent={activeAgent}
        onAgentCreated={handleAgentCreatedOrUpdated}
      />

      {/* 4. Pane Chat Test Agent (Kanan) */}
      <TestAgentPane
        activeAgent={activeAgent}
        agents={agents}
        onSelectAgent={(agent) => setActiveAgent(agent)}
        isLoadingAgents={isLoadingAgents}
      />
    </div>
  );
}
