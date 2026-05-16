import { useEffect, useRef, useState, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Ban,
  FileText,
  AlertTriangle,
  Terminal,
} from "lucide-react";

import { api, connectJobLogs } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import type { JobStatusResponse } from "@/types/api";

interface JobPanelProps {
  jobId: string;
  onBack: () => void;
}

const statusIcons: Record<string, React.ReactNode> = {
  pending: <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />,
  running: <Loader2 className="h-5 w-5 animate-spin text-primary" />,
  completed: <CheckCircle2 className="h-5 w-5 text-success" />,
  failed: <XCircle className="h-5 w-5 text-destructive" />,
  cancelled: <Ban className="h-5 w-5 text-warning" />,
};

const statusBadgeVariant: Record<
  string,
  "default" | "success" | "warning" | "destructive" | "secondary"
> = {
  pending: "secondary",
  running: "default",
  completed: "success",
  failed: "destructive",
  cancelled: "warning",
};

export function JobPanel({ jobId, onBack }: JobPanelProps) {
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isTerminal =
    job?.status === "completed" ||
    job?.status === "failed" ||
    job?.status === "cancelled";

  // Poll job status
  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.getJob(jobId);
      setJob(data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to fetch job status";
      // Stop polling on 404 (job lost after server restart)
      if (msg.includes("404") || msg.includes("not found") || msg.includes("Not Found")) {
        setError("Job not found — the server may have restarted. Please start a new job.");
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } else {
        setError(msg);
      }
    }
  }, [jobId]);

  useEffect(() => {
    fetchStatus();
    pollRef.current = setInterval(fetchStatus, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchStatus]);

  // Stop polling when job finishes
  useEffect(() => {
    if (isTerminal && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, [isTerminal]);

  // WebSocket logs
  useEffect(() => {
    const ws = connectJobLogs(
      jobId,
      (data) => {
        if (typeof data === "string") {
          setLogs((prev) => [...prev, data]);
        }
        // Status updates come as objects — we already poll for those
      },
      () => {
        // Connection closed
      }
    );
    wsRef.current = ws;
    return () => {
      // Only close if still open/connecting — avoids EPIPE on dead sockets
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [jobId]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  async function handleCancel() {
    try {
      await api.cancelJob(jobId);
      await fetchStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel job");
    }
  }

  if (error && !job) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <XCircle className="mx-auto mb-3 h-10 w-10 text-destructive" />
          <p className="text-destructive">{error}</p>
          <Button variant="outline" className="mt-4" onClick={onBack}>
            Go back
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!job) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <span className="ml-2 text-muted-foreground">Loading job status...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>
              <span className="flex items-center gap-2">
                {statusIcons[job.status]}
                Job {job.job_id}
              </span>
            </CardTitle>
            <Badge variant={statusBadgeVariant[job.status]}>
              {job.status.toUpperCase()}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Progress */}
          {!isTerminal && (
            <ProgressBar value={job.progress} label={job.current_step ?? "Processing"} />
          )}

          {/* Meta info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Repository</span>
              <p className="font-medium">{job.repo_url}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Mode</span>
              <p className="font-medium capitalize">{job.mode.replace("_", " ")}</p>
            </div>
            <div>
              <span className="text-muted-foreground">PRs Processed</span>
              <p className="font-medium">
                {job.processed_prs} / {job.total_prs || "—"}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Created</span>
              <p className="font-medium">
                {new Date(job.created_at).toLocaleTimeString()}
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={onBack}>
              &larr; New Job
            </Button>
            {!isTerminal && (
              <Button variant="destructive" size="sm" onClick={handleCancel}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      {job.results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Results ({job.results.length})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y divide-border">
              {job.results.map((r) => (
                <div
                  key={r.pr_number}
                  className="flex items-center justify-between py-3"
                >
                  <div>
                    <span className="font-medium">PR #{r.pr_number}</span>
                    {r.title && (
                      <span className="ml-2 text-sm text-muted-foreground">
                        {r.title}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {r.status === "completed" ? (
                      <CheckCircle2 className="h-4 w-4 text-success" />
                    ) : (
                      <XCircle className="h-4 w-4 text-destructive" />
                    )}
                    {r.summary_file && (
                      <a
                        href={`/api/jobs/${jobId}/files/${encodeURIComponent(
                          r.summary_file.split("/").pop() ?? ""
                        )}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-primary hover:underline"
                      >
                        Download
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Errors */}
      {job.errors.length > 0 && (
        <Card className="border-destructive/30">
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="h-5 w-5" />
                Errors ({job.errors.length})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {job.errors.map((e, i) => (
                <li key={i} className="rounded bg-destructive/5 p-2">
                  <span className="font-medium">{String(e.context ?? "Error")}:</span>{" "}
                  {String(e.message ?? "")}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Warnings */}
      {job.warnings.length > 0 && (
        <Card className="border-warning/30">
          <CardHeader>
            <CardTitle>
              <span className="flex items-center gap-2 text-warning">
                <AlertTriangle className="h-5 w-5" />
                Warnings ({job.warnings.length})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {job.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Live Logs */}
      <Card>
        <CardHeader>
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="flex w-full items-center justify-between cursor-pointer"
          >
            <CardTitle>
              <span className="flex items-center gap-2">
                <Terminal className="h-5 w-5" />
                Live Logs
              </span>
            </CardTitle>
            <span className="text-xs text-muted-foreground">
              {showLogs ? "Hide" : "Show"} ({logs.length} lines)
            </span>
          </button>
        </CardHeader>
        {showLogs && (
          <CardContent>
            <div className="max-h-80 overflow-y-auto rounded-md bg-foreground/5 p-3 font-mono text-xs leading-relaxed">
              {logs.length === 0 ? (
                <span className="text-muted-foreground">Waiting for logs...</span>
              ) : (
                logs.map((line, i) => (
                  <div key={i} className="whitespace-pre-wrap break-all">
                    {line}
                  </div>
                ))
              )}
              <div ref={logsEndRef} />
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
