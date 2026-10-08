import { Agent, Tool, McpServer } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API Error ${res.status}: ${errorBody || res.statusText}`);
  }

  return res.json();
}

// ==================== AGENTS ====================

export async function getAgentsApi(): Promise<Agent[]> {
  try {
    return await fetchJson<Agent[]>("/agents");
  } catch (err) {
    console.warn("Backend offline or error on getAgentsApi:", err);
    return [];
  }
}

export async function createAgentApi(agent: Partial<Agent>): Promise<Agent> {
  return await fetchJson<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(agent),
  });
}

export async function deleteAgentApi(id: string): Promise<{ success: boolean }> {
  return await fetchJson<{ success: boolean }>(`/agents/${id}`, {
    method: "DELETE",
  });
}

// ==================== REGISTRY (TOOLS & MCP) ====================

export interface RegistryResponse {
  tools: Tool[];
  mcp_servers: McpServer[];
}

export async function getRegistryApi(): Promise<RegistryResponse> {
  try {
    return await fetchJson<RegistryResponse>("/registry");
  } catch (err) {
    console.warn("Backend offline or error on getRegistryApi:", err);
    return { tools: [], mcp_servers: [] };
  }
}

export async function createMcpServerApi(data: Partial<McpServer>): Promise<McpServer> {
  return await fetchJson<McpServer>("/registry/mcp", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function createToolApi(data: Partial<Tool>): Promise<Tool> {
  return await fetchJson<Tool>("/registry/tools", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
