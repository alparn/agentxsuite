"use client";

import { useState, useEffect, useRef } from "react";
import { X, CheckCircle2, XCircle, AlertCircle, Info, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";

interface ToolRunDialogProps {
  tool: any;
  onRun: (inputJson: Record<string, any>, agentId?: string) => void;
  onClose: () => void;
  running: boolean;
  result: any;
  error: string | null;
  agents?: any[];
  selectedAgentId?: string | null;
  onAgentChange?: (agentId: string | null) => void;
}

export function ToolRunDialog({
  tool,
  onRun,
  onClose,
  running,
  result,
  error,
  agents = [],
  selectedAgentId = null,
  onAgentChange,
}: ToolRunDialogProps) {
  const { currentOrgId: orgId } = useAppStore();
  const [args, setArgs] = useState<Record<string, any>>({});
  const [localAgentId, setLocalAgentId] = useState<string | null>(selectedAgentId || null);
  const [runId, setRunId] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch run steps if runId is set
  const { data: stepsData } = useQuery({
    queryKey: ["run-steps", orgId, runId],
    queryFn: async () => {
      if (!orgId || !runId) return [];
      const response = await api.get(`/orgs/${orgId}/runs/${runId}/steps/`);
      return Array.isArray(response.data) ? response.data : [];
    },
    enabled: !!orgId && !!runId && (running || showChat),
    refetchInterval: running ? 500 : false, // Poll every 500ms while running
  });

  const steps = Array.isArray(stepsData) ? stepsData : [];

  // Scroll to bottom when new steps arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [steps]);

  // Extract runId from result (MCP format uses run_id, legacy format uses id)
  useEffect(() => {
    const id = result?.run_id || result?.id;
    if (id) {
      setRunId(id);
      setShowChat(true);
    }
  }, [result]);

  // Show chat automatically when running starts
  useEffect(() => {
    if (running) {
      setShowChat(true);
    }
  }, [running]);

  // Hide chat when error occurs (to show error message prominently)
  useEffect(() => {
    if (error && !running) {
      setShowChat(false);
    }
  }, [error, running]);

  // Parse JSON Schema to generate form fields
  const schema = tool.schema_json || {};
  const properties = schema.properties || {};
  const required = schema.required || [];
  
  // Get description from schema
  const toolDescription = schema.description || "";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun(args, localAgentId || undefined);
  };

  const effectiveAgentId = selectedAgentId !== undefined ? selectedAgentId : localAgentId;

  const updateArg = (key: string, value: any) => {
    setArgs((prev) => ({ ...prev, [key]: value }));
  };

  const getStepIcon = (stepType: string, isRunning: boolean) => {
    switch (stepType) {
      case "success":
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case "error":
        return <XCircle className="w-4 h-4 text-red-400" />;
      case "warning":
        return <AlertCircle className="w-4 h-4 text-yellow-400" />;
      case "check":
        // Show spinner only while running, otherwise show info icon
        return isRunning 
          ? <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
          : <Info className="w-4 h-4 text-blue-400" />;
      case "execution":
        // Show spinner only while running, otherwise show checkmark
        return isRunning
          ? <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
          : <CheckCircle2 className="w-4 h-4 text-purple-400" />;
      default:
        return <Info className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStepColor = (stepType: string) => {
    switch (stepType) {
      case "success":
        return "bg-green-500/10 border-green-500/20 text-green-300";
      case "error":
        return "bg-red-500/10 border-red-500/20 text-red-300";
      case "warning":
        return "bg-yellow-500/10 border-yellow-500/20 text-yellow-300";
      case "check":
        return "bg-blue-500/10 border-blue-500/20 text-blue-300";
      case "execution":
        return "bg-purple-500/10 border-purple-500/20 text-purple-300";
      default:
        return "bg-slate-800 border-slate-700 text-slate-300";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-4xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between mb-4 flex-shrink-0">
          <h2 className="text-2xl font-bold text-white">Run Tool: {tool.name}</h2>
          <div className="flex items-center gap-2">
            {runId && (
              <button
                onClick={() => setShowChat(!showChat)}
                className="px-3 py-1.5 text-sm bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
              >
                {showChat ? "Formular" : "Chat"}
              </button>
            )}
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
            disabled={running}
          >
            <X className="w-5 h-5" />
          </button>
          </div>
        </div>

        {showChat && runId ? (
          <div className="flex-1 flex flex-col min-h-0">
            <div className="mb-2 text-sm text-slate-400">Agent-Schritte:</div>
            <div className="flex-1 overflow-y-auto bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-2">
              {steps.length === 0 ? (
                <div className="text-center text-slate-500 py-8">
                  {running ? "Warte auf Schritte..." : "Keine Schritte verfügbar"}
                </div>
              ) : (
                steps.map((step: any) => (
                  <div
                    key={step.id}
                    className={`p-3 rounded-lg border ${getStepColor(step.step_type)} flex items-start gap-3`}
                  >
                    <div className="flex-shrink-0 mt-0.5">{getStepIcon(step.step_type, running)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium break-words">{step.message}</div>
                      {step.details && Object.keys(step.details).length > 0 && (
                        <details className="mt-2">
                          <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                            Details anzeigen
                          </summary>
                          <pre className="mt-2 text-xs bg-slate-900/50 p-2 rounded overflow-x-auto">
                            {JSON.stringify(step.details, null, 2)}
                          </pre>
                        </details>
                      )}
                      <div className="text-xs text-slate-500 mt-1">
                        {new Date(step.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))
              )}
              {running && (
                <div className="flex items-center gap-2 text-slate-400 text-sm p-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Läuft...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
        {toolDescription && (
          <p className="text-slate-400 mb-4">{toolDescription}</p>
        )}

            {agents && agents.length > 0 ? (
              <div className="mb-4">
                <label className="block text-sm font-medium mb-1 text-slate-300">
                  Agent auswählen
                  <span className="text-red-500 ml-1">*</span>
                </label>
                <select
                  value={effectiveAgentId || ""}
                  onChange={(e) => {
                    const newAgentId = e.target.value || null;
                    setLocalAgentId(newAgentId);
                    if (onAgentChange) {
                      onAgentChange(newAgentId);
                    }
                  }}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  required
                >
                  <option value="">-- Agent auswählen --</option>
                  {agents.map((agent: any) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} {agent.is_axcore || agent.tags?.includes("axcore") ? "(AxCore)" : ""}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  Wählen Sie den Agent aus, der diese Aufgabe ausführen soll.
                </p>
              </div>
            ) : (
              <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded">
                <p className="text-sm text-yellow-300">
                  ⚠️ Kein Agent in derselben Environment wie dieses Tool verfügbar. 
                  Bitte erstellen Sie einen Agent in der Environment "{tool.environment?.name || 'Unknown'}".
                </p>
              </div>
            )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {Object.entries(properties).map(([key, prop]: [string, any]) => {
            // Skip status field for query tools - it's confusing for users
            // Status should only be used as a filter parameter, not as input for action tools
            // For list_runs, status is a filter, which is fine, but we should make it clearer
            const isStatusField = key === "status";
            const isQueryTool = tool.name?.startsWith("agentxsuite_list_") || tool.name?.startsWith("list_");
            
            // Only show status field for query/list tools where it makes sense as a filter
            if (isStatusField && !isQueryTool) {
              return null; // Hide status field for action tools
            }
            
            return (
            <div key={key}>
              <label className="block text-sm font-medium mb-1 text-slate-300">
                  {prop.title || (isStatusField && isQueryTool ? "Filter by Status" : key)}
                {required.includes(key) && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </label>
              {renderSchemaField(key, prop, args, updateArg, required)}
            </div>
            );
          })}

          {Object.keys(properties).length === 0 && (
            <p className="text-slate-400">No parameters required</p>
          )}

          <div className="flex gap-2 justify-end mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
              disabled={running}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={running || (agents && agents.length > 0 && !effectiveAgentId)}
            >
              {running ? "Running..." : "Run Tool"}
            </button>
          </div>
        </form>

            {result && !showChat && (
          <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded">
            <h3 className="font-semibold mb-2 text-green-400">Result:</h3>
            <div className="space-y-2 text-sm text-green-300">
              {result.status && (
                <div>
                  <span className="font-medium">Status:</span>{" "}
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    result.status === "succeeded"
                      ? "bg-green-500/20 text-green-400"
                      : result.status === "failed"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-yellow-500/20 text-yellow-400"
                  }`}>
                    {result.status}
                  </span>
                </div>
              )}
              {(result.output_json || result.content) && (
                <div>
                  <span className="font-medium">Output:</span>
                  <pre className="mt-1 whitespace-pre-wrap overflow-x-auto">
                    {result.output_json 
                      ? formatResult(result.output_json) 
                      : result.content?.map((item: any) => item.text || JSON.stringify(item, null, 2)).join("\n") || "No output"}
                  </pre>
                </div>
              )}
              {result.error_text && (
                <div>
                  <span className="font-medium">Error:</span>{" "}
                  <span className="text-red-300">{result.error_text}</span>
                </div>
              )}
              {(result.run_id || result.id) && (
                <div className="text-xs text-slate-400 mt-2">
                  Run ID: {result.run_id || result.id}
                </div>
              )}
              {result.execution?.duration_ms && (
                <div className="text-xs text-slate-400">
                  Duration: {result.execution.duration_ms}ms
                </div>
              )}
            </div>
          </div>
        )}

            {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded">
            <h3 className="font-semibold mb-2 text-red-400">❌ Error</h3>
            <pre className="whitespace-pre-wrap text-sm text-red-300 overflow-x-auto max-h-48">
              {error}
            </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function renderSchemaField(
  key: string,
  prop: any,
  args: Record<string, any>,
  updateArg: (key: string, value: any) => void,
  required: string[]
) {
  const propType = prop.type || (Array.isArray(prop.type) ? prop.type[0] : "string");
  const isRequired = required.includes(key);

  // Handle enum
  if (prop.enum && Array.isArray(prop.enum)) {
    return (
      <>
        <select
          value={args[key] || ""}
          onChange={(e) => updateArg(key, e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
        >
          <option value="">Select {key}...</option>
          {prop.enum.map((value: any) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle boolean
  if (propType === "boolean") {
    return (
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={args[key] || false}
          onChange={(e) => updateArg(key, e.target.checked)}
          className="w-4 h-4 rounded"
        />
        <span className="text-slate-400 text-sm">
          {prop.description || key}
        </span>
      </div>
    );
  }

  // Handle array
  if (propType === "array") {
    const arrayValue = Array.isArray(args[key]) ? args[key] : [];
    return (
      <>
        <textarea
          value={JSON.stringify(arrayValue, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (Array.isArray(parsed)) {
                updateArg(key, parsed);
              }
            } catch {
              // Invalid JSON, ignore
            }
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
          placeholder='["item1", "item2"]'
          rows={3}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle object
  if (propType === "object") {
    const objectValue = typeof args[key] === "object" && args[key] !== null ? args[key] : {};
    return (
      <>
        <textarea
          value={JSON.stringify(objectValue, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (typeof parsed === "object" && parsed !== null) {
                updateArg(key, parsed);
              }
            } catch {
              // Invalid JSON, ignore
            }
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
          placeholder='{"key": "value"}'
          rows={4}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle string with format
  if (propType === "string" && prop.format === "textarea") {
    return (
      <>
        <textarea
          value={args[key] || ""}
          onChange={(e) => updateArg(key, e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
          placeholder={prop.description || key}
          rows={4}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle number/integer
  if (propType === "number" || propType === "integer") {
    return (
      <>
        <input
          type="number"
          value={args[key] || ""}
          onChange={(e) => {
            const value = propType === "integer" 
              ? parseInt(e.target.value, 10) || 0
              : parseFloat(e.target.value) || 0;
            updateArg(key, value);
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
          placeholder={prop.description || key}
          min={prop.minimum}
          max={prop.maximum}
          step={propType === "integer" ? 1 : undefined}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Default: text input
  return (
    <>
      <input
        type="text"
        value={args[key] || ""}
        onChange={(e) => updateArg(key, e.target.value)}
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
        required={isRequired}
        placeholder={prop.description || key}
        pattern={prop.pattern}
        minLength={prop.minLength}
        maxLength={prop.maxLength}
      />
      {prop.description && (
        <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
      )}
    </>
  );
}

function formatResult(result: any): string {
  // Try to parse and format as JSON if possible
  if (typeof result === "object") {
    return JSON.stringify(result, null, 2);
  }
  try {
    const parsed = JSON.parse(result);
    return JSON.stringify(parsed, null, 2);
  } catch {
    // Not JSON, return as-is
    return String(result);
  }
}

