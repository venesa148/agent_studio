export interface Agent {
  id: string;
  slug?: string;
  name: string;
  description: string;
  instructions: string;
  model: string;
  harness_id?: string;
  status: "draft" | "published" | "active";
  version?: string;
  created_at?: string;
  updated_at?: string;
  deployment?: string;
}

export interface Tool {
  id: string;
  name: string;
  description?: string;
  source: string; // BUILTIN | MCP | OPENAPI | BUILTIN_HTTP
  source_id?: string | null;
  auth?: string;
  health?: "ok" | "error" | "unknown";
  used_by?: string;
  input_schema?: Record<string, any>;
  config?: Record<string, any>;
  enabled?: boolean;
}

export interface McpServer {
  id: string;
  name: string;
  endpoint_url: string;
  transport: string;
  auth_type: string;
  secret_name?: string | null;
  tools_count?: number;
  status?: string;
  last_synced?: string;
  docs?: string;
}
