import { useState, useCallback, useRef } from "react";
import {
  GitBranch,
  Database,
  FileSearch,
  Brain,
  Save,
  ArrowRight,
  ArrowDown,
  ChevronDown,
  Zap,
  MessageSquare,
  Code,
  FileText,
  Globe,
  Layers,
  AlertTriangle,
  RefreshCw,
  X,
  Play,
  SkipForward,
  FastForward,
  Square,
  Loader2,
  Check,
  XCircle,
  ChevronRight,
  RotateCcw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { api, executePipelineSSE, retryPipelineNodeSSE } from "@/lib/api";
import type { PipelineSessionResponse, PipelineSSEEvent } from "@/types/api";

// ── Graph metadata ─────────────────────────────────────────────────────────

type NodeCategory = "setup" | "context" | "analysis" | "summary" | "output";

interface GraphNode {
  id: string;
  label: string;
  description: string;
  category: NodeCategory;
  stateReads: string[];
  stateWrites: string[];
  usesLLM: boolean;
  promptTemplate?: string;
  details: string;
  icon: keyof typeof nodeIcons;
}

const nodeIcons = {
  GitBranch,
  Database,
  FileSearch,
  Brain,
  Save,
  Zap,
  MessageSquare,
  Code,
  FileText,
  Globe,
  Layers,
  AlertTriangle,
  RefreshCw,
  ArrowRight,
};

const categoryConfig: Record<
  NodeCategory,
  { label: string; color: string; bg: string; border: string }
> = {
  setup: {
    label: "Setup",
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
  },
  context: {
    label: "Context Fetching",
    color: "text-emerald-700",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
  },
  analysis: {
    label: "Analysis",
    color: "text-violet-700",
    bg: "bg-violet-50",
    border: "border-violet-200",
  },
  summary: {
    label: "Summary Generation",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
  },
  output: {
    label: "Output",
    color: "text-rose-700",
    bg: "bg-rose-50",
    border: "border-rose-200",
  },
};

const NODES: GraphNode[] = [
  {
    id: "parse_repo_url",
    label: "Parse Repo URL",
    description:
      "Parses the GitHub repository URL to extract the owner and repository name.",
    category: "setup",
    stateReads: ["repo_url"],
    stateWrites: ["repo_owner", "repo_name"],
    usesLLM: false,
    icon: "GitBranch",
    details:
      "Supports both HTTPS (`https://github.com/owner/repo`) and SSH (`git@github.com:owner/repo.git`) URL formats. Uses regex pattern matching to extract the owner/repo pair.",
  },
  {
    id: "fetch_prs",
    label: "Fetch PRs",
    description:
      "Fetches merged pull requests from the repository via the GitHub MCP server.",
    category: "setup",
    stateReads: ["repo_owner", "repo_name"],
    stateWrites: ["pr_list"],
    usesLLM: false,
    icon: "Database",
    details:
      "Supports three modes: (1) fetch a specific PR by number, (2) fetch PRs by label using GitHub search, or (3) fetch latest merged PRs up to `max_prs`. Uses the official GitHub MCP server's `search_issues` and `get_pull_request` tools.",
  },
  {
    id: "select_next_pr",
    label: "Select Next PR",
    description:
      "Selects the next PR to process from the list, or signals completion.",
    category: "setup",
    stateReads: ["pr_list", "current_pr_index"],
    stateWrites: ["current_pr", "current_pr_index"],
    usesLLM: false,
    icon: "RefreshCw",
    details:
      "Acts as the loop controller. Resets PR-specific context (jira_tickets, figma_files, etc.) before each new PR. When all PRs are processed, sets `current_pr = None` which routes to END via a conditional edge.",
  },
  {
    id: "extract_references",
    label: "Extract References",
    description:
      "Extracts Jira IDs, Figma URLs, and Confluence URLs from the PR title and body.",
    category: "context",
    stateReads: ["current_pr"],
    stateWrites: ["jira_ids", "figma_urls", "confluence_urls"],
    usesLLM: false,
    icon: "FileSearch",
    details:
      "Uses regex-based extractors: `extract_jira_ids_from_pr()` with configurable Jira project patterns, `extract_figma_urls()` for Figma file/prototype links, and `extract_confluence_urls()` for Confluence page links. Searches PR title, body, and commit messages.",
  },
  {
    id: "fetch_jira_context",
    label: "Fetch Jira Context",
    description: "Fetches detailed Jira ticket information for extracted IDs.",
    category: "context",
    stateReads: ["jira_ids"],
    stateWrites: ["jira_tickets"],
    usesLLM: false,
    icon: "Database",
    details:
      'Uses the Atlassian MCP server\'s `getJiraIssue` tool with `responseContentFormat: "markdown"`. Extracts title, description (with ADF fallback), status, priority, assignee, and acceptance criteria (via configurable custom field ID).',
  },
  {
    id: "enrich_references_from_jira",
    label: "Enrich References from Jira",
    description:
      "Scans Jira ticket descriptions for additional Figma and Confluence URLs.",
    category: "context",
    stateReads: ["jira_tickets", "figma_urls", "confluence_urls"],
    stateWrites: ["figma_urls", "confluence_urls"],
    usesLLM: false,
    icon: "Zap",
    details:
      "Jira tickets often embed Figma design links and Confluence spec pages in their description or acceptance criteria. This node enriches the URL lists by scanning those fields, deduplicating against already-known URLs.",
  },
  {
    id: "fetch_figma_context",
    label: "Fetch Figma Context",
    description: "Fetches Figma file metadata for extracted URLs.",
    category: "context",
    stateReads: ["figma_urls"],
    stateWrites: ["figma_files"],
    usesLLM: false,
    icon: "Layers",
    details:
      "Extracts file keys from Figma URLs using regex, then calls the Figma MCP server to get file metadata (name, thumbnail, version, last modified). Provides design context for the PR summary.",
  },
  {
    id: "fetch_confluence_context",
    label: "Fetch Confluence Context",
    description:
      "Searches and fetches related Confluence pages using CQL queries.",
    category: "context",
    stateReads: [
      "current_pr",
      "jira_ids",
      "jira_tickets",
      "confluence_urls",
    ],
    stateWrites: ["confluence_pages"],
    usesLLM: true,
    promptTemplate: "CONFLUENCE_PAGE_SUMMARY_PROMPT",
    icon: "Globe",
    details:
      "Three-signal search: (1) Jira ticket IDs for exact matches, (2) PR title + Jira summaries as free-text phrases, (3) keyword fallback from PR title. Over-fetches candidates (3x max), then scores each with `score_confluence_relevance()` and keeps those above the threshold. Fetches full page bodies via `getConfluencePage`, and summarizes large pages (> `max_body_tokens`) with the LLM to keep final prompts compact.",
  },
  {
    id: "analyze_files",
    label: "Analyze Files",
    description:
      "Categorizes changed files by type (frontend, backend, tests, config, etc.).",
    category: "analysis",
    stateReads: ["current_pr"],
    stateWrites: ["file_stats", "grouped_files"],
    usesLLM: false,
    icon: "FileText",
    details:
      "Uses configurable glob patterns from `file_categories` config to classify each file. Produces `file_stats` (per-category counts/additions/deletions) and `grouped_files` (files grouped by category, sorted by change volume within each group).",
  },
  {
    id: "summarize_diffs",
    label: "Summarize Diffs",
    description:
      "Summarizes code diffs via map-reduce batching, one summary per file category.",
    category: "analysis",
    stateReads: ["grouped_files"],
    stateWrites: ["diff_summaries"],
    usesLLM: true,
    promptTemplate: "DIFF_BATCH_SUMMARY_PROMPT",
    icon: "Code",
    details:
      "For each file category: (1) filter out files matching `skip_patterns` (e.g. *.lock, *.snap), (2) split remaining files into token-budgeted batches (`max_tokens_per_batch`), (3) chain-summarize each batch with the LLM, carrying the previous batch's summary as rolling context. Produces one cumulative summary per category. Full patches are included — no truncation.",
  },
  {
    id: "generate_summary",
    label: "Generate Summary",
    description:
      "Generates the main AI summary using all collected knowledge sources.",
    category: "summary",
    stateReads: [
      "current_pr",
      "jira_tickets",
      "confluence_pages",
      "figma_files",
      "diff_summaries",
    ],
    stateWrites: ["ai_summary"],
    usesLLM: true,
    promptTemplate: "PR_SUMMARY_PROMPT",
    icon: "Brain",
    details:
      "The central synthesis node. Renders the PR_SUMMARY_PROMPT template with: PR title/description, Jira tickets (with acceptance criteria), Confluence pages (using `content_summary` > `body` > `excerpt` cascade), Figma files, diff summaries by category, and a file change list as fallback. This is the main LLM call that produces the PR summary.",
  },
  {
    id: "build_review_threads",
    label: "Build Review Threads",
    description:
      "Converts flat review comments into threaded conversations grouped by reply chains.",
    category: "analysis",
    stateReads: ["current_pr"],
    stateWrites: ["review_threads"],
    usesLLM: false,
    icon: "MessageSquare",
    details:
      "Groups flat review comments into threaded conversations using `in_reply_to_id` chains. Each thread preserves: file path, line range, full `diff_hunk` code context from the root comment, chronological comment list, and resolution status (tracked via heuristic). Writes threaded data to state once — downstream analysis nodes read from `review_threads` instead of re-computing.",
  },
  {
    id: "identify_coding_standards",
    label: "Identify Coding Standards",
    description:
      "Identifies coding standards and patterns from threaded review conversations.",
    category: "analysis",
    stateReads: ["current_pr", "review_threads"],
    stateWrites: ["coding_standards"],
    usesLLM: true,
    promptTemplate: "CODING_STANDARDS_PROMPT",
    icon: "Code",
    details:
      "Reads pre-built `review_threads` from state (computed by the Build Review Threads node). The prompt shows threads with file path, line range, diff context, and chronological comments — giving the LLM rich context to identify patterns like: frontend guidelines, backend practices, testing standards, and linting rules.",
  },
  {
    id: "identify_architectural_patterns",
    label: "Identify Architectural Patterns",
    description:
      "Identifies architectural patterns and design principles from the PR.",
    category: "analysis",
    stateReads: [
      "current_pr",
      "review_threads",
      "file_stats",
      "grouped_files",
      "jira_tickets",
    ],
    stateWrites: ["architectural_patterns"],
    usesLLM: true,
    promptTemplate: "ARCHITECTURAL_PATTERNS_PROMPT",
    icon: "Layers",
    details:
      "Reads pre-built `review_threads` from state plus file statistics and Jira context. Analyzes: frontend architecture (component patterns, state management), backend architecture (API design, service patterns), testing architecture, infrastructure/DevOps, data layer, and integration patterns. Only reports when distinctive patterns are found.",
  },
  {
    id: "generate_review_summary",
    label: "Generate Review Summary",
    description:
      "Generates a structured summary of review conversations.",
    category: "analysis",
    stateReads: ["current_pr", "review_threads"],
    stateWrites: ["review_summary"],
    usesLLM: true,
    promptTemplate: "REVIEW_SUMMARY_PROMPT",
    icon: "MessageSquare",
    details:
      "Reads pre-built `review_threads` from state to produce an attributed summary. Each thread includes the file path, line range, full diff_hunk code context, and the chronological conversation. The LLM organizes feedback into: coding standards enforced, technical decisions, patterns & best practices, concerns & resolutions, and follow-up actions — all attributed to specific reviewers.",
  },
  {
    id: "identify_breaking_changes",
    label: "Identify Breaking Changes",
    description:
      "Identifies breaking changes from file paths and PR description.",
    category: "analysis",
    stateReads: ["current_pr"],
    stateWrites: ["breaking_changes"],
    usesLLM: true,
    promptTemplate: "BREAKING_CHANGES_PROMPT",
    icon: "AlertTriangle",
    details:
      "Analyzes PR title, description, and file paths for: API endpoint changes, database schema changes, removed/renamed functions, configuration changes, and dependency version bumps with breaking changes. Provides migration guidance when breaking changes are found.",
  },
  {
    id: "save_summary",
    label: "Save Summary",
    description:
      "Renders the final Markdown summary file and saves to disk.",
    category: "output",
    stateReads: [
      "current_pr",
      "ai_summary",
      "jira_tickets",
      "confluence_pages",
      "figma_files",
      "file_stats",
      "grouped_files",
      "coding_standards",
      "architectural_patterns",
      "review_summary",
      "breaking_changes",
    ],
    stateWrites: ["output_files", "summaries", "current_pr_index"],
    usesLLM: false,
    icon: "Save",
    details:
      "Renders a Jinja2 Markdown template (main or fallback) with all collected data. Generates per-file diff URLs using SHA-256 anchors pointing to the PR's file diff view. Supports configurable output directory, filename pattern, overwrite policy, and optional YAML front-matter metadata. Increments `current_pr_index` to advance the processing loop.",
  },
];

// Layout definition: rows of node IDs (parallel nodes share a row)
interface LayoutRow {
  nodes: string[][];  // groups of node IDs; each group shown side-by-side
  label?: string;
  connectorType?: "fork" | "join" | "straight" | "loop";
}

const LAYOUT: LayoutRow[] = [
  { label: "Setup", nodes: [["parse_repo_url"], ["fetch_prs"], ["select_next_pr"]] },
  { label: "Extraction", nodes: [["extract_references"]] },
  {
    label: "Context Fetching",
    nodes: [
      ["fetch_jira_context", "analyze_files"],
      ["enrich_references_from_jira", "summarize_diffs"],
      ["fetch_figma_context", "fetch_confluence_context"],
    ],
  },
  { label: "Synthesis", nodes: [["generate_summary"]] },
  { label: "Threading", nodes: [["build_review_threads"]] },
  {
    label: "Post-Analysis",
    nodes: [
      ["identify_coding_standards"],
      ["identify_architectural_patterns"],
      ["generate_review_summary"],
      ["identify_breaking_changes"],
    ],
  },
  { label: "Output", nodes: [["save_summary"]] },
];

const EDGES: { from: string; to: string; label?: string }[] = [
  { from: "__start__", to: "parse_repo_url" },
  { from: "parse_repo_url", to: "fetch_prs" },
  { from: "fetch_prs", to: "select_next_pr" },
  { from: "select_next_pr", to: "extract_references", label: "has PRs" },
  { from: "extract_references", to: "fetch_jira_context" },
  { from: "extract_references", to: "analyze_files" },
  { from: "fetch_jira_context", to: "enrich_references_from_jira" },
  { from: "enrich_references_from_jira", to: "fetch_figma_context" },
  { from: "enrich_references_from_jira", to: "fetch_confluence_context" },
  { from: "analyze_files", to: "summarize_diffs" },
  { from: "fetch_figma_context", to: "generate_summary" },
  { from: "fetch_confluence_context", to: "generate_summary" },
  { from: "summarize_diffs", to: "generate_summary" },
  { from: "generate_summary", to: "build_review_threads" },
  { from: "build_review_threads", to: "identify_coding_standards" },
  { from: "identify_coding_standards", to: "identify_architectural_patterns" },
  { from: "identify_architectural_patterns", to: "generate_review_summary" },
  { from: "generate_review_summary", to: "identify_breaking_changes" },
  { from: "identify_breaking_changes", to: "save_summary" },
  { from: "save_summary", to: "select_next_pr", label: "next PR" },
];

const nodeMap = new Map(NODES.map((n) => [n.id, n]));

// ── Execution types ────────────────────────────────────────────────────────

type NodeExecStatus = "pending" | "running" | "completed" | "error";

// ── Components ─────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status?: NodeExecStatus }) {
  if (!status || status === "pending") return null;
  if (status === "running")
    return <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />;
  if (status === "completed")
    return <Check className="h-3.5 w-3.5 text-emerald-600" />;
  return <XCircle className="h-3.5 w-3.5 text-red-500" />;
}

function NodeCard({
  node,
  isSelected,
  onClick,
  execStatus,
  duration,
}: {
  node: GraphNode;
  isSelected: boolean;
  onClick: () => void;
  execStatus?: NodeExecStatus;
  duration?: number;
}) {
  const cat = categoryConfig[node.category];
  const IconComp = nodeIcons[node.icon];

  // Execution-aware ring colors
  const execRing =
    execStatus === "running"
      ? "ring-2 ring-blue-400 ring-offset-1"
      : execStatus === "completed"
        ? "ring-1 ring-emerald-300"
        : execStatus === "error"
          ? "ring-2 ring-red-400 ring-offset-1"
          : "";

  return (
    <button
      onClick={onClick}
      className={`
        group relative flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5
        text-left text-sm transition-all cursor-pointer min-w-[180px] max-w-[220px]
        ${execRing}
        ${isSelected
          ? `${cat.border} ${cat.bg} ring-2 ring-offset-1 ring-current ${cat.color} shadow-md`
          : `border-border bg-card hover:${cat.bg} hover:${cat.border} hover:shadow-sm`
        }
      `}
    >
      <IconComp
        className={`h-4 w-4 shrink-0 ${isSelected ? cat.color : "text-muted-foreground group-hover:" + cat.color}`}
      />
      <div className="min-w-0 flex-1">
        <div className={`font-medium text-xs leading-tight truncate ${isSelected ? cat.color : "text-foreground"}`}>
          {node.label}
        </div>
        <div className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
          {execStatus === "completed" && duration != null
            ? `${(duration / 1000).toFixed(1)}s`
            : node.description.slice(0, 60) + "…"}
        </div>
      </div>
      {/* AI badge */}
      {node.usesLLM && (
        <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-amber-600 text-[8px] font-bold ring-1 ring-amber-200" title="Uses LLM">
          AI
        </span>
      )}
      {/* Execution status indicator */}
      {execStatus && execStatus !== "pending" && (
        <span className="absolute -top-1.5 -left-1.5">
          <StatusIcon status={execStatus} />
        </span>
      )}
    </button>
  );
}

function Connector({ type = "straight" }: { type?: "straight" | "fork" | "join" }) {
  if (type === "straight") {
    return (
      <div className="flex justify-center py-1">
        <ArrowDown className="h-4 w-4 text-border" />
      </div>
    );
  }
  return (
    <div className="flex justify-center py-1">
      <ChevronDown className="h-4 w-4 text-border" />
    </div>
  );
}

function StageLabel({ label, category }: { label: string; category?: NodeCategory }) {
  const cat = category ? categoryConfig[category] : null;
  return (
    <div className="flex items-center gap-2 mb-2 mt-1">
      <div
        className={`text-[10px] font-semibold uppercase tracking-wider ${cat ? cat.color : "text-muted-foreground"}`}
      >
        {label}
      </div>
      <div className="flex-1 h-px bg-border" />
    </div>
  );
}

/** Renders one key-value pair from a node's state diff output. */
function OutputEntry({ stateKey, value }: { stateKey: string; value: unknown }) {
  const [expanded, setExpanded] = useState(false);

  const rendered = (() => {
    if (value === null || value === undefined) return <span className="text-muted-foreground italic">null</span>;
    if (typeof value === "string") {
      if (value.length > 300) {
        return (
          <div>
            <pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">
              {expanded ? value : value.slice(0, 300) + "…"}
            </pre>
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-blue-600 hover:underline cursor-pointer mt-0.5">
              {expanded ? "Collapse" : `Show all (${value.length} chars)`}
            </button>
          </div>
        );
      }
      return <pre className="text-xs text-foreground/80 whitespace-pre-wrap break-all font-mono">{value}</pre>;
    }
    if (typeof value === "number" || typeof value === "boolean")
      return <span className="text-xs font-mono text-foreground/80">{String(value)}</span>;

    // Objects / arrays
    const json = JSON.stringify(value, null, 2);
    if (json.length > 500) {
      const summary = Array.isArray(value)
        ? `Array (${value.length} items)`
        : `Object (${Object.keys(value as Record<string, unknown>).length} keys)`;
      return (
        <div>
          <span className="text-xs text-muted-foreground">{summary}</span>
          <button onClick={() => setExpanded(!expanded)} className="ml-2 text-[10px] text-blue-600 hover:underline cursor-pointer">
            {expanded ? "Collapse" : "Expand"}
          </button>
          {expanded && (
            <pre className="text-[11px] text-foreground/70 whitespace-pre-wrap break-all font-mono mt-1 max-h-[200px] overflow-auto bg-white/50 rounded p-1.5">
              {json}
            </pre>
          )}
        </div>
      );
    }
    return (
      <pre className="text-[11px] text-foreground/70 whitespace-pre-wrap break-all font-mono max-h-[200px] overflow-auto bg-white/50 rounded p-1.5">
        {json}
      </pre>
    );
  })();

  return (
    <div className="border-t border-emerald-200 pt-1.5 first:border-t-0 first:pt-0">
      <code className="text-[11px] font-semibold text-emerald-800">{stateKey}</code>
      <div className="mt-0.5">{rendered}</div>
    </div>
  );
}

function NodeDetail({
  node,
  onClose,
  execStatus,
  duration,
  output,
  error,
  onExecuteUpTo,
  onRetry,
  isExecuting,
  hasSession,
}: {
  node: GraphNode;
  onClose: () => void;
  execStatus?: NodeExecStatus;
  duration?: number;
  output?: Record<string, unknown> | null;
  error?: string | null;
  onExecuteUpTo: (nodeId: string) => void;
  onRetry: (nodeId: string) => void;
  isExecuting: boolean;
  hasSession: boolean;
}) {
  const cat = categoryConfig[node.category];
  const IconComp = nodeIcons[node.icon];
  const [outputExpanded, setOutputExpanded] = useState(true);

  // Find incoming and outgoing edges
  const incoming = EDGES.filter((e) => e.to === node.id);
  const outgoing = EDGES.filter((e) => e.from === node.id);

  return (
    <div className={`rounded-xl border ${cat.border} ${cat.bg}/30 overflow-hidden`}>
      {/* Header */}
      <div className={`px-5 py-4 border-b ${cat.border} ${cat.bg}`}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`rounded-lg ${cat.bg} p-2 ring-1 ${cat.border}`}>
              <IconComp className={`h-5 w-5 ${cat.color}`} />
            </div>
            <div>
              <h3 className={`text-base font-bold ${cat.color}`}>{node.label}</h3>
              <p className="text-sm text-foreground/70 mt-0.5">{node.description}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-2 mt-3">
          <Badge variant={node.usesLLM ? "warning" : "secondary"}>
            {node.usesLLM ? "LLM Call" : "Logic Only"}
          </Badge>
          <Badge>{cat.label}</Badge>
          {node.promptTemplate && (
            <Badge variant="default">{node.promptTemplate}</Badge>
          )}
          {/* Execution status badge */}
          {execStatus === "completed" && (
            <Badge variant="default">
              <Check className="h-3 w-3 mr-0.5" />
              {duration != null ? `${(duration / 1000).toFixed(1)}s` : "Done"}
            </Badge>
          )}
          {execStatus === "running" && (
            <Badge variant="default">
              <Loader2 className="h-3 w-3 mr-0.5 animate-spin" />
              Running…
            </Badge>
          )}
          {execStatus === "error" && (
            <Badge variant="destructive">
              <XCircle className="h-3 w-3 mr-0.5" />
              Failed
            </Badge>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-4 space-y-4 text-sm">

        {/* Execute button (only when session is active and node not yet run) */}
        {hasSession && execStatus !== "completed" && execStatus !== "running" && execStatus !== "error" && (
          <button
            onClick={() => onExecuteUpTo(node.id)}
            disabled={isExecuting}
            className="w-full flex items-center justify-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {isExecuting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Execute up to here
          </button>
        )}

        {/* Retry button (shown for completed or errored nodes) */}
        {hasSession && (execStatus === "completed" || execStatus === "error") && (
          <button
            onClick={() => onRetry(node.id)}
            disabled={isExecuting}
            className={`w-full flex items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer ${
              execStatus === "error"
                ? "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                : "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100"
            }`}
          >
            {isExecuting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Retry this node
          </button>
        )}

        {/* Error display */}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <h4 className="font-semibold text-red-700 mb-1 flex items-center gap-1.5">
              <XCircle className="h-3.5 w-3.5" />
              Error
            </h4>
            <pre className="text-xs text-red-800 whitespace-pre-wrap break-all font-mono">{error}</pre>
          </div>
        )}

        {/* Node output viewer */}
        {output && Object.keys(output).length > 0 && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50/50">
            <button
              onClick={() => setOutputExpanded(!outputExpanded)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-semibold text-emerald-700 cursor-pointer hover:bg-emerald-100/50 transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5" />
                State Output ({Object.keys(output).length} keys)
              </span>
              <ChevronRight
                className={`h-3.5 w-3.5 transition-transform ${outputExpanded ? "rotate-90" : ""}`}
              />
            </button>
            {outputExpanded && (
              <div className="px-3 pb-3 space-y-2 max-h-[400px] overflow-auto">
                {Object.entries(output).map(([key, value]) => (
                  <OutputEntry key={key} stateKey={key} value={value} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Details */}
        <div>
          <h4 className="font-semibold text-foreground mb-1.5">How it works</h4>
          <p className="text-foreground/80 leading-relaxed">{node.details}</p>
        </div>

        {/* State I/O */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="font-semibold text-foreground mb-1.5 flex items-center gap-1.5">
              <ArrowRight className="h-3 w-3 text-emerald-500" />
              Reads from state
            </h4>
            <div className="flex flex-wrap gap-1">
              {node.stateReads.map((key) => (
                <code
                  key={key}
                  className="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] text-emerald-700 ring-1 ring-emerald-200"
                >
                  {key}
                </code>
              ))}
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-foreground mb-1.5 flex items-center gap-1.5">
              <ArrowRight className="h-3 w-3 text-blue-500" />
              Writes to state
            </h4>
            <div className="flex flex-wrap gap-1">
              {node.stateWrites.map((key) => (
                <code
                  key={key}
                  className="rounded bg-blue-50 px-1.5 py-0.5 text-[11px] text-blue-700 ring-1 ring-blue-200"
                >
                  {key}
                </code>
              ))}
            </div>
          </div>
        </div>

        {/* Connections */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="font-semibold text-foreground mb-1.5">Receives from</h4>
            <div className="space-y-1">
              {incoming.length === 0 ? (
                <span className="text-muted-foreground text-xs">START</span>
              ) : (
                incoming.map((e) => {
                  const src = e.from === "__start__" ? null : nodeMap.get(e.from);
                  return (
                    <div key={e.from} className="flex items-center gap-1.5 text-xs text-foreground/70">
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      {src ? src.label : "START"}
                      {e.label && (
                        <span className="text-muted-foreground">({e.label})</span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-foreground mb-1.5">Sends to</h4>
            <div className="space-y-1">
              {outgoing.length === 0 ? (
                <span className="text-muted-foreground text-xs">END</span>
              ) : (
                outgoing.map((e) => {
                  const tgt = e.to === "__end__" ? null : nodeMap.get(e.to);
                  return (
                    <div key={e.to} className="flex items-center gap-1.5 text-xs text-foreground/70">
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      {tgt ? tgt.label : "END"}
                      {e.label && (
                        <span className="text-muted-foreground">({e.label})</span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Prompt template preview for review-thread nodes */}
        {node.id === "build_review_threads" && (
            <div className="rounded-lg border border-violet-200 bg-violet-50/50 p-3">
              <h4 className="font-semibold text-violet-700 mb-1.5 flex items-center gap-1.5">
                <MessageSquare className="h-3.5 w-3.5" />
                Review Threading Pipeline
              </h4>
              <div className="text-xs text-violet-900/70 space-y-1.5">
                <p>
                  <strong>1.</strong> Flat review comments → <code className="text-violet-700">build_review_threads()</code>
                </p>
                <p>
                  <strong>2.</strong> Groups by <code className="text-violet-700">in_reply_to_id</code> chains,
                  sorts chronologically
                </p>
                <p>
                  <strong>3.</strong> Each thread preserves: <code className="text-violet-700">file_path</code>,{" "}
                  <code className="text-violet-700">line_range</code>, full{" "}
                  <code className="text-violet-700">diff_hunk</code> code context
                </p>
                <p>
                  <strong>4.</strong> Resolution status tracked via heuristic (not shown in prompt)
                </p>
                <p>
                  <strong>5.</strong> Stored in state — downstream nodes read without re-computing
                </p>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

const EXECUTION_ORDER = [
  "parse_repo_url", "fetch_prs", "select_next_pr", "extract_references",
  "fetch_jira_context", "analyze_files", "enrich_references_from_jira",
  "summarize_diffs", "fetch_figma_context", "fetch_confluence_context",
  "generate_summary", "build_review_threads", "identify_coding_standards",
  "identify_architectural_patterns", "generate_review_summary",
  "identify_breaking_changes", "save_summary",
];

export function PipelineGraph() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // ── Session & execution state ────────────────────────────────────────
  const [session, setSession] = useState<PipelineSessionResponse | null>(null);
  const [nodeStatuses, setNodeStatuses] = useState<Record<string, NodeExecStatus>>({});
  const [nodeOutputs, setNodeOutputs] = useState<Record<string, Record<string, unknown>>>({});
  const [nodeDurations, setNodeDurations] = useState<Record<string, number>>({});
  const [nodeErrors, setNodeErrors] = useState<Record<string, string>>({});
  const [isExecuting, setIsExecuting] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── Form state ───────────────────────────────────────────────────────
  const [repoUrl, setRepoUrl] = useState("https://github.com/nasuni/portal");
  const [prNumber, setPrNumber] = useState<string>("");

  const selectedNode = selectedNodeId ? nodeMap.get(selectedNodeId) ?? null : null;

  // ── Session lifecycle ────────────────────────────────────────────────

  const createSession = useCallback(async () => {
    const num = parseInt(prNumber, 10);
    if (!repoUrl || isNaN(num) || num <= 0) {
      setSessionError("Enter a valid repo URL and PR number");
      return;
    }
    setIsCreating(true);
    setSessionError(null);
    try {
      const res = await api.createPipelineSession({ repo_url: repoUrl, pr_number: num });
      setSession(res);
      // Initialize all node statuses to pending
      const statuses: Record<string, NodeExecStatus> = {};
      for (const n of EXECUTION_ORDER) statuses[n] = "pending";
      setNodeStatuses(statuses);
      setNodeOutputs({});
      setNodeDurations({});
      setNodeErrors({});
    } catch (e) {
      setSessionError(e instanceof Error ? e.message : "Failed to create session");
    } finally {
      setIsCreating(false);
    }
  }, [repoUrl, prNumber]);

  const resetSession = useCallback(async () => {
    if (session) {
      try { await api.deletePipelineSession(session.session_id); } catch { /* ignore */ }
    }
    setSession(null);
    setNodeStatuses({});
    setNodeOutputs({});
    setNodeDurations({});
    setNodeErrors({});
    setIsExecuting(false);
    setSelectedNodeId(null);
    setSessionError(null);
    abortRef.current?.abort();
  }, [session]);

  // ── Execution ────────────────────────────────────────────────────────

  const executeUpTo = useCallback(async (targetNode: string | null) => {
    if (!session) return;
    setIsExecuting(true);
    setSessionError(null);

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      await executePipelineSSE(
        session.session_id,
        targetNode,
        (event: PipelineSSEEvent) => {
          switch (event.type) {
            case "node_start":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "running" }));
              setSelectedNodeId(event.node);
              break;
            case "node_complete":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "completed" }));
              setNodeOutputs((prev) => ({ ...prev, [event.node]: event.output }));
              setNodeDurations((prev) => ({ ...prev, [event.node]: event.duration_ms }));
              break;
            case "node_error":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "error" }));
              setNodeErrors((prev) => ({ ...prev, [event.node]: event.error }));
              setNodeDurations((prev) => ({ ...prev, [event.node]: event.duration_ms }));
              break;
            case "done":
              // Refresh session snapshot
              setSession((prev) =>
                prev ? { ...prev, executed_nodes: event.executed_nodes } : prev
              );
              break;
          }
        },
        ac.signal
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setSessionError(e instanceof Error ? e.message : "Execution failed");
      }
    } finally {
      setIsExecuting(false);
      abortRef.current = null;
    }
  }, [session]);

  const executeNext = useCallback(() => {
    // Find the first pending node
    const next = EXECUTION_ORDER.find((n) => nodeStatuses[n] === "pending" || !nodeStatuses[n]);
    if (next) executeUpTo(next);
  }, [nodeStatuses, executeUpTo]);

  const executeAll = useCallback(() => executeUpTo(null), [executeUpTo]);

  const retryNode = useCallback(async (nodeName: string) => {
    if (!session) return;
    setIsExecuting(true);
    setSessionError(null);

    // Clear previous error for this node before retry
    setNodeErrors((prev) => {
      const copy = { ...prev };
      delete copy[nodeName];
      return copy;
    });

    const ac = new AbortController();
    abortRef.current = ac;

    try {
      await retryPipelineNodeSSE(
        session.session_id,
        nodeName,
        (event: PipelineSSEEvent) => {
          switch (event.type) {
            case "node_start":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "running" }));
              break;
            case "node_complete":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "completed" }));
              setNodeOutputs((prev) => ({ ...prev, [event.node]: event.output }));
              setNodeDurations((prev) => ({ ...prev, [event.node]: event.duration_ms }));
              setNodeErrors((prev) => {
                const copy = { ...prev };
                delete copy[event.node];
                return copy;
              });
              break;
            case "node_error":
              setNodeStatuses((prev) => ({ ...prev, [event.node]: "error" }));
              setNodeErrors((prev) => ({ ...prev, [event.node]: event.error }));
              setNodeDurations((prev) => ({ ...prev, [event.node]: event.duration_ms }));
              break;
            case "done":
              setSession((prev) =>
                prev ? { ...prev, executed_nodes: event.executed_nodes } : prev
              );
              break;
          }
        },
        ac.signal
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setSessionError(e instanceof Error ? e.message : "Retry failed");
      }
    } finally {
      setIsExecuting(false);
      abortRef.current = null;
    }
  }, [session]);

  const stopExecution = useCallback(() => abortRef.current?.abort(), []);

  // ── Derived state ────────────────────────────────────────────────────
  const completedCount = Object.values(nodeStatuses).filter((s) => s === "completed").length;
  const hasSession = session !== null;

  // Map stages to categories for labels
  const stageCategories: Record<string, NodeCategory> = {
    Setup: "setup",
    Extraction: "context",
    "Context Fetching": "context",
    Synthesis: "summary",
    Threading: "analysis",
    "Post-Analysis": "analysis",
    Output: "output",
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-bold text-foreground">Pipeline Graph</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Interactive visualization of the LangGraph PR summary pipeline. Click any node to see details or execute.
        </p>
      </div>

      {/* Session creation / toolbar */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
        {!hasSession ? (
          /* ── Create session form ── */
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[260px]">
              <label className="block text-xs font-medium text-muted-foreground mb-1">Repository URL</label>
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <div className="w-28">
              <label className="block text-xs font-medium text-muted-foreground mb-1">PR #</label>
              <input
                type="number"
                value={prNumber}
                onChange={(e) => setPrNumber(e.target.value)}
                placeholder="1234"
                min={1}
                className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            </div>
            <button
              onClick={createSession}
              disabled={isCreating}
              className="flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
            >
              {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Create Session
            </button>
          </div>
        ) : (
          /* ── Execution toolbar ── */
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-sm">
              <Badge variant="default">{session.session_id}</Badge>
              <span className="text-muted-foreground">
                PR #{session.pr_number}
              </span>
              <span className="font-medium">
                {completedCount}/{EXECUTION_ORDER.length} nodes
              </span>
            </div>

            <div className="flex-1" />

            {!isExecuting ? (
              <>
                {completedCount < EXECUTION_ORDER.length && (
                  <>
                    <button
                      onClick={executeNext}
                      className="flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors cursor-pointer"
                    >
                      <SkipForward className="h-3.5 w-3.5" />
                      Next
                    </button>
                    <button
                      onClick={executeAll}
                      className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors cursor-pointer"
                    >
                      <FastForward className="h-3.5 w-3.5" />
                      Run All
                    </button>
                  </>
                )}
                <button
                  onClick={resetSession}
                  className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset
                </button>
              </>
            ) : (
              <>
                <span className="flex items-center gap-1.5 text-xs text-blue-600">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Executing…
                </span>
                <button
                  onClick={stopExecution}
                  className="flex items-center gap-1.5 rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 transition-colors cursor-pointer"
                >
                  <Square className="h-3 w-3" />
                  Stop
                </button>
              </>
            )}
          </div>
        )}

        {sessionError && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {sessionError}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {Object.entries(categoryConfig).map(([key, val]) => (
          <div key={key} className={`flex items-center gap-1.5 ${val.color}`}>
            <div className={`h-2.5 w-2.5 rounded-full ${val.bg} ring-1 ${val.border}`} />
            {val.label}
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-amber-600">
          <span className="flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-[8px] font-bold ring-1 ring-amber-200">
            AI
          </span>
          LLM Call
        </div>
        {hasSession && (
          <>
            <div className="w-px h-4 bg-border mx-1" />
            <div className="flex items-center gap-1.5 text-emerald-600"><Check className="h-3 w-3" /> Completed</div>
            <div className="flex items-center gap-1.5 text-blue-500"><Loader2 className="h-3 w-3" /> Running</div>
            <div className="flex items-center gap-1.5 text-red-500"><XCircle className="h-3 w-3" /> Error</div>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-6 items-start">
        {/* Pipeline diagram */}
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          {LAYOUT.map((stage, stageIdx) => (
            <div key={stageIdx}>
              <StageLabel label={stage.label!} category={stageCategories[stage.label!]} />

              {stage.nodes.map((row, rowIdx) => (
                <div key={rowIdx}>
                  <div className="flex items-center justify-center gap-3 flex-wrap">
                    {row.map((nodeId) => {
                      const node = nodeMap.get(nodeId);
                      if (!node) return null;
                      return (
                        <NodeCard
                          key={nodeId}
                          node={node}
                          isSelected={selectedNodeId === nodeId}
                          execStatus={nodeStatuses[nodeId]}
                          duration={nodeDurations[nodeId]}
                          onClick={() =>
                            setSelectedNodeId((prev) =>
                              prev === nodeId ? null : nodeId
                            )
                          }
                        />
                      );
                    })}
                  </div>
                  {/* Connector between rows within same stage */}
                  {rowIdx < stage.nodes.length - 1 && <Connector />}
                </div>
              ))}

              {/* Connector between stages */}
              {stageIdx < LAYOUT.length - 1 && (
                <div className="flex justify-center py-1.5">
                  <ArrowDown className="h-4 w-4 text-border" />
                </div>
              )}
            </div>
          ))}

          {/* Loop-back indicator */}
          <div className="mt-3 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Loops back to <strong>Select Next PR</strong> until all PRs processed</span>
          </div>
        </div>

        {/* Detail panel */}
        <div className="lg:sticky lg:top-4">
          {selectedNode ? (
            <NodeDetail
              node={selectedNode}
              onClose={() => setSelectedNodeId(null)}
              execStatus={nodeStatuses[selectedNode.id]}
              duration={nodeDurations[selectedNode.id]}
              output={nodeOutputs[selectedNode.id]}
              error={nodeErrors[selectedNode.id]}
              onExecuteUpTo={executeUpTo}
              onRetry={retryNode}
              isExecuting={isExecuting}
              hasSession={hasSession}
            />
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-muted/30 p-8 text-center">
              <Brain className="mx-auto h-10 w-10 text-muted-foreground/40 mb-3" />
              <p className="text-sm font-medium text-muted-foreground">
                {hasSession ? "Select a node to view output or execute" : "Select a node to view details"}
              </p>
              <p className="text-xs text-muted-foreground/70 mt-1">
                {hasSession
                  ? "Click a node to see its state output, or click 'Execute up to here' to run the pipeline."
                  : "Click any node in the pipeline to see what it does, which state it reads/writes, and what prompt template it uses."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
