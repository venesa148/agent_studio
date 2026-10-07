"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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

  const searchParams = useSearchParams();
  const agentId = searchParams ? searchParams.get("id") : null;
  const isNewQuery = searchParams ? searchParams.get("new") === "true" : false;

  const fetchAgents = async () => {
    try {
      setIsLoadingAgents(true);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/v1/agent`);
      if (res.ok) {
        const data: AgentSpecData[] = await res.json();
        setAgents(data);
        return data;
      }
    } catch (err) {
      console.warn("Failed to fetch agents:", err);
    } finally {
      setIsLoadingAgents(false);
    }
    return [];
  };

  useEffect(() => {
    fetchAgents().then((data) => {
      if (agentId && data.length > 0) {
        const found = data.find(a => a.id === agentId);
        setActiveAgent(found || null);
      } else {
        setActiveAgent(null);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Listen to URL changes for agent selection or 'new' explicitly
  useEffect(() => {
    if (isNewQuery) {
      setActiveAgent(null);
      if (typeof window !== "undefined") {
        window.history.replaceState({}, '', '/');
      }
    } else if (agentId) {
      if (agents.length > 0) {
        const found = agents.find(a => a.id === agentId);
        setActiveAgent(found || null);
      }
    } else {
      setActiveAgent(null);
    }
  }, [agentId, isNewQuery, agents]);

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
    if (typeof window !== "undefined") {
      window.history.pushState({}, '', `/?id=${agent.id}`);
    }
  };

  const handleClearActiveAgent = () => {
    setActiveAgent(null);
    if (typeof window !== "undefined") {
      window.history.pushState({}, '', '/');
    }
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
        onClearActiveAgent={handleClearActiveAgent}
      />

      {/* 4. Pane Chat Test Agent (Kanan) */}
      <TestAgentPane
        activeAgent={activeAgent}
        agents={agents}
        onSelectAgent={(agent) => {
          setActiveAgent(agent);
          if (typeof window !== "undefined") {
            window.history.pushState({}, '', `/?id=${agent.id}`);
          }
        }}
        isLoadingAgents={isLoadingAgents}
      />
    </div>
  );
}
