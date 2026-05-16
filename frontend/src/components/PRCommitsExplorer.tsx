import { useState, useCallback } from "react";
import { GitCommitHorizontal, Play, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ResultViewer } from "@/components/ResultViewer";
import type { GitHubPRCommitsResponse } from "@/types/api";

export function PRCommitsExplorer() {
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [prNumber, setPrNumber] = useState("");
  const [page, setPage] = useState("");
  const [perPage, setPerPage] = useState("100");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GitHubPRCommitsResponse | null>(null);

  const handleFetch = useCallback(async () => {
    if (!owner.trim() || !repo.trim() || !prNumber.trim()) {
      setError("Owner, repo, and PR number are required");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.fetchPRCommits({
        owner: owner.trim(),
        repo: repo.trim(),
        pull_number: Number(prNumber),
        page: page.trim() ? Number(page) : undefined,
        per_page: Number(perPage) || 100,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch commits");
    } finally {
      setLoading(false);
    }
  }, [owner, repo, prNumber, page, perPage]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="flex items-center gap-2">
            <GitCommitHorizontal className="h-5 w-5 text-primary" />
            Fetch PR Commits (Direct GitHub API)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <p className="text-xs text-muted-foreground -mt-2">
          Fetches commits for a pull request directly from GitHub REST API with
          full pagination. The official GitHub MCP server only exposes
          repo-level commits, not PR-specific ones.
        </p>

        {/* Form */}
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">
              Owner <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="e.g. facebook"
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              Repo <span className="text-destructive">*</span>
            </label>
            <Input
              placeholder="e.g. react"
              value={repo}
              onChange={(e) => setRepo(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">
              PR # <span className="text-destructive">*</span>
            </label>
            <Input
              type="number"
              placeholder="1234"
              value={prNumber}
              onChange={(e) => setPrNumber(e.target.value)}
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">
              Page{" "}
              <span className="text-muted-foreground font-normal">
                (blank = all)
              </span>
            </label>
            <Input
              type="number"
              placeholder="All pages"
              value={page}
              onChange={(e) => setPage(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Per Page</label>
            <Input
              type="number"
              placeholder="100"
              value={perPage}
              onChange={(e) => setPerPage(e.target.value)}
            />
          </div>
        </div>

        <Button onClick={handleFetch} disabled={loading} className="w-full">
          {loading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Fetching...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Fetch Commits
            </>
          )}
        </Button>

        {/* Error */}
        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <ResultViewer
            success
            result={result.commits}
            durationMs={result.duration_ms}
            infoBadges={[
              `${result.total_count} commits`,
              ...(result.total_pages_fetched
                ? [`${result.total_pages_fetched} pages fetched`]
                : []),
            ]}
          />
        )}
      </CardContent>
    </Card>
  );
}
