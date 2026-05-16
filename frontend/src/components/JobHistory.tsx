import { useEffect, useState } from "react";
import { Clock, CheckCircle2, XCircle, Loader2, Ban } from "lucide-react";

import { api } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { JobStatusResponse } from "@/types/api";

interface JobHistoryProps {
  onSelectJob: (jobId: string) => void;
  refreshTick: number; // increment to trigger refresh
}

const statusIcon: Record<string, React.ReactNode> = {
  pending: <Clock className="h-4 w-4 text-muted-foreground" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  completed: <CheckCircle2 className="h-4 w-4 text-success" />,
  failed: <XCircle className="h-4 w-4 text-destructive" />,
  cancelled: <Ban className="h-4 w-4 text-warning" />,
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

export function JobHistory({ onSelectJob, refreshTick }: JobHistoryProps) {
  const [jobs, setJobs] = useState<JobStatusResponse[]>([]);

  useEffect(() => {
    api.listJobs().then((data) => setJobs(data.jobs)).catch(() => {});
  }, [refreshTick]);

  if (jobs.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Recent Jobs
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="divide-y divide-border">
          {jobs.slice(0, 10).map((j) => (
            <button
              key={j.job_id}
              onClick={() => onSelectJob(j.job_id)}
              className="flex w-full items-center justify-between py-3 text-left hover:bg-accent/50 px-2 -mx-2 rounded transition-colors cursor-pointer"
            >
              <div className="flex items-center gap-2">
                {statusIcon[j.status]}
                <div>
                  <span className="text-sm font-medium">
                    {j.repo_url.replace("https://github.com/", "")}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    ({j.mode.replace("_", " ")})
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={statusBadgeVariant[j.status]} className="text-xs">
                  {j.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(j.created_at).toLocaleTimeString()}
                </span>
              </div>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
