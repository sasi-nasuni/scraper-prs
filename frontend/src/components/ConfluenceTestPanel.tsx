import { useState, useCallback } from "react";
import {
  Search,
  Play,
  Loader2,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Code,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type {
  ConfluenceTestResponse,
  ConfluenceTestPageResult,
} from "@/types/api";

// ── Score bar ───────────────────────────────────────────────────────────────

function ScoreBar({ score, kept }: { score: number; kept: boolean }) {
  const pct = Math.round(score * 100);
  const color = kept
    ? pct >= 50
      ? "bg-emerald-500"
      : "bg-emerald-400"
    : "bg-zinc-400";

  return (
    <div className="flex items-center gap-2 min-w-[140px]">
      <div className="h-2 w-20 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
      <span className="text-xs font-mono tabular-nums w-10 text-right">
        {score.toFixed(2)}
      </span>
    </div>
  );
}

// ── Page row ────────────────────────────────────────────────────────────────

function PageRow({ page }: { page: ConfluenceTestPageResult }) {
  const [showExcerpt, setShowExcerpt] = useState(false);

  return (
    <div
      className={`rounded-lg border px-4 py-3 transition-colors ${
        page.kept
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-border bg-card/50 opacity-70"
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            {page.kept ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
            ) : (
              <XCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <a
              href={page.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-sm hover:underline truncate"
            >
              {page.title}
              <ExternalLink className="inline h-3 w-3 ml-1 opacity-50" />
            </a>
          </div>

          <div className="flex items-center gap-2 mt-1 ml-6">
            {page.space_name && (
              <Badge variant="secondary" className="text-[10px]">
                {page.space_name}
              </Badge>
            )}
            <span className="text-[10px] text-muted-foreground font-mono">
              ID: {page.page_id}
            </span>
          </div>

          {page.excerpt && (
            <button
              onClick={() => setShowExcerpt(!showExcerpt)}
              className="flex items-center gap-1 mt-1.5 ml-6 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {showExcerpt ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              excerpt
            </button>
          )}
          {showExcerpt && page.excerpt && (
            <p className="mt-1 ml-6 text-xs text-muted-foreground leading-relaxed">
              {page.excerpt}
            </p>
          )}
        </div>

        <ScoreBar score={page.relevance_score} kept={page.kept} />
      </div>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

export function ConfluenceTestPanel() {
  // Form state
  const [prTitle, setPrTitle] = useState("");
  const [jiraIds, setJiraIds] = useState<string[]>([""]);
  const [jiraTicketTitles, setJiraTicketTitles] = useState<string[]>([""]);
  const [maxResults, setMaxResults] = useState("10");
  const [threshold, setThreshold] = useState("0.15");

  // Result state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConfluenceTestResponse | null>(null);
  const [showQuery, setShowQuery] = useState(false);

  // Array field helpers
  const addJiraId = () => setJiraIds((ids) => [...ids, ""]);
  const removeJiraId = (i: number) =>
    setJiraIds((ids) => ids.filter((_, idx) => idx !== i));
  const updateJiraId = (i: number, val: string) =>
    setJiraIds((ids) => ids.map((id, idx) => (idx === i ? val : id)));

  const addTicketTitle = () => setJiraTicketTitles((ts) => [...ts, ""]);
  const removeTicketTitle = (i: number) =>
    setJiraTicketTitles((ts) => ts.filter((_, idx) => idx !== i));
  const updateTicketTitle = (i: number, val: string) =>
    setJiraTicketTitles((ts) => ts.map((t, idx) => (idx === i ? val : t)));

  const handleSearch = useCallback(async () => {
    if (!prTitle.trim()) {
      setError("PR title is required");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.testConfluenceSearch({
        pr_title: prTitle.trim(),
        jira_ids: jiraIds.map((s) => s.trim()).filter(Boolean),
        jira_ticket_titles: jiraTicketTitles
          .map((s) => s.trim())
          .filter(Boolean),
        max_results: Number(maxResults) || 10,
        relevance_threshold: Number(threshold) || 0.15,
      });
      setResult(res);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to test Confluence search"
      );
    } finally {
      setLoading(false);
    }
  }, [prTitle, jiraIds, jiraTicketTitles, maxResults, threshold]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Confluence Search Test
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-xs text-muted-foreground -mt-2">
          Test the Confluence search + relevance scoring pipeline. Provide a PR
          title and optional Jira context to see which Confluence pages are
          matched, their relevance scores, and which ones pass the threshold
          filter.
        </p>

        {/* PR Title */}
        <div>
          <label className="mb-1 block text-sm font-medium">
            PR Title <span className="text-destructive">*</span>
          </label>
          <Input
            placeholder='e.g. "feat: Add user roles management page"'
            value={prTitle}
            onChange={(e) => setPrTitle(e.target.value)}
          />
        </div>

        {/* Jira IDs */}
        <div>
          <label className="mb-1 flex items-center justify-between text-sm font-medium">
            <span>Jira Ticket IDs</span>
            <button
              onClick={addJiraId}
              className="flex items-center gap-1 text-xs text-primary hover:underline cursor-pointer"
            >
              <Plus className="h-3 w-3" /> Add
            </button>
          </label>
          <div className="space-y-2">
            {jiraIds.map((id, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  placeholder="e.g. PORTAL-1687"
                  value={id}
                  onChange={(e) => updateJiraId(i, e.target.value)}
                />
                {jiraIds.length > 1 && (
                  <button
                    onClick={() => removeJiraId(i)}
                    className="text-muted-foreground hover:text-destructive cursor-pointer"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Jira Ticket Titles */}
        <div>
          <label className="mb-1 flex items-center justify-between text-sm font-medium">
            <span>Jira Ticket Titles / Summaries</span>
            <button
              onClick={addTicketTitle}
              className="flex items-center gap-1 text-xs text-primary hover:underline cursor-pointer"
            >
              <Plus className="h-3 w-3" /> Add
            </button>
          </label>
          <div className="space-y-2">
            {jiraTicketTitles.map((title, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  placeholder="e.g. Implement RBAC for portal settings"
                  value={title}
                  onChange={(e) => updateTicketTitle(i, e.target.value)}
                />
                {jiraTicketTitles.length > 1 && (
                  <button
                    onClick={() => removeTicketTitle(i)}
                    className="text-muted-foreground hover:text-destructive cursor-pointer"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Settings row */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">
              Max Results
            </label>
            <Input
              type="number"
              placeholder="10"
              value={maxResults}
              onChange={(e) => setMaxResults(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              Relevance Threshold{" "}
              <span className="text-muted-foreground font-normal">
                (0.0 – 1.0)
              </span>
            </label>
            <Input
              type="number"
              step="0.05"
              min="0"
              max="1"
              placeholder="0.15"
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
            />
          </div>
        </div>

        {/* Search button */}
        <Button onClick={handleSearch} disabled={loading} className="w-full">
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching Confluence...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Test Search
            </>
          )}
        </Button>

        {/* Error */}
        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Stats row */}
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">
                {result.total_candidates} candidates
              </Badge>
              <Badge variant="success">{result.kept_count} kept</Badge>
              <Badge variant="warning">
                {result.total_candidates - result.kept_count} filtered out
              </Badge>
              <Badge variant="secondary">
                {result.duration_ms.toFixed(0)} ms
              </Badge>
              <Badge variant="secondary">
                threshold: {result.relevance_threshold}
              </Badge>
            </div>

            {/* Derived info */}
            <div className="rounded-md border border-border bg-muted/30 px-4 py-3 space-y-2 text-xs">
              <div>
                <span className="font-medium">Keywords extracted: </span>
                {result.keywords.length > 0 ? (
                  result.keywords.map((kw) => (
                    <Badge key={kw} variant="secondary" className="mr-1">
                      {kw}
                    </Badge>
                  ))
                ) : (
                  <span className="text-muted-foreground">none</span>
                )}
              </div>
              <div>
                <span className="font-medium">Free-text phrases: </span>
                {result.free_text_phrases.map((p, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center rounded bg-primary/10 text-primary px-1.5 py-0.5 text-[11px] mr-1"
                  >
                    &quot;{p}&quot;
                  </span>
                ))}
              </div>
            </div>

            {/* CQL query */}
            <div>
              <button
                onClick={() => setShowQuery(!showQuery)}
                className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer"
              >
                <Code className="h-3.5 w-3.5" />
                {showQuery ? "Hide" : "Show"} CQL Query
                {showQuery ? (
                  <ChevronDown className="h-3 w-3" />
                ) : (
                  <ChevronRight className="h-3 w-3" />
                )}
              </button>
              {showQuery && (
                <pre className="mt-2 rounded-md border border-border bg-muted/50 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">
                  {result.cql_query}
                </pre>
              )}
            </div>

            {/* Page results */}
            {result.pages.length > 0 ? (
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Results</h4>
                {result.pages.map((page) => (
                  <PageRow key={page.page_id} page={page} />
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-border bg-muted/30 px-4 py-6 text-center text-sm text-muted-foreground">
                No Confluence pages found for the given query.
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
