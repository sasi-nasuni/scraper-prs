import type {
  AgentConfig,
  AgentConfigWithMeta,
  ConfluenceTestRequest,
  ConfluenceTestResponse,
  GenerateRequest,
  GitHubPRCommentsRequest,
  GitHubPRCommentsResponse,
  GitHubPRCommitsRequest,
  GitHubPRCommitsResponse,
  HealthResponse,
  JobCreatedResponse,
  JobListResponse,
  JobStatusResponse,
  MCPServersResponse,
  MCPToolCallRequest,
  MCPToolCallResponse,
  MCPToolsResponse,
  PipelineCreateRequest,
  PipelineSessionResponse,
  PipelineSSEEvent,
} from "@/types/api";

const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(
      body?.detail ?? body?.error ?? `Request failed: ${res.status}`
    );
  }

  return res.json() as Promise<T>;
}

// ── Endpoints ──────────────────────────────────────────────────────────────

export const api = {
  health: () => request<HealthResponse>("/health"),

  createJob: (data: GenerateRequest) =>
    request<JobCreatedResponse>("/jobs", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getJob: (jobId: string) =>
    request<JobStatusResponse>(`/jobs/${jobId}`),

  listJobs: (status?: string, limit = 20, offset = 0) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    return request<JobListResponse>(`/jobs?${params}`);
  },

  cancelJob: (jobId: string) =>
    request<JobStatusResponse>(`/jobs/${jobId}/cancel`, { method: "POST" }),

  // ── MCP Tool Testing ──────────────────────────────────────────────────

  listMCPServers: () =>
    request<MCPServersResponse>("/mcp/servers"),

  listServerTools: (server: string, q?: string) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    const qs = params.toString();
    return request<MCPToolsResponse>(
      `/mcp/servers/${server}/tools${qs ? `?${qs}` : ""}`
    );
  },

  callTool: (data: MCPToolCallRequest) =>
    request<MCPToolCallResponse>("/mcp/tools/call", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // ── GitHub Direct API ─────────────────────────────────────────────────

  fetchPRComments: (data: GitHubPRCommentsRequest) =>
    request<GitHubPRCommentsResponse>("/github/pr-comments", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  fetchPRCommits: (data: GitHubPRCommitsRequest) =>
    request<GitHubPRCommitsResponse>("/github/pr-commits", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // ── Agent Config ──────────────────────────────────────────────────────────

  getConfig: () => request<AgentConfigWithMeta>("/config"),

  updateConfig: (data: Partial<AgentConfig>) =>
    request<AgentConfigWithMeta>("/config", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // ── Confluence Test ───────────────────────────────────────────────────

  testConfluenceSearch: (data: ConfluenceTestRequest) =>
    request<ConfluenceTestResponse>("/confluence/test-search", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // ── Pipeline Step Execution ───────────────────────────────────────────

  createPipelineSession: (data: PipelineCreateRequest) =>
    request<PipelineSessionResponse>("/pipeline/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getPipelineSession: (sessionId: string) =>
    request<PipelineSessionResponse>(`/pipeline/sessions/${sessionId}`),

  deletePipelineSession: (sessionId: string) =>
    request<void>(`/pipeline/sessions/${sessionId}`, { method: "DELETE" }),
};

// ── WebSocket helper ───────────────────────────────────────────────────────

// In dev, connect WebSocket directly to the backend to avoid Vite proxy EPIPE
// issues. In production, use the same host as the page.
const WS_BASE = import.meta.env.DEV
  ? "ws://127.0.0.1:8001"
  : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//` +
    window.location.host;

export function connectJobLogs(
  jobId: string,
  onMessage: (data: string | Record<string, unknown>) => void,
  onClose?: () => void
): WebSocket {
  const ws = new WebSocket(
    `${WS_BASE}/api/ws/jobs/${jobId}/logs`
  );

  ws.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      onMessage(parsed);
    } catch {
      onMessage(event.data as string);
    }
  };

  ws.onclose = () => onClose?.();

  ws.onerror = () => {
    // Only attempt close if the socket isn't already closed/closing
    if (ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  };

  return ws;
}

// ── Pipeline SSE stream helper ─────────────────────────────────────────────

/**
 * Execute pipeline nodes via SSE streaming.
 * Calls `onEvent` for each SSE event; resolves when the stream ends.
 */
export async function executePipelineSSE(
  sessionId: string,
  targetNode: string | null,
  onEvent: (event: PipelineSSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${BASE}/pipeline/sessions/${sessionId}/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_node: targetNode }),
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Execute failed: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse complete SSE events (separated by \n\n)
    while (true) {
      const boundary = buffer.indexOf("\n\n");
      if (boundary === -1) break;

      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as PipelineSSEEvent);
          } catch {
            // skip malformed events
          }
        }
      }
    }
  }
}

// ── Pipeline retry SSE stream helper ─────────────────────────────────────

/**
 * Retry a single pipeline node via SSE streaming.
 * Same event shape as executePipelineSSE.
 */
export async function retryPipelineNodeSSE(
  sessionId: string,
  nodeName: string,
  onEvent: (event: PipelineSSEEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(
    `${BASE}/pipeline/sessions/${sessionId}/retry/${nodeName}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
    }
  );

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Retry failed: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    while (true) {
      const boundary = buffer.indexOf("\n\n");
      if (boundary === -1) break;

      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as PipelineSSEEvent);
          } catch {
            // skip malformed events
          }
        }
      }
    }
  }
}
