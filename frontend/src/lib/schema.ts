import { z } from "zod";

export const formSchema = z
  .object({
    repo_url: z
      .string()
      .min(1, "Repository URL is required")
      .regex(
        /^https:\/\/github\.com\/[\w.\-]+\/[\w.\-]+$/,
        "Must be a valid GitHub URL (https://github.com/owner/repo)"
      ),
    mode: z.enum(["latest", "label", "pr_number"] as const),
    pr_number: z.union([z.coerce.number().int().positive(), z.literal("")]).optional(),
    label: z.string().optional(),
    max_prs: z.coerce.number().int().min(1).max(50),
    output_dir: z.string().optional(),
    verbose: z.boolean(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "pr_number") {
      if (!data.pr_number) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "PR number is required when mode is 'Specific PR'",
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
  });

export type FormValues = z.infer<typeof formSchema>;

export const defaultValues: FormValues = {
  repo_url: "",
  mode: "latest",
  pr_number: "",
  label: "",
  max_prs: 5,
  output_dir: "",
  verbose: false,
};
