import { z } from "zod";

export const formSchema = z
  .object({
    repo_url: z.string(),
    mode: z.enum(["latest", "label", "pr_number", "pr_urls"] as const),
    pr_number: z.string().optional(),
    label: z.string().optional(),
    pr_urls: z.string().optional(),
    max_prs: z.number().int().min(1).max(50),
    output_dir: z.string().optional(),
    verbose: z.boolean(),
  })
  .superRefine((data, ctx) => {
    // repo_url is required for all modes except pr_urls
    if (data.mode !== "pr_urls") {
      if (!data.repo_url || data.repo_url.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Repository URL is required",
          path: ["repo_url"],
        });
      } else if (
        !/^https:\/\/github\.com\/[\w.\-]+\/[\w.\-]+$/.test(data.repo_url)
      ) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message:
            "Must be a valid GitHub URL (https://github.com/owner/repo)",
          path: ["repo_url"],
        });
      }
    }
    if (data.mode === "pr_number") {
      const num = Number(data.pr_number);
      if (!data.pr_number || !Number.isInteger(num) || num < 1) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "A valid PR number is required when mode is 'Specific PR'",
          path: ["pr_number"],
        });
      }
    }
    if (data.mode === "label") {
      if (!data.label || data.label.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Label is required when mode is 'Filter by label'",
          path: ["label"],
        });
      }
    }
    if (data.mode === "pr_urls") {
      if (!data.pr_urls || data.pr_urls.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "At least one PR URL is required",
          path: ["pr_urls"],
        });
      } else {
        const urls = data.pr_urls
          .split("\n")
          .map((u) => u.trim())
          .filter((u) => u.length > 0);
        if (urls.length === 0) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "At least one PR URL is required",
            path: ["pr_urls"],
          });
        }
        const prUrlPattern =
          /^https:\/\/github\.com\/[\w.\-]+\/[\w.\-]+\/pull\/\d+$/;
        for (const url of urls) {
          if (!prUrlPattern.test(url.replace(/\/$/, ""))) {
            ctx.addIssue({
              code: z.ZodIssueCode.custom,
              message: `Invalid PR URL: ${url}. Expected format: https://github.com/owner/repo/pull/123`,
              path: ["pr_urls"],
            });
            break;
          }
        }
      }
    }
  });

export type FormValues = z.infer<typeof formSchema>;

export const defaultValues: FormValues = {
  repo_url: "",
  mode: "latest",
  pr_number: "",
  label: "",
  pr_urls: "",
  max_prs: 5,
  output_dir: "",
  verbose: false,
};
