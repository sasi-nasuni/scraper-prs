import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  GitPullRequest,
  Tag,
  Clock,
  ChevronDown,
  ChevronUp,
  Loader2,
  Link,
  Upload,
} from "lucide-react";
import { useState, useRef } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { RadioGroup } from "@/components/ui/RadioGroup";
import { formSchema, defaultValues, type FormValues } from "@/lib/schema";
import type { GenerateRequest, PRSelectionMode } from "@/types/api";

interface GenerateFormProps {
  onSubmit: (data: GenerateRequest) => void;
  isSubmitting: boolean;
}

const modeOptions = [
  {
    value: "latest" as const,
    label: "Latest merged PRs",
    description: "Process the most recently merged pull requests",
  },
  {
    value: "label" as const,
    label: "Filter by label",
    description: "Find merged PRs matching a specific GitHub label",
  },
  {
    value: "pr_number" as const,
    label: "Specific PR number",
    description: "Process a single pull request by its number",
  },
  {
    value: "pr_urls" as const,
    label: "PR URLs list",
    description: "Provide a list of GitHub PR URLs to process",
  },
];

export function GenerateForm({ onSubmit, isSubmitting }: GenerateFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  });

  const mode = watch("mode");

  function handleFormSubmit(values: FormValues) {
    // Parse PR URLs from textarea (one per line)
    const parsedPrUrls =
      values.mode === "pr_urls" && values.pr_urls
        ? values.pr_urls
            .split("\n")
            .map((u) => u.trim())
            .filter((u) => u.length > 0)
        : null;

    const payload: GenerateRequest = {
      repo_url:
        values.mode === "pr_urls"
          ? parsedPrUrls && parsedPrUrls.length > 0
            ? parsedPrUrls[0].replace(/\/pull\/\d+$/, "")
            : ""
          : values.repo_url.replace(/\/$/, ""),
      mode: values.mode as PRSelectionMode,
      max_prs:
        values.mode === "pr_number"
          ? 1
          : values.mode === "pr_urls" && parsedPrUrls
            ? parsedPrUrls.length
            : values.max_prs,
      verbose: values.verbose,
      pr_number:
        values.mode === "pr_number" && values.pr_number
          ? Number(values.pr_number)
          : null,
      label:
        values.mode === "label" && values.label ? values.label : null,
      pr_urls: parsedPrUrls,
      output_dir: values.output_dir || null,
    };
    onSubmit(payload);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <span className="flex items-center gap-2">
            <GitPullRequest className="h-5 w-5 text-primary" />
            Generate PR Summaries
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
          {/* Repository URL (hidden for pr_urls mode) */}
          {mode !== "pr_urls" && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                Repository URL <span className="text-destructive">*</span>
              </label>
              <Input
                placeholder="https://github.com/owner/repo"
                {...register("repo_url")}
                error={errors.repo_url?.message}
              />
            </div>
          )}

          {/* PR Selection Mode */}
          <div>
            <label className="mb-1.5 block text-sm font-medium">
              PR Selection Mode
            </label>
            <RadioGroup
              name="mode"
              options={modeOptions}
              value={mode}
              onChange={(v) => setValue("mode", v, { shouldValidate: true })}
            />
          </div>

          {/* Conditional: Label */}
          {mode === "label" && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                <Tag className="mr-1 inline h-4 w-4" />
                GitHub Label <span className="text-destructive">*</span>
              </label>
              <Input
                placeholder='e.g. "[PM-1587] NOTIFICATION EPIC"'
                {...register("label")}
                error={errors.label?.message}
              />
            </div>
          )}

          {/* Conditional: PR Number */}
          {mode === "pr_number" && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                <GitPullRequest className="mr-1 inline h-4 w-4" />
                PR Number <span className="text-destructive">*</span>
              </label>
              <Input
                type="number"
                min={1}
                placeholder="e.g. 1449"
                {...register("pr_number")}
                error={errors.pr_number?.message}
              />
            </div>
          )}

          {/* Conditional: PR URLs */}
          {mode === "pr_urls" && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                <Link className="mr-1 inline h-4 w-4" />
                PR URLs <span className="text-destructive">*</span>
              </label>
              <textarea
                className="flex min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder={"https://github.com/owner/repo/pull/123\nhttps://github.com/owner/repo/pull/456\nhttps://github.com/other-owner/other-repo/pull/789"}
                {...register("pr_urls")}
              />
              {errors.pr_urls?.message && (
                <p className="mt-1 text-sm text-destructive">
                  {errors.pr_urls.message}
                </p>
              )}
              <div className="mt-2 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/50 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Upload file
                </button>
                <span className="text-xs text-muted-foreground">
                  or enter URLs manually above (one per line)
                </span>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.csv,.text"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  const reader = new FileReader();
                  reader.onload = (evt) => {
                    const text = evt.target?.result as string;
                    const currentVal = watch("pr_urls") || "";
                    const newVal = currentVal
                      ? currentVal.trimEnd() + "\n" + text.trim()
                      : text.trim();
                    setValue("pr_urls", newVal, { shouldValidate: true });
                  };
                  reader.readAsText(file);
                  // Reset input so the same file can be re-uploaded
                  e.target.value = "";
                }}
              />
            </div>
          )}

          {/* Max PRs (hidden for specific PR mode and pr_urls mode) */}
          {mode !== "pr_number" && mode !== "pr_urls" && (
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                <Clock className="mr-1 inline h-4 w-4" />
                Max PRs to process
              </label>
              <Input
                type="number"
                min={1}
                max={50}
                {...register("max_prs", { valueAsNumber: true })}
                error={errors.max_prs?.message}
              />
            </div>
          )}

          {/* Advanced options */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
            >
              {showAdvanced ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
              Advanced options
            </button>

            {showAdvanced && (
              <div className="mt-3 space-y-4 rounded-md border border-border bg-muted/30 p-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Output directory
                  </label>
                  <Input
                    placeholder="outputs (default)"
                    {...register("output_dir")}
                  />
                </div>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    {...register("verbose")}
                    className="h-4 w-4 accent-primary"
                  />
                  Enable verbose/debug logging
                </label>
              </div>
            )}
          </div>

          {/* Submit */}
          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full"
            size="lg"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Submitting...
              </>
            ) : (
              "Generate Summaries"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
