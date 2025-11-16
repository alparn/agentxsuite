"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X, Play, Loader2, CheckCircle, XCircle } from "lucide-react";
import { api, runsApi } from "@/lib/api";

interface RunToolModalProps {
  isOpen: boolean;
  onClose: () => void;
  toolId: string;
  toolName: string;
  orgId: string;
}

export function RunToolModal({
  isOpen,
  onClose,
  toolId,
  toolName,
  orgId,
}: RunToolModalProps) {
  const [inputJson, setInputJson] = useState("{}");
  const [agentId, setAgentId] = useState("");
  const [runResult, setRunResult] = useState<any>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch tool details to get schema
  const { data: toolData } = useQuery({
    queryKey: ["tool", orgId, toolId],
    queryFn: async () => {
      const response = await api.get(`/orgs/${orgId}/tools/${toolId}/`);
      return response.data;
    },
    enabled: !!orgId && !!toolId && isOpen,
  });

  // Fetch agents for selection
  const { data: agentsData } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      const response = await api.get(`/orgs/${orgId}/agents/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  const agents = Array.isArray(agentsData) ? agentsData : [];

  useEffect(() => {
    if (toolData?.input_schema) {
      setInputJson(JSON.stringify(toolData.input_schema, null, 2));
    }
  }, [toolData]);

  const runMutation = useMutation({
    mutationFn: async () => {
      let parsedInput = {};
      try {
        parsedInput = JSON.parse(inputJson);
      } catch (err) {
        throw new Error("Invalid JSON format");
      }

      // Use unified runs API
      const envId = toolData?.environment?.id || toolData?.environment_id;
      
      const response = await runsApi.execute(orgId, {
        tool: toolId, // Can be UUID or name
        agent: agentId || undefined, // Optional
        input: parsedInput,
        environment: envId, // Optional, will be derived from tool if not provided
      });
      
      return response.data;
    },
    onSuccess: (data) => {
      setRunResult(data);
      setErrors({});
    },
    onError: (error: any) => {
      if (error.message === "Invalid JSON format") {
        setErrors({ input_json: "Invalid JSON format" });
      } else {
        setRunResult({
          error: error.message || error.response?.data?.error || "Run failed",
        });
      }
    },
  });

  const handleRun = () => {
    setRunResult(null);
    setErrors({});
    runMutation.mutate();
  };

  const handleClose = () => {
    setRunResult(null);
    setErrors({});
    setInputJson("{}");
    setAgentId("");
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-2xl w-full shadow-xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between sticky top-0 bg-slate-900 z-10">
          <div className="flex items-center gap-2">
            <Play className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Run Tool</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Tool</label>
            <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
              {toolName}
            </div>
          </div>

          {/* Agent Selection */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Agent (Optional)
            </label>
            <select
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">Auto-select enabled agent</option>
              {agents.filter((a: any) => a.enabled).map((agent: any) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </div>

          {/* Input JSON */}
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">
              Input JSON
            </label>
            <textarea
              value={inputJson}
              onChange={(e) => setInputJson(e.target.value)}
              rows={8}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder='{"key": "value"}'
            />
            {errors.input_json && (
              <p className="text-sm text-red-400 mt-1">{errors.input_json}</p>
            )}
          </div>

          {/* Run Result */}
          {runResult && (
            <div className={`p-4 rounded-lg border ${
              runResult.error 
                ? "bg-red-500/10 border-red-500/30" 
                : "bg-green-500/10 border-green-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-3">
                {runResult.error ? (
                  <XCircle className="w-5 h-5 text-red-400" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                )}
                <span className={`font-medium ${
                  runResult.error ? "text-red-400" : "text-green-400"
                }`}>
                  {runResult.error ? "Run Failed" : "Run Started"}
                </span>
              </div>
              
              {!runResult.error && runResult.run_id && (
                <div className="space-y-2">
                  <div className="text-sm text-slate-300">
                    <span className="text-slate-400">Run ID:</span>{" "}
                    <span className="font-mono text-purple-400">{runResult.run_id}</span>
                  </div>
                  <div className="text-sm text-slate-300">
                    <span className="text-slate-400">Status:</span>{" "}
                    <span className="capitalize">{runResult.status}</span>
                  </div>
                  {runResult.execution?.started_at && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Started:</span>{" "}
                      {new Date(runResult.execution.started_at).toLocaleString()}
                    </div>
                  )}
                  {runResult.execution?.duration_ms && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Duration:</span>{" "}
                      {runResult.execution.duration_ms}ms
                    </div>
                  )}
                  {runResult.content && runResult.content.length > 0 && (
                    <div className="mt-3">
                      <div className="text-sm text-slate-400 mb-1">Output:</div>
                      <pre className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 text-xs overflow-x-auto max-h-48 overflow-y-auto">
                        {runResult.content.map((item: any, idx: number) => (
                          <div key={idx}>{item.text || JSON.stringify(item, null, 2)}</div>
                        ))}
                      </pre>
                    </div>
                  )}
                </div>
              )}
              
              {runResult.error && (
                <p className="text-sm text-red-400 mt-2">
                  Error: {runResult.error}
                </p>
              )}
            </div>
          )}

          {/* Tool Schema (if available) */}
          {toolData?.input_schema && (
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">
                Tool Schema
              </label>
              <pre className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 text-xs overflow-x-auto max-h-48 overflow-y-auto">
                {JSON.stringify(toolData.input_schema, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 flex items-center gap-2 justify-end sticky bottom-0 bg-slate-900">
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
          >
            Close
          </button>
          <button
            onClick={handleRun}
            disabled={runMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {runMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Run Tool
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

