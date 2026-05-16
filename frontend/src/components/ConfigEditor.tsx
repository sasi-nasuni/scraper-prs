import { useCallback, useEffect, useState } from "react";
import {
  Settings,
  Loader2,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Info,
} from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type {
  AgentConfig,
  AgentConfigWithMeta,
  ConfigPriorityInfo,
} from "@/types/api";

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Deep-clone a plain JSON object. */
function clone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/** Check shallow-deep equality of two plain JSON values. */
function isEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

// ── Tiny Toggle Component ───────────────────────────────────────────────────

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors
        ${checked ? "bg-primary" : "bg-muted"}
        ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
    >
      <span
        className={`pointer-events-none block h-4 w-4 rounded-full bg-white shadow-md transition-transform
          ${checked ? "translate-x-5" : "translate-x-1"}`}
      />
    </button>
  );
}

// ── Collapsible Section ─────────────────────────────────────────────────────

function Section({
  title,
  defaultOpen = false,
  children,
  badge,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  badge?: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-border rounded-lg">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold hover:bg-muted/30 transition-colors cursor-pointer"
      >
        <span className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          {title}
        </span>
        {badge}
      </button>
      {open && <div className="px-4 pb-4 space-y-3">{children}</div>}
    </div>
  );
}

// ── Field Row ───────────────────────────────────────────────────────────────

function FieldRow({
  label,
  description,
  overrideInfo,
  children,
}: {
  label: string;
  description?: string;
  overrideInfo?: ConfigPriorityInfo;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto] gap-3 items-start">
      <div className="space-y-0.5">
        <label className="text-sm font-medium flex items-center gap-2">
          {label}
          {overrideInfo && overrideInfo.active_source === "env" && (
            <Badge variant="warning">
              ENV: {overrideInfo.env_var}={overrideInfo.env_value}
            </Badge>
          )}
        </label>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="min-w-[220px]">{children}</div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────────────────

export function ConfigEditor() {
  const [meta, setMeta] = useState<AgentConfigWithMeta | null>(null);
  const [draft, setDraft] = useState<AgentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  // Fetch config on mount
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getConfig();
      setMeta(res);
      setDraft(clone(res.config));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Dirty check
  const isDirty = meta && draft ? !isEqual(meta.config, draft) : false;

  // Save handler — only sends changed sections
  const handleSave = useCallback(async () => {
    if (!meta || !draft) return;
    setSaving(true);
    setError(null);
    setSaveMsg(null);
    try {
      // Build a partial payload containing only sections that changed
      const patch: Partial<AgentConfig> = {};
      const sections = Object.keys(draft) as (keyof AgentConfig)[];
      for (const key of sections) {
        if (!isEqual(meta.config[key], draft[key])) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (patch as any)[key] = draft[key];
        }
      }
      if (Object.keys(patch).length === 0) {
        setSaveMsg("No changes to save");
        return;
      }
      const res = await api.updateConfig(patch);
      setMeta(res);
      setDraft(clone(res.config));
      setSaveMsg("Config saved successfully");
      setTimeout(() => setSaveMsg(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save config");
    } finally {
      setSaving(false);
    }
  }, [meta, draft]);

  // Helper to find override info for a dotted key
  const getOverride = (key: string): ConfigPriorityInfo | undefined =>
    meta?.overrides.find((o) => o.key === key);

  // Setters that update draft in-place
  const set = <S extends keyof AgentConfig>(
    section: S,
    field: string,
    value: unknown,
  ) => {
    setDraft((prev) => {
      if (!prev) return prev;
      const next = clone(prev);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (next[section] as any)[field] = value;
      return next;
    });
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-16 gap-3 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading configuration…
        </CardContent>
      </Card>
    );
  }

  if (error && !draft) {
    return (
      <Card>
        <CardContent className="py-10 text-center space-y-3">
          <p className="text-destructive">{error}</p>
          <Button onClick={fetchConfig} variant="outline">
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!draft) return null;

  const envOverrides = meta?.overrides.filter((o) => o.active_source === "env") ?? [];

  return (
    <div className="space-y-5">
      {/* Header card */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-primary" />
              Agent Configuration
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-muted-foreground -mt-2">
            Edit the agent&apos;s <code className="text-foreground">config/agent_config.yaml</code> file.
            Changes are persisted to disk immediately.
          </p>

          {/* Priority info banner */}
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs space-y-1">
            <p className="font-semibold flex items-center gap-1.5">
              <Info className="h-3.5 w-3.5 text-primary" /> Config Priority
              Order (highest wins):
            </p>
            <ol className="list-decimal ml-5 space-y-0.5 text-muted-foreground">
              <li>CLI / API request parameters (per-job overrides)</li>
              <li>
                Environment variables{" "}
                {envOverrides.length > 0 && (
                  <Badge variant="warning">{envOverrides.length} active</Badge>
                )}
              </li>
              <li>
                <strong className="text-foreground">
                  YAML file (what you edit here)
                </strong>
              </li>
            </ol>
          </div>

          {/* Env override warnings */}
          {envOverrides.length > 0 && (
            <div className="rounded-md border border-warning/30 bg-warning/5 p-3 text-xs space-y-1">
              <p className="font-semibold flex items-center gap-1.5 text-warning">
                <AlertTriangle className="h-3.5 w-3.5" /> Active Environment
                Overrides
              </p>
              <p className="text-muted-foreground">
                These env vars override the YAML values at runtime:
              </p>
              <ul className="ml-4 list-disc text-muted-foreground space-y-0.5">
                {envOverrides.map((o) => (
                  <li key={o.key}>
                    <code className="text-foreground">{o.env_var}</code> ={" "}
                    <code className="text-warning">{o.env_value}</code>{" "}
                    <span className="text-muted-foreground">
                      (YAML: {String(o.yaml_value ?? "–")})
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action bar */}
          <div className="flex items-center gap-3">
            <Button onClick={handleSave} disabled={saving || !isDirty}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Saving…
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" /> Save Changes
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={fetchConfig}
              disabled={loading}
            >
              <RefreshCw className="h-4 w-4" /> Reload
            </Button>
            {isDirty && (
              <Badge variant="warning">Unsaved changes</Badge>
            )}
            {saveMsg && (
              <span className="flex items-center gap-1 text-xs text-success">
                <CheckCircle2 className="h-3.5 w-3.5" /> {saveMsg}
              </span>
            )}
            {error && (
              <span className="text-xs text-destructive">{error}</span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── LLM Section ──────────────────────────────────────────────── */}
      <Section title="LLM Settings" defaultOpen>
        <FieldRow
          label="Provider"
          description="openai or anthropic"
          overrideInfo={getOverride("llm.provider")}
        >
          <select
            value={draft.llm.provider}
            onChange={(e) => set("llm", "provider", e.target.value)}
            className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm"
          >
            <option value="openai">openai</option>
            <option value="anthropic">anthropic</option>
          </select>
        </FieldRow>

        <FieldRow
          label="Model"
          description="e.g. gpt-4.1, gpt-4o, claude-sonnet-4-20250514"
          overrideInfo={getOverride("llm.model")}
        >
          <Input
            value={draft.llm.model}
            onChange={(e) => set("llm", "model", e.target.value)}
          />
        </FieldRow>

        <FieldRow
          label="Temperature"
          description="0.0 = focused, 1.0 = creative"
          overrideInfo={getOverride("llm.temperature")}
        >
          <Input
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={draft.llm.temperature}
            onChange={(e) =>
              set("llm", "temperature", parseFloat(e.target.value) || 0)
            }
          />
        </FieldRow>

        <FieldRow
          label="Max Tokens"
          overrideInfo={getOverride("llm.max_tokens")}
        >
          <Input
            type="number"
            min="1"
            value={draft.llm.max_tokens}
            onChange={(e) =>
              set("llm", "max_tokens", parseInt(e.target.value) || 4096)
            }
          />
        </FieldRow>

        <FieldRow label="Streaming">
          <Toggle
            checked={draft.llm.streaming}
            onChange={(v) => set("llm", "streaming", v)}
          />
        </FieldRow>

        <FieldRow
          label="Base URL"
          description="Custom endpoint (e.g. GitHub Models)"
          overrideInfo={getOverride("llm.base_url")}
        >
          <Input
            value={draft.llm.base_url ?? ""}
            placeholder="https://..."
            onChange={(e) =>
              set("llm", "base_url", e.target.value || null)
            }
          />
        </FieldRow>
      </Section>

      {/* ── Processing Section ───────────────────────────────────────── */}
      <Section title="Processing">
        <FieldRow
          label="Max PRs"
          description="Max PRs to process per run"
          overrideInfo={getOverride("processing.max_prs")}
        >
          <Input
            type="number"
            min="1"
            max="50"
            value={draft.processing.max_prs}
            onChange={(e) =>
              set("processing", "max_prs", parseInt(e.target.value) || 5)
            }
          />
        </FieldRow>

        <FieldRow label="Enable Parallel" description="Process PRs in parallel">
          <Toggle
            checked={draft.processing.enable_parallel}
            onChange={(v) => set("processing", "enable_parallel", v)}
          />
        </FieldRow>

        <FieldRow label="Parallel Workers">
          <Input
            type="number"
            min="1"
            max="10"
            value={draft.processing.parallel_workers}
            onChange={(e) =>
              set(
                "processing",
                "parallel_workers",
                parseInt(e.target.value) || 3,
              )
            }
          />
        </FieldRow>

        <FieldRow
          label="Timeout per PR"
          description="Seconds before giving up on a single PR"
        >
          <Input
            type="number"
            min="30"
            value={draft.processing.timeout_per_pr}
            onChange={(e) =>
              set(
                "processing",
                "timeout_per_pr",
                parseInt(e.target.value) || 300,
              )
            }
          />
        </FieldRow>
      </Section>

      {/* ── Templates Section ────────────────────────────────────────── */}
      <Section title="Templates">
        <FieldRow label="Main Template">
          <Input
            value={draft.templates.main_template}
            onChange={(e) =>
              set("templates", "main_template", e.target.value)
            }
          />
        </FieldRow>
        <FieldRow label="Fallback Template">
          <Input
            value={draft.templates.fallback_template}
            onChange={(e) =>
              set("templates", "fallback_template", e.target.value)
            }
          />
        </FieldRow>
        <FieldRow label="Use Fallback When Missing">
          <Toggle
            checked={draft.templates.use_fallback_when_missing}
            onChange={(v) =>
              set("templates", "use_fallback_when_missing", v)
            }
          />
        </FieldRow>
      </Section>

      {/* ── Extraction Section ───────────────────────────────────────── */}
      <Section title="Extraction">
        <p className="text-xs font-medium text-muted-foreground">Jira</p>
        <FieldRow label="Pattern" description="Regex for Jira ticket IDs">
          <Input
            value={draft.extraction.jira.pattern}
            onChange={(e) =>
              setDraft((p) => {
                if (!p) return p;
                const n = clone(p);
                n.extraction.jira.pattern = e.target.value;
                return n;
              })
            }
          />
        </FieldRow>
        <FieldRow label="Search In" description="Comma-separated list">
          <Input
            value={draft.extraction.jira.search_in.join(", ")}
            onChange={(e) =>
              setDraft((p) => {
                if (!p) return p;
                const n = clone(p);
                n.extraction.jira.search_in = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean);
                return n;
              })
            }
          />
        </FieldRow>

        <hr className="border-border" />
        <p className="text-xs font-medium text-muted-foreground">Figma</p>
        <FieldRow label="Patterns" description="One regex per line">
          <textarea
            value={draft.extraction.figma.patterns.join("\n")}
            rows={3}
            onChange={(e) =>
              setDraft((p) => {
                if (!p) return p;
                const n = clone(p);
                n.extraction.figma.patterns = e.target.value
                  .split("\n")
                  .map((s) => s.trim())
                  .filter(Boolean);
                return n;
              })
            }
            className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm font-mono"
          />
        </FieldRow>

        <hr className="border-border" />
        <p className="text-xs font-medium text-muted-foreground">Confluence</p>
        <FieldRow
          label="Strategies"
          description="Comma-separated search strategies"
        >
          <Input
            value={draft.extraction.confluence.strategies.join(", ")}
            onChange={(e) =>
              setDraft((p) => {
                if (!p) return p;
                const n = clone(p);
                n.extraction.confluence.strategies = e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean);
                return n;
              })
            }
          />
        </FieldRow>
        <FieldRow label="Max Pages per PR">
          <Input
            type="number"
            min="1"
            max="20"
            value={draft.extraction.confluence.max_pages_per_pr}
            onChange={(e) =>
              setDraft((p) => {
                if (!p) return p;
                const n = clone(p);
                n.extraction.confluence.max_pages_per_pr =
                  parseInt(e.target.value) || 3;
                return n;
              })
            }
          />
        </FieldRow>
      </Section>

      {/* ── Retry Section ────────────────────────────────────────────── */}
      <Section title="Retry / Backoff">
        <FieldRow
          label="Max Attempts"
          description="1 = no retries"
        >
          <Input
            type="number"
            min="1"
            max="10"
            value={draft.retry.max_attempts}
            onChange={(e) =>
              set("retry", "max_attempts", parseInt(e.target.value) || 1)
            }
          />
        </FieldRow>
        <FieldRow label="Initial Delay (s)">
          <Input
            type="number"
            min="1"
            value={draft.retry.initial_delay}
            onChange={(e) =>
              set("retry", "initial_delay", parseInt(e.target.value) || 2)
            }
          />
        </FieldRow>
        <FieldRow label="Max Delay (s)">
          <Input
            type="number"
            min="1"
            value={draft.retry.max_delay}
            onChange={(e) =>
              set("retry", "max_delay", parseInt(e.target.value) || 30)
            }
          />
        </FieldRow>
        <FieldRow label="Exponential Base">
          <Input
            type="number"
            min="2"
            max="5"
            value={draft.retry.exponential_base}
            onChange={(e) =>
              set(
                "retry",
                "exponential_base",
                parseInt(e.target.value) || 2,
              )
            }
          />
        </FieldRow>
      </Section>

      {/* ── Error Handling Section ───────────────────────────────────── */}
      <Section title="Error Handling">
        <FieldRow
          label="Continue on Error"
          description="Keep processing remaining PRs if one fails"
        >
          <Toggle
            checked={draft.error_handling.continue_on_error}
            onChange={(v) => set("error_handling", "continue_on_error", v)}
          />
        </FieldRow>
        <FieldRow
          label="Partial Summaries"
          description="Generate summaries even without Jira/Figma"
        >
          <Toggle
            checked={draft.error_handling.generate_partial_summaries}
            onChange={(v) =>
              set("error_handling", "generate_partial_summaries", v)
            }
          />
        </FieldRow>
        <FieldRow label="Log Errors">
          <Toggle
            checked={draft.error_handling.log_errors}
            onChange={(v) => set("error_handling", "log_errors", v)}
          />
        </FieldRow>
        <FieldRow
          label="Include Errors in Summary"
          description="Append error details to generated markdown"
        >
          <Toggle
            checked={draft.error_handling.include_errors_in_summary}
            onChange={(v) =>
              set("error_handling", "include_errors_in_summary", v)
            }
          />
        </FieldRow>
      </Section>

      {/* ── Output Section ───────────────────────────────────────────── */}
      <Section title="Output">
        <FieldRow
          label="Directory"
          overrideInfo={getOverride("output.directory")}
        >
          <Input
            value={draft.output.directory}
            onChange={(e) => set("output", "directory", e.target.value)}
          />
        </FieldRow>
        <FieldRow label="Filename Pattern">
          <Input
            value={draft.output.filename_pattern}
            onChange={(e) =>
              set("output", "filename_pattern", e.target.value)
            }
          />
        </FieldRow>
        <FieldRow label="Overwrite Existing">
          <Toggle
            checked={draft.output.overwrite_existing}
            onChange={(v) => set("output", "overwrite_existing", v)}
          />
        </FieldRow>
        <FieldRow label="Include Metadata">
          <Toggle
            checked={draft.output.include_metadata}
            onChange={(v) => set("output", "include_metadata", v)}
          />
        </FieldRow>
      </Section>

      {/* ── Logging Section ──────────────────────────────────────────── */}
      <Section title="Logging">
        <FieldRow
          label="Level"
          overrideInfo={getOverride("logging.level")}
        >
          <select
            value={draft.logging.level}
            onChange={(e) => set("logging", "level", e.target.value)}
            className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm"
          >
            {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
        </FieldRow>
        <FieldRow label="Console Output">
          <Toggle
            checked={draft.logging.console}
            onChange={(v) => set("logging", "console", v)}
          />
        </FieldRow>
        <FieldRow label="File Output">
          <Toggle
            checked={draft.logging.file}
            onChange={(v) => set("logging", "file", v)}
          />
        </FieldRow>
        <FieldRow
          label="File Path"
          overrideInfo={getOverride("logging.file_path")}
        >
          <Input
            value={draft.logging.file_path}
            onChange={(e) => set("logging", "file_path", e.target.value)}
          />
        </FieldRow>
      </Section>

      {/* ── Rate Limits Section ──────────────────────────────────────── */}
      <Section title="Rate Limits">
        {(["github", "jira", "confluence"] as const).map((svc) => (
          <div key={svc} className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground capitalize">
              {svc}
            </p>
            <div className="grid grid-cols-3 gap-3">
              {svc === "github" ? (
                <div>
                  <label className="text-xs text-muted-foreground">
                    Requests / hour
                  </label>
                  <Input
                    type="number"
                    min="0"
                    value={draft.rate_limits[svc].requests_per_hour ?? ""}
                    onChange={(e) =>
                      setDraft((p) => {
                        if (!p) return p;
                        const n = clone(p);
                        n.rate_limits[svc].requests_per_hour =
                          parseInt(e.target.value) || null;
                        return n;
                      })
                    }
                  />
                </div>
              ) : (
                <div>
                  <label className="text-xs text-muted-foreground">
                    Requests / minute
                  </label>
                  <Input
                    type="number"
                    min="0"
                    value={draft.rate_limits[svc].requests_per_minute ?? ""}
                    onChange={(e) =>
                      setDraft((p) => {
                        if (!p) return p;
                        const n = clone(p);
                        n.rate_limits[svc].requests_per_minute =
                          parseInt(e.target.value) || null;
                        return n;
                      })
                    }
                  />
                </div>
              )}
              <div>
                <label className="text-xs text-muted-foreground">
                  Min delay (s)
                </label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  value={draft.rate_limits[svc].min_delay_between_requests}
                  onChange={(e) =>
                    setDraft((p) => {
                      if (!p) return p;
                      const n = clone(p);
                      n.rate_limits[svc].min_delay_between_requests =
                        parseFloat(e.target.value) || 0;
                      return n;
                    })
                  }
                />
              </div>
            </div>
            {svc !== "confluence" && <hr className="border-border" />}
          </div>
        ))}
      </Section>

      {/* Bottom save bar */}
      {isDirty && (
        <div className="sticky bottom-4 flex justify-end">
          <Button onClick={handleSave} disabled={saving} className="shadow-lg">
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Saving…
              </>
            ) : (
              <>
                <Save className="h-4 w-4" /> Save Changes
              </>
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
