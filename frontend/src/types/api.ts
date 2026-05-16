// ── API Types ────────────────────────────────────────────────────────────────
// These mirror the FastAPI Pydantic models in src/api/models.py

export type PRSelectionMode = "latest" | "label" | "pr_number";

export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface GenerateRequest {
  repo_url: string;
  mode: PRSelectionMode;
  pr_number?: number | null;
  label?: string | null;
  max_prs: number;
  output_dir?: string | null;
  verbose: boolean;
}

export interface JobCreatedResponse {
  job_id: string;
  status: JobStatus;
  message: string;
  created_at: string;
}

export interface PRSummaryResult {
  pr_number: number;
  title?: string | null;
  summary_file?: string | null;
  status: string;
  error?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  current_step?: string | null;
  repo_url: string;
  mode: PRSelectionMode;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  results: PRSummaryResult[];
  errors: Array<Record<string, unknown>>;
  warnings: string[];
  total_prs: number;
  processed_prs: number;
  logs: string[];
}

export interface JobListResponse {
  jobs: JobStatusResponse[];
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
}

// ── MCP Tool Testing Types ─────────────────────────────────────────────────

export interface MCPToolInfo {
  name: string;
  description?: string | null;
  input_schema?: Record<string, unknown> | null;
}

export interface MCPServerStatus {
  name: string;
  connected: boolean;
  tool_count: number;
  description?: string | null;
}

export interface MCPServersResponse {
  servers: MCPServerStatus[];
}

export interface MCPToolsResponse {
  server: string;
  tools: MCPToolInfo[];
  total: number;
}

export interface MCPToolCallRequest {
  server: string;
  tool: string;
  arguments: Record<string, unknown>;
}

export interface MCPToolCallResponse {
  server: string;
  tool: string;
  success: boolean;
  result?: unknown;
  error?: string | null;
  duration_ms?: number | null;
}

// ── GitHub Direct API Types ────────────────────────────────────────────────

export type CommentType = "review" | "issue" | "all";

export interface GitHubPRCommentsRequest {
  owner: string;
  repo: string;
  pull_number: number;
  comment_type?: CommentType;
  page?: number | null;
  per_page?: number;
}

export interface GitHubPRCommentsResponse {
  owner: string;
  repo: string;
  pull_number: number;
  comment_type: string;
  comments: Record<string, unknown>[];
  total_count: number;
  page?: number | null;
  per_page: number;
  total_pages_fetched?: number | null;
  duration_ms: number;
}

// ── GitHub PR Commits Types ────────────────────────────────────────────────

export interface GitHubPRCommitsRequest {
  owner: string;
  repo: string;
  pull_number: number;
  page?: number | null;
  per_page?: number;
}

export interface GitHubPRCommitsResponse {
  owner: string;
  repo: string;
  pull_number: number;
  commits: Record<string, unknown>[];
  total_count: number;
  page?: number | null;
  per_page: number;
  total_pages_fetched?: number | null;
  duration_ms: number;
}

// ── Agent Config Types ─────────────────────────────────────────────────────

export interface LLMConfig {
  provider: string;
  model: string;
  temperature: number;
  max_tokens: number;
  streaming: boolean;
  base_url?: string | null;
}

export interface ProcessingConfig {
  max_prs: number;
  enable_parallel: boolean;
  parallel_workers: number;
  timeout_per_pr: number;
}

export interface TemplatesConfig {
  main_template: string;
  fallback_template: string;
  use_fallback_when_missing: boolean;
}

export interface JiraExtractionConfig {
  pattern: string;
  search_in: string[];
}

export interface FigmaExtractionConfig {
  patterns: string[];
  search_in: string[];
}

export interface ConfluenceExtractionConfig {
  strategies: string[];
  max_pages_per_pr: number;
}

export interface ExtractionConfig {
  jira: JiraExtractionConfig;
  figma: FigmaExtractionConfig;
  confluence: ConfluenceExtractionConfig;
}

export interface RetryConfig {
  max_attempts: number;
  initial_delay: number;
  max_delay: number;
  exponential_base: number;
}

export interface ErrorHandlingConfig {
  continue_on_error: boolean;
  generate_partial_summaries: boolean;
  log_errors: boolean;
  include_errors_in_summary: boolean;
}

export interface OutputConfig {
  directory: string;
  filename_pattern: string;
  overwrite_existing: boolean;
  include_metadata: boolean;
}

export interface LoggingConfig {
  level: string;
  format: string;
  console: boolean;
  file: boolean;
  file_path: string;
  max_bytes: number;
  backup_count: number;
}

export interface RateLimitEntry {
  requests_per_hour?: number | null;
  requests_per_minute?: number | null;
  min_delay_between_requests: number;
}

export interface RateLimitsConfig {
  github: RateLimitEntry;
  jira: RateLimitEntry;
  confluence: RateLimitEntry;
}

export interface AgentConfig {
  llm: LLMConfig;
  processing: ProcessingConfig;
  templates: TemplatesConfig;
  extraction: ExtractionConfig;
  retry: RetryConfig;
  error_handling: ErrorHandlingConfig;
  output: OutputConfig;
  logging: LoggingConfig;
  rate_limits: RateLimitsConfig;
  file_categories?: Record<string, string[]> | null;
}

export interface ConfigPriorityInfo {
  key: string;
  env_var: string;
  env_value?: string | null;
  yaml_value?: unknown;
  active_source: "yaml" | "env" | "cli";
}

export interface AgentConfigWithMeta {
  config: AgentConfig;
  overrides: ConfigPriorityInfo[];
}

// ── Confluence Test Types ──────────────────────────────────────────────────

export interface ConfluenceTestRequest {
  pr_title: string;
  jira_ids?: string[];
  jira_ticket_titles?: string[];
  max_results?: number;
  relevance_threshold?: number;
}

export interface ConfluenceTestPageResult {
  page_id: string;
  title: string;
  url: string;
  excerpt?: string | null;
  space_name?: string | null;
  relevance_score: number;
  kept: boolean;
}

export interface ConfluenceTestResponse {
  cql_query: string;
  keywords: string[];
  free_text_phrases: string[];
  total_candidates: number;
  kept_count: number;
  relevance_threshold: number;
  pages: ConfluenceTestPageResult[];
  duration_ms: number;
}

// ── Pipeline Step Execution Types ──────────────────────────────────────────

export interface PipelineCreateRequest {
  repo_url: string;
  pr_number: number;
}

export interface PipelineExecuteRequest {
  target_node?: string | null;
}

export interface PipelineNodeResult {
  node: string;
  status: "completed" | "error";
  duration_ms: number;
  output?: Record<string, unknown> | null;
  error?: string | null;
}

export interface PipelineSessionResponse {
  session_id: string;
  repo_url: string;
  pr_number: number;
  created_at: string;
  is_initialized: boolean;
  is_running: boolean;
  executed_nodes: string[];
  total_nodes: number;
  execution_order: string[];
  node_outputs: Record<string, Record<string, unknown>>;
  node_durations: Record<string, number>;
  node_errors: Record<string, string>;
}

/** A single SSE event from the execute endpoint. */
export type PipelineSSEEvent =
  | { type: "node_start"; node: string }
  | { type: "node_complete"; node: string; output: Record<string, unknown>; duration_ms: number }
  | { type: "node_error"; node: string; error: string; duration_ms: number }
  | { type: "done"; executed_nodes: string[] };
