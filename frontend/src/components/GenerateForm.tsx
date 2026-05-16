import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  GitPullRequest,
  Tag,
  Clock,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { useState } from "react";

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
];

export function GenerateForm({ onSubmit, isSubmitting }: GenerateFormProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

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
    const payload: GenerateRequest = {
      repo_url: values.repo_url.replace(/\/$/, ""),
      mode: values.mode as PRSelectionMode,
      max_prs: values.mode === "pr_number" ? 1 : values.max_prs,
      verbose: values.verbose,
      pr_number:
        values.mode === "pr_number" && values.pr_number
          ? Number(values.pr_number)
          : null,
      label:
        values.mode === "label" && values.label ? values.label : null,
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
          {/* Repository URL */}
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

          {/* Max PRs (hidden for specific PR mode) */}
          {mode !== "pr_number" && (
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
