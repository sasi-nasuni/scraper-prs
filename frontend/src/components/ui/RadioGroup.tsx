import { cn } from "@/lib/utils";

interface RadioOption<T extends string> {
  value: T;
  label: string;
  description?: string;
}

interface RadioGroupProps<T extends string> {
  name: string;
  options: RadioOption<T>[];
  value: T;
  onChange: (value: T) => void;
  className?: string;
}

export function RadioGroup<T extends string>({
  name,
  options,
  value,
  onChange,
  className,
}: RadioGroupProps<T>) {
  return (
    <div className={cn("space-y-2", className)}>
      {options.map((opt) => (
        <label
          key={opt.value}
          className={cn(
            "flex items-start gap-3 rounded-md border p-3 cursor-pointer transition-colors",
            value === opt.value
              ? "border-primary bg-primary/5"
              : "border-border hover:bg-accent/50"
          )}
        >
          <input
            type="radio"
            name={name}
            value={opt.value}
            checked={value === opt.value}
            onChange={() => onChange(opt.value)}
            className="mt-0.5 h-4 w-4 accent-primary"
          />
          <div>
            <div className="text-sm font-medium">{opt.label}</div>
            {opt.description && (
              <div className="text-xs text-muted-foreground">
                {opt.description}
              </div>
            )}
          </div>
        </label>
      ))}
    </div>
  );
}
