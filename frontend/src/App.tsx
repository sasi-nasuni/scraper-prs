import { useState, useCallback } from "react";
import { GitPullRequest, Wrench, Settings, Search, Workflow } from "lucide-react";

import { api } from "@/lib/api";
import { GenerateForm } from "@/components/GenerateForm";
import { JobPanel } from "@/components/JobPanel";
import { JobHistory } from "@/components/JobHistory";
import { ToolExplorer } from "@/components/ToolExplorer";
import { ConfigEditor } from "@/components/ConfigEditor";
import { ConfluenceTestPanel } from "@/components/ConfluenceTestPanel";
import { PipelineGraph } from "@/components/PipelineGraph";
import type { GenerateRequest } from "@/types/api";

type Page = "summary" | "tools" | "pipeline" | "confluence" | "config";
type View = { kind: "form" } | { kind: "job"; jobId: string };

function App() {
  const [page, setPage] = useState<Page>("summary");
  const [view, setView] = useState<View>({ kind: "form" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const handleSubmit = useCallback(async (data: GenerateRequest) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const res = await api.createJob(data);
      setRefreshTick((t) => t + 1);
      setView({ kind: "job", jobId: res.job_id });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const handleBack = useCallback(() => {
    setView({ kind: "form" });
    setRefreshTick((t) => t + 1);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <div className="flex items-center gap-3">
            <GitPullRequest className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-lg font-bold">PR Summary Agent</h1>
              <p className="text-xs text-muted-foreground">
                Generate comprehensive PR summaries with AI
              </p>
            </div>
          </div>

          {/* Navigation tabs */}
          <nav className="flex items-center gap-1 rounded-lg border border-border bg-muted/30 p-1">
            <button
              onClick={() => setPage("summary")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                page === "summary"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <GitPullRequest className="h-3.5 w-3.5" />
              Summaries
            </button>
            <button
              onClick={() => setPage("tools")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                page === "tools"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Wrench className="h-3.5 w-3.5" />
              MCP Tools
            </button>
            <button
              onClick={() => setPage("pipeline")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                page === "pipeline"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Workflow className="h-3.5 w-3.5" />
              Pipeline
            </button>
            <button
              onClick={() => setPage("config")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                page === "config"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Settings className="h-3.5 w-3.5" />
              Config
            </button>
            <button
              onClick={() => setPage("confluence")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                page === "confluence"
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Search className="h-3.5 w-3.5" />
              Confluence
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className={`mx-auto px-4 py-8 space-y-6 ${page === "summary" ? "max-w-3xl" : page === "pipeline" ? "max-w-6xl" : "max-w-5xl"}`}>
        {page === "summary" ? (
          <>
            {view.kind === "form" ? (
              <>
                <GenerateForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />

                {submitError && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                    {submitError}
                  </div>
                )}

                <JobHistory
                  onSelectJob={(id) => setView({ kind: "job", jobId: id })}
                  refreshTick={refreshTick}
                />
              </>
            ) : (
              <JobPanel jobId={view.jobId} onBack={handleBack} />
            )}
          </>
        ) : page === "tools" ? (
          <ToolExplorer />
        ) : page === "pipeline" ? (
          <PipelineGraph />
        ) : page === "confluence" ? (
          <ConfluenceTestPanel />
        ) : (
          <ConfigEditor />
        )}
      </main>
    </div>
  );
}

export default App;
