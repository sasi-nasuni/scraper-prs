import { useState, useMemo, useCallback, useRef } from "react";
import {
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  Clock,
  Filter,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface ResultViewerProps {
  success: boolean;
  result?: unknown;
  error?: string | null;
  durationMs?: number | null;
  /** Extra info badges to show in the header (e.g. "45 comments") */
  infoBadges?: string[];
}

/**
 * Try to parse a value into a JS object/array.
 * Returns the parsed value if it's an array of objects, else null.
 */
function parseAsArrayOfObjects(
  value: unknown
): Record<string, unknown>[] | null {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      return null;
    }
  }
  if (
    Array.isArray(parsed) &&
    parsed.length > 0 &&
    typeof parsed[0] === "object" &&
    parsed[0] !== null
  ) {
    return parsed as Record<string, unknown>[];
  }
  return null;
}

/**
 * Try to parse a value into a single plain object (non-array) with at least 2 keys.
 * Returns the parsed object if it qualifies, else null.
 */
function parseAsSingleObject(
  value: unknown
): Record<string, unknown> | null {
  let parsed = value;
  if (typeof parsed === "string") {
    try {
      parsed = JSON.parse(parsed);
    } catch {
      return null;
    }
  }
  if (
    parsed !== null &&
    typeof parsed === "object" &&
    !Array.isArray(parsed) &&
    Object.keys(parsed as Record<string, unknown>).length >= 2
  ) {
    return parsed as Record<string, unknown>;
  }
  return null;
}

/**
 * Check whether a value is a plain object (not an array, null, Date, etc.).
 */
function isPlainObject(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/**
 * Check if a value is an array of plain objects (at least one element).
 */
function isArrayOfObjects(
  v: unknown
): v is Record<string, unknown>[] {
  return (
    Array.isArray(v) &&
    v.length > 0 &&
    v.some((el) => isPlainObject(el))
  );
}

/**
 * Structured key entry: top-level keys + their sub-keys (one level deep).
 * `subKeys` is non-empty when the value is a plain object OR an array of
 * plain objects.
 */
interface KeyEntry {
  key: string;
  subKeys: string[];
}

/**
 * Extract top-level keys and, for values that are plain objects **or arrays
 * of plain objects** (across all items), their one-level-deep sub-keys.
 *
 * Returns a *flat* sorted list of dot-notation paths (e.g.
 * `["body", "files", "files.path", "pr", "pr.number", "pr.title"]`)
 * plus a structured list grouped by parent for the dropdown UI.
 */
function extractKeysStructured(
  items: Record<string, unknown>[]
): { flat: string[]; structured: KeyEntry[] } {
  const topKeys = new Set<string>();
  const subKeysMap = new Map<string, Set<string>>();

  for (const item of items) {
    for (const key of Object.keys(item)) {
      topKeys.add(key);
      const val = item[key];

      if (isPlainObject(val)) {
        // Plain object → collect its keys
        if (!subKeysMap.has(key)) subKeysMap.set(key, new Set());
        const set = subKeysMap.get(key)!;
        for (const sk of Object.keys(val)) set.add(sk);
      } else if (isArrayOfObjects(val)) {
        // Array of objects → union of keys across all elements
        if (!subKeysMap.has(key)) subKeysMap.set(key, new Set());
        const set = subKeysMap.get(key)!;
        for (const elem of val) {
          if (isPlainObject(elem)) {
            for (const sk of Object.keys(elem)) set.add(sk);
          }
        }
      }
    }
  }

  const structured: KeyEntry[] = Array.from(topKeys)
    .sort()
    .map((key) => ({
      key,
      subKeys: subKeysMap.has(key)
        ? Array.from(subKeysMap.get(key)!).sort()
        : [],
    }));

  const flat: string[] = [];
  for (const entry of structured) {
    flat.push(entry.key);
    for (const sk of entry.subKeys) flat.push(`${entry.key}.${sk}`);
  }

  return { flat, structured };
}

/**
 * Given a set of selected keys (which may include dot-notation paths like
 * `pr.title`), filter a single object.
 *
 * Rules:
 *  - Selecting a top-level key includes its entire value.
 *  - Selecting `parent.child` includes `parent` but only with the chosen
 *    sub-keys.  If the user also selects the bare `parent`, the entire
 *    object is kept (top-level wins).
 */
function filterObjectByKeys(
  obj: Record<string, unknown>,
  keys: Set<string>
): Record<string, unknown> {
  // Partition selected keys into top-level vs sub-paths
  const topLevel = new Set<string>();
  const subPaths = new Map<string, Set<string>>(); // parent → child set

  for (const k of keys) {
    const dot = k.indexOf(".");
    if (dot === -1) {
      topLevel.add(k);
    } else {
      const parent = k.slice(0, dot);
      const child = k.slice(dot + 1);
      if (!subPaths.has(parent)) subPaths.set(parent, new Set());
      subPaths.get(parent)!.add(child);
    }
  }

  const filtered: Record<string, unknown> = {};

  // Top-level selections → include entire value
  for (const key of topLevel) {
    if (key in obj) filtered[key] = obj[key];
  }

  // Sub-path selections → include parent with only chosen children
  for (const [parent, children] of subPaths) {
    if (topLevel.has(parent)) continue; // already included in full
    if (!(parent in obj)) continue;
    const val = obj[parent];
    if (isPlainObject(val)) {
      const sub: Record<string, unknown> = {};
      for (const child of children) {
        if (child in val) sub[child] = val[child];
      }
      filtered[parent] = sub;
    } else if (isArrayOfObjects(val)) {
      // Array of objects → filter each element to only selected sub-keys
      filtered[parent] = val.map((elem) => {
        if (!isPlainObject(elem)) return elem;
        const sub: Record<string, unknown> = {};
        for (const child of children) {
          if (child in elem) sub[child] = elem[child];
        }
        return sub;
      });
    } else {
      // Non-object value — just include it
      filtered[parent] = val;
    }
  }

  return filtered;
}

/**
 * Filter each object in the array using the nested-aware logic.
 */
function filterByKeys(
  items: Record<string, unknown>[],
  keys: Set<string>
): Record<string, unknown>[] {
  return items.map((item) => filterObjectByKeys(item, keys));
}

export function ResultViewer({
  success,
  result,
  error,
  durationMs,
  infoBadges,
}: ResultViewerProps) {
  const [copied, setCopied] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);
  const resultRef = useRef<HTMLPreElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Parse result into array of objects (if possible) for key filtering
  const arrayData = useMemo(
    () => (success ? parseAsArrayOfObjects(result) : null),
    [success, result]
  );
  // Parse result as a single object (if not an array) for key filtering
  const objectData = useMemo(
    () => (success && !arrayData ? parseAsSingleObject(result) : null),
    [success, result, arrayData]
  );
  const allKeys = useMemo(() => {
    if (arrayData) return extractKeysStructured(arrayData);
    if (objectData) return extractKeysStructured([objectData]);
    return { flat: [], structured: [] };
  }, [arrayData, objectData]);

  // Compute the displayed result text
  const displayText = useMemo(() => {
    if (!success) return error ?? "";

    if (selectedKeys.size > 0) {
      if (arrayData) {
        const filtered = filterByKeys(arrayData, selectedKeys);
        return JSON.stringify(filtered, null, 2);
      }
      if (objectData) {
        const filtered = filterObjectByKeys(objectData, selectedKeys);
        return JSON.stringify(filtered, null, 2);
      }
    }

    if (typeof result === "string") {
      // Try to pretty-print JSON strings
      try {
        return JSON.stringify(JSON.parse(result), null, 2);
      } catch {
        return result;
      }
    }
    return JSON.stringify(result, null, 2);
  }, [success, result, error, arrayData, objectData, selectedKeys]);

  // Count items if array
  const itemCount = arrayData?.length;

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(displayText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [displayText]);

  const toggleKey = useCallback((key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const clearFilter = useCallback(() => {
    setSelectedKeys(new Set());
  }, []);

  const selectAllKeys = useCallback(() => {
    setSelectedKeys(new Set(allKeys.flat));
  }, [allKeys]);

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {success ? (
            <CheckCircle2 className="h-4 w-4 text-success" />
          ) : (
            <XCircle className="h-4 w-4 text-destructive" />
          )}
          <span
            className={`text-sm font-medium ${
              success ? "text-success" : "text-destructive"
            }`}
          >
            {success ? "Success" : "Failed"}
          </span>
          {durationMs != null && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock className="h-3 w-3" />
              {durationMs}ms
            </span>
          )}
          {itemCount != null && (
            <Badge variant="secondary">{itemCount} items</Badge>
          )}
          {infoBadges?.map((badge) => (
            <Badge key={badge} variant="secondary">
              {badge}
            </Badge>
          ))}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleCopy}
          className="h-7 px-2"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {/* Key filter */}
      {allKeys.flat.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <div className="relative" ref={dropdownRef}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowFilterDropdown((s) => !s)}
                className="h-8 gap-1.5 text-xs"
              >
                <Filter className="h-3 w-3" />
                Filter Keys
                {selectedKeys.size > 0 && (
                  <Badge variant="default" className="ml-1 text-[10px] px-1.5">
                    {selectedKeys.size}
                  </Badge>
                )}
              </Button>

              {/* Dropdown */}
              {showFilterDropdown && (
                <div className="absolute left-0 top-full z-50 mt-1 w-72 max-h-72 overflow-y-auto rounded-md border border-border bg-card shadow-lg">
                  {/* Actions */}
                  <div className="sticky top-0 flex items-center justify-between border-b border-border bg-card px-3 py-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      {allKeys.flat.length} keys available
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={selectAllKeys}
                        className="text-xs text-primary hover:underline cursor-pointer"
                      >
                        All
                      </button>
                      <button
                        onClick={clearFilter}
                        className="text-xs text-primary hover:underline cursor-pointer"
                      >
                        None
                      </button>
                    </div>
                  </div>
                  {/* Key checkboxes — grouped by parent with sub-keys indented */}
                  <div className="p-1">
                    {allKeys.structured.map((entry) => (
                      <div key={entry.key}>
                        {/* Top-level key */}
                        <label
                          className="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedKeys.has(entry.key)}
                            onChange={() => toggleKey(entry.key)}
                            className="h-3.5 w-3.5 rounded border-input accent-primary"
                          />
                          <span className="truncate font-mono text-xs font-semibold">
                            {entry.key}
                          </span>
                          {entry.subKeys.length > 0 && (
                            <span className="text-[10px] text-muted-foreground">
                              ({entry.subKeys.length})
                            </span>
                          )}
                        </label>
                        {/* Sub-keys */}
                        {entry.subKeys.map((sk) => {
                          const dotKey = `${entry.key}.${sk}`;
                          return (
                            <label
                              key={dotKey}
                              className="flex items-center gap-2 rounded-sm pl-7 pr-2 py-1 text-sm hover:bg-accent cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={selectedKeys.has(dotKey)}
                                onChange={() => toggleKey(dotKey)}
                                className="h-3 w-3 rounded border-input accent-primary"
                              />
                              <span className="truncate font-mono text-[11px] text-muted-foreground">
                                .{sk}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Active filter chips */}
            {selectedKeys.size > 0 && (
              <div className="flex flex-wrap gap-1">
                {Array.from(selectedKeys).map((key) => (
                  <button
                    key={key}
                    onClick={() => toggleKey(key)}
                    className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/20 transition-colors cursor-pointer"
                  >
                    {key}
                    <X className="h-2.5 w-2.5" />
                  </button>
                ))}
                <button
                  onClick={clearFilter}
                  className="text-[11px] text-muted-foreground hover:text-foreground ml-1 cursor-pointer"
                >
                  Clear all
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Result content */}
      <pre
        ref={resultRef}
        className="max-h-[40vh] overflow-auto rounded-md border border-border bg-muted/30 p-4 text-xs leading-relaxed font-mono whitespace-pre-wrap break-words"
      >
        {displayText}
      </pre>
    </div>
  );
}
