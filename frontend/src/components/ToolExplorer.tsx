import { useState, useEffect, useCallback } from "react";
import {
  Search,
  Play,
  Server,
  Wrench,
  ChevronRight,
  ChevronDown,
  Loader2,
  Plus,
  Trash2,
  Info,
  Code,
} from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ResultViewer } from "@/components/ResultViewer";
import type {
  MCPServerStatus,
  MCPToolInfo,
  MCPToolCallResponse,
} from "@/types/api";

// ── Helpers ─────────────────────────────────────────────────────────────────

function getSchemaProperties(
  schema: Record<string, unknown> | null | undefined
): Record<
  string,
  { type?: string; description?: string; required: boolean; enum?: string[] }
> {
  if (!schema) return {};
  const props = (schema.properties ?? {}) as Record<
    string,
    Record<string, unknown>
  >;
  const required = (schema.required ?? []) as string[];
  const result: Record<
    string,
    { type?: string; description?: string; required: boolean; enum?: string[] }
  > = {};
  for (const [key, val] of Object.entries(props)) {
    result[key] = {
      type: val.type as string | undefined,
      description: val.description as string | undefined,
      required: required.includes(key),
      enum: val.enum as string[] | undefined,
    };
  }
  return result;
}

// ── Component ───────────────────────────────────────────────────────────────

export function ToolExplorer() {
  // State
  const [servers, setServers] = useState<MCPServerStatus[]>([]);
  const [selectedServer, setSelectedServer] = useState<string | null>(null);
  const [tools, setTools] = useState<MCPToolInfo[]>([]);
  const [filteredTools, setFilteredTools] = useState<MCPToolInfo[]>([]);
  const [selectedTool, setSelectedTool] = useState<MCPToolInfo | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [argValues, setArgValues] = useState<Record<string, string>>({});
  const [customParams, setCustomParams] = useState<
    { key: string; value: string }[]
  >([]);
  const [result, setResult] = useState<MCPToolCallResponse | null>(null);
  const [loading, setLoading] = useState({
    servers: false,
    tools: false,
    call: false,
  });
  const [errors, setErrors] = useState<{
    servers?: string;
    tools?: string;
    call?: string;
  }>({});
  const [showSchema, setShowSchema] = useState(false);

  // ── Load servers on mount ────────────────────────────────────────────────

  const loadServers = useCallback(async () => {
    setLoading((l) => ({ ...l, servers: true }));
    setErrors((e) => ({ ...e, servers: undefined }));
    try {
      const res = await api.listMCPServers();
      setServers(res.servers);
      // Auto-select the first connected server
      const first = res.servers.find((s) => s.connected);
      if (first && !selectedServer) {
        setSelectedServer(first.name);
      }
    } catch (err) {
      setErrors((e) => ({
        ...e,
        servers:
          err instanceof Error ? err.message : "Failed to load MCP servers",
      }));
    } finally {
      setLoading((l) => ({ ...l, servers: false }));
    }
  }, [selectedServer]);

  useEffect(() => {
    loadServers();
  }, [loadServers]);

  // ── Load tools when server changes ───────────────────────────────────────

  useEffect(() => {
    if (!selectedServer) return;
    let cancelled = false;

    const load = async () => {
      setLoading((l) => ({ ...l, tools: true }));
      setErrors((e) => ({ ...e, tools: undefined }));
      setSelectedTool(null);
      setResult(null);
      try {
        const res = await api.listServerTools(selectedServer);
        if (!cancelled) {
          setTools(res.tools);
          setFilteredTools(res.tools);
        }
      } catch (err) {
        if (!cancelled) {
          setErrors((e) => ({
            ...e,
            tools:
              err instanceof Error ? err.message : "Failed to load tools",
          }));
        }
      } finally {
        if (!cancelled) setLoading((l) => ({ ...l, tools: false }));
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [selectedServer]);

  // ── Filter tools ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredTools(tools);
      return;
    }
    const q = searchQuery.toLowerCase();
    setFilteredTools(
      tools.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          (t.description && t.description.toLowerCase().includes(q))
      )
    );
  }, [searchQuery, tools]);

  // ── Select tool ──────────────────────────────────────────────────────────

  const handleSelectTool = useCallback((tool: MCPToolInfo) => {
    setSelectedTool(tool);
    setArgValues({});
    setCustomParams([]);
    setResult(null);
    setShowSchema(false);
    setErrors((e) => ({ ...e, call: undefined }));
  }, []);

  // ── Call tool ────────────────────────────────────────────────────────────

  const handleCallTool = useCallback(async () => {
    if (!selectedServer || !selectedTool) return;

    setLoading((l) => ({ ...l, call: true }));
    setErrors((e) => ({ ...e, call: undefined }));
    setResult(null);

    // Build arguments object, converting types as needed
    const args: Record<string, unknown> = {};
    const props = getSchemaProperties(
      selectedTool.input_schema as Record<string, unknown> | null
    );

    for (const [key, val] of Object.entries(argValues)) {
      if (val === "") continue;
      const propType = props[key]?.type;
      if (propType === "integer" || propType === "number") {
        args[key] = Number(val);
      } else if (propType === "boolean") {
        args[key] = val === "true";
      } else if (propType === "array" || propType === "object") {
        try {
          args[key] = JSON.parse(val);
        } catch {
          args[key] = val;
        }
      } else {
        args[key] = val;
      }
    }

    // Merge custom (extra) parameters
    for (const { key, value } of customParams) {
      if (!key.trim() || value === "") continue;
      // Auto-detect numbers and booleans
      if (/^\d+$/.test(value)) {
        args[key.trim()] = Number(value);
      } else if (value === "true" || value === "false") {
        args[key.trim()] = value === "true";
      } else {
        try {
          args[key.trim()] = JSON.parse(value);
        } catch {
          args[key.trim()] = value;
        }
      }
    }

    try {
      const res = await api.callTool({
        server: selectedServer,
        tool: selectedTool.name,
        arguments: args,
      });
      setResult(res);
    } catch (err) {
      setErrors((e) => ({
        ...e,
        call: err instanceof Error ? err.message : "Tool call failed",
      }));
    } finally {
      setLoading((l) => ({ ...l, call: false }));
    }
  }, [selectedServer, selectedTool, argValues, customParams]);

  // ── Render ───────────────────────────────────────────────────────────────

  const schemaProps = selectedTool
    ? getSchemaProperties(
        selectedTool.input_schema as Record<string, unknown> | null
      )
    : {};

  return (
    <div className="space-y-6">
      {/* Server selector */}
      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2">
              <Server className="h-5 w-5 text-primary" />
              MCP Servers
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading.servers ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Connecting to MCP servers...
            </div>
          ) : errors.servers ? (
            <div className="text-sm text-destructive">{errors.servers}</div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {servers.map((s) => (
                <button
                  key={s.name}
                  onClick={() => setSelectedServer(s.name)}
                  className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-left transition-colors cursor-pointer ${
                    selectedServer === s.name
                      ? "border-primary bg-primary/5 ring-1 ring-primary"
                      : "border-border hover:border-primary/50 hover:bg-accent/50"
                  } ${!s.connected ? "opacity-50" : ""}`}
                  disabled={!s.connected}
                >
                  <div
                    className={`h-2 w-2 rounded-full ${
                      s.connected ? "bg-success" : "bg-destructive"
                    }`}
                  />
                  <div>
                    <div className="text-sm font-medium capitalize">
                      {s.name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {s.connected
                        ? `${s.tool_count} tools`
                        : "Disconnected"}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tool browser + detail pane */}
      {selectedServer && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Tool list (left) */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>
                <span className="flex items-center gap-2">
                  <Wrench className="h-5 w-5 text-primary" />
                  Tools
                  <Badge variant="secondary">{filteredTools.length}</Badge>
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search tools..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-card pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>

              {/* Tool list */}
              {loading.tools ? (
                <div className="flex items-center gap-2 py-8 justify-center text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading tools...
                </div>
              ) : errors.tools ? (
                <div className="text-sm text-destructive py-4">
                  {errors.tools}
                </div>
              ) : (
                <div className="max-h-[60vh] space-y-1 overflow-y-auto pr-1">
                  {filteredTools.map((tool) => (
                    <button
                      key={tool.name}
                      onClick={() => handleSelectTool(tool)}
                      className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors cursor-pointer ${
                        selectedTool?.name === tool.name
                          ? "bg-primary/10 text-primary font-medium"
                          : "hover:bg-accent"
                      }`}
                    >
                      <ChevronRight
                        className={`h-3 w-3 shrink-0 transition-transform ${
                          selectedTool?.name === tool.name ? "rotate-90" : ""
                        }`}
                      />
                      <span className="truncate">{tool.name}</span>
                    </button>
                  ))}
                  {filteredTools.length === 0 && (
                    <p className="py-4 text-center text-sm text-muted-foreground">
                      No tools match your search
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Tool detail + execution (right) */}
          <Card className="lg:col-span-3">
            <CardContent>
              {selectedTool ? (
                <div className="space-y-5 pt-2">
                  {/* Tool header */}
                  <div>
                    <h3 className="text-base font-semibold">{selectedTool.name}</h3>
                    {selectedTool.description && (
                      <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                        {selectedTool.description}
                      </p>
                    )}
                  </div>

                  {/* Arguments form */}
                  {Object.keys(schemaProps).length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                        Parameters
                      </h4>
                      {Object.entries(schemaProps).map(([key, prop]) => (
                        <div key={key}>
                          <label className="mb-1 flex items-center gap-1.5 text-sm font-medium">
                            {key}
                            {prop.required && (
                              <span className="text-destructive">*</span>
                            )}
                            {prop.type && (
                              <Badge variant="secondary" className="text-[10px]">
                                {prop.type}
                              </Badge>
                            )}
                          </label>
                          {prop.description && (
                            <p className="mb-1.5 text-xs text-muted-foreground">
                              {prop.description}
                            </p>
                          )}
                          {prop.enum ? (
                            <select
                              value={argValues[key] ?? ""}
                              onChange={(e) =>
                                setArgValues((v) => ({
                                  ...v,
                                  [key]: e.target.value,
                                }))
                              }
                              className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              <option value="">Select...</option>
                              {prop.enum.map((val) => (
                                <option key={val} value={val}>
                                  {val}
                                </option>
                              ))}
                            </select>
                          ) : prop.type === "boolean" ? (
                            <select
                              value={argValues[key] ?? ""}
                              onChange={(e) =>
                                setArgValues((v) => ({
                                  ...v,
                                  [key]: e.target.value,
                                }))
                              }
                              className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              <option value="">Select...</option>
                              <option value="true">true</option>
                              <option value="false">false</option>
                            </select>
                          ) : (prop.type === "object" || prop.type === "array") ? (
                            <textarea
                              value={argValues[key] ?? ""}
                              onChange={(e) =>
                                setArgValues((v) => ({
                                  ...v,
                                  [key]: e.target.value,
                                }))
                              }
                              rows={3}
                              placeholder={`Enter JSON ${prop.type}...`}
                              className="flex w-full rounded-md border border-input bg-card px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            />
                          ) : (
                            <Input
                              type={
                                prop.type === "integer" || prop.type === "number"
                                  ? "number"
                                  : "text"
                              }
                              value={argValues[key] ?? ""}
                              onChange={(e) =>
                                setArgValues((v) => ({
                                  ...v,
                                  [key]: e.target.value,
                                }))
                              }
                              placeholder={
                                prop.type === "integer" || prop.type === "number"
                                  ? "0"
                                  : `Enter ${key}...`
                              }
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Custom / extra parameters */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                        Extra Parameters
                      </h4>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setCustomParams((p) => [
                            ...p,
                            { key: "", value: "" },
                          ])
                        }
                        className="h-7 gap-1 px-2 text-xs"
                      >
                        <Plus className="h-3 w-3" />
                        Add
                      </Button>
                    </div>
                    <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400 -mt-1">
                      <Info className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      <span>
                        Extra parameters are passed to the MCP server but may be
                        <strong> silently ignored</strong> if the server doesn't
                        support them. Only the parameters listed above are
                        guaranteed to work.
                      </span>
                    </div>
                    {customParams.map((param, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <Input
                          placeholder="key"
                          value={param.key}
                          onChange={(e) =>
                            setCustomParams((p) =>
                              p.map((item, i) =>
                                i === idx
                                  ? { ...item, key: e.target.value }
                                  : item
                              )
                            )
                          }
                          className="w-1/3"
                        />
                        <Input
                          placeholder="value"
                          value={param.value}
                          onChange={(e) =>
                            setCustomParams((p) =>
                              p.map((item, i) =>
                                i === idx
                                  ? { ...item, value: e.target.value }
                                  : item
                              )
                            )
                          }
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-10 w-10 shrink-0 text-muted-foreground hover:text-destructive"
                          onClick={() =>
                            setCustomParams((p) =>
                              p.filter((_, i) => i !== idx)
                            )
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>

                  {/* Raw schema viewer */}
                  {selectedTool.input_schema && (
                    <div>
                      <button
                        onClick={() => setShowSchema((s) => !s)}
                        className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                      >
                        {showSchema ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ChevronRight className="h-3 w-3" />
                        )}
                        <Code className="h-3 w-3" />
                        Raw Input Schema
                      </button>
                      {showSchema && (
                        <pre className="mt-2 max-h-48 overflow-auto rounded-md border border-border bg-muted/30 p-3 text-xs font-mono leading-relaxed">
                          {JSON.stringify(selectedTool.input_schema, null, 2)}
                        </pre>
                      )}
                    </div>
                  )}

                  {/* Execute button */}
                  <Button
                    onClick={handleCallTool}
                    disabled={loading.call}
                    className="w-full"
                  >
                    {loading.call ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Running...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        Execute Tool
                      </>
                    )}
                  </Button>

                  {/* Error */}
                  {errors.call && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                      {errors.call}
                    </div>
                  )}

                  {/* Result */}
                  {result && (
                    <ResultViewer
                      success={result.success}
                      result={result.result}
                      error={result.error}
                      durationMs={result.duration_ms}
                    />
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground">
                  <Wrench className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">
                    Select a tool from the list to view its details and test it
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
