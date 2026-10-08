/**
 * Draft Store - Local persistence and event emitter for uncommitted agent drafts.
 * Memungkinkan draf agent yang sedang dirancang oleh builder tetap tersimpan
 * dan dapat dibuka kembali meskipun pengguna keluar/pindah halaman.
 */

export interface AgentDraft {
  id: string; // ID unik draf, misal: draft_1728400000000
  name: string;
  description?: string;
  instructions?: string;
  model: string;
  tools: string[];
  mcp_servers: string[];
  harness: string;
  status: "draft";
  messages: any[]; // Seluruh riwayat percakapan dengan builder
  created_at: string;
  updated_at: string;
}

const STORAGE_KEY = "agent_studio_drafts_v1";
const DRAFT_EVENT_NAME = "agent_studio_drafts_updated";

export function getDrafts(): AgentDraft[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.warn("Gagal membaca drafts dari localStorage:", e);
    return [];
  }
}

export function getDraftById(id: string): AgentDraft | null {
  if (!id) return null;
  const drafts = getDrafts();
  return drafts.find((d) => d.id === id) || null;
}

export function saveDraft(draft: Partial<AgentDraft> & { id: string; name: string }): AgentDraft {
  if (typeof window === "undefined") return draft as AgentDraft;
  const drafts = getDrafts();
  const now = new Date().toISOString();

  const existingIdx = drafts.findIndex((d) => d.id === draft.id);
  let updatedDraft: AgentDraft;

  if (existingIdx >= 0) {
    updatedDraft = {
      ...drafts[existingIdx],
      ...draft,
      status: "draft",
      updated_at: now,
    };
    drafts[existingIdx] = updatedDraft;
  } else {
    updatedDraft = {
      id: draft.id,
      name: draft.name || "Draf Agen Baru",
      description: draft.description || "",
      instructions: draft.instructions || "",
      model: draft.model || "z-ai/glm-5.3",
      tools: draft.tools || [],
      mcp_servers: draft.mcp_servers || [],
      harness: draft.harness || "default-safe-v1",
      status: "draft",
      messages: draft.messages || [],
      created_at: draft.created_at || now,
      updated_at: now,
    };
    drafts.unshift(updatedDraft);
  }

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
    window.dispatchEvent(new CustomEvent(DRAFT_EVENT_NAME, { detail: drafts }));
  } catch (e) {
    console.warn("Gagal menyimpan draft ke localStorage:", e);
  }

  return updatedDraft;
}

export function deleteDraft(id: string): void {
  if (typeof window === "undefined" || !id) return;
  const drafts = getDrafts().filter((d) => d.id !== id);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drafts));
    window.dispatchEvent(new CustomEvent(DRAFT_EVENT_NAME, { detail: drafts }));
  } catch (e) {
    console.warn("Gagal menghapus draft:", e);
  }
}

export function subscribeToDrafts(callback: (drafts: AgentDraft[]) => void): () => void {
  if (typeof window === "undefined") return () => {};

  const handleUpdate = () => {
    callback(getDrafts());
  };

  window.addEventListener(DRAFT_EVENT_NAME, handleUpdate);
  window.addEventListener("storage", handleUpdate);

  return () => {
    window.removeEventListener(DRAFT_EVENT_NAME, handleUpdate);
    window.removeEventListener("storage", handleUpdate);
  };
}
