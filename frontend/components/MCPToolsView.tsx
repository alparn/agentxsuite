"use client";

import { useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { mcpFabric, MCPTool, MCPFabricError } from "@/lib/mcpFabric";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { MCPToolRunDialog } from "./MCPToolRunDialog";
import { MCPToolCreateDialog } from "./MCPToolCreateDialog";
import { AlertCircle, RefreshCw, Plus, Edit } from "lucide-react";

export function MCPToolsView() {
  const { currentOrgId, currentEnvId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingTool, setEditingTool] = useState<MCPTool | null>(null);

  // Fetch organizations
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  // Auto-select first organization if none selected
  useEffect(() => {
    if (!currentOrgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, currentOrgId, setCurrentOrg]);

  // Fetch environments for selected organization
  const { data: environmentsData } = useQuery({
    queryKey: ["environments", currentOrgId],
    queryFn: async () => {
      if (!currentOrgId) return [];
      const response = await api.get(`/orgs/${currentOrgId}/environments/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!currentOrgId,
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Auto-select first environment if none selected
  useEffect(() => {
    if (currentOrgId && !currentEnvId && environments && environments.length > 0) {
      setCurrentEnv(environments[0].id);
    }
  }, [currentOrgId, currentEnvId, environments, setCurrentEnv]);

  const loadTools = useCallback(async () => {
    if (!currentOrgId || !currentEnvId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await mcpFabric.getTools(currentOrgId, currentEnvId);
      // Handle both formats: {tools: [...]} or direct array
      const toolsArray = Array.isArray(response) 
        ? response 
        : (Array.isArray(response?.tools) ? response.tools : []);
      setTools(toolsArray);
    } catch (err: any) {
      setTools([]); // Reset tools on error
      if (err instanceof MCPFabricError) {
        setError(err.message);
      } else {
        setError(err.response?.data?.detail || "Failed to load tools");
      }
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, currentEnvId]);

  useEffect(() => {
    if (currentOrgId && currentEnvId) {
      loadTools();
    } else {
      setTools([]);
      setError(null);
    }
  }, [currentOrgId, currentEnvId, loadTools]);

  if (organizations.length === 0) {
    return (
      <div className="p-4 text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
        No organizations available. Please create an organization first.
      </div>
    );
  }

  if (!currentOrgId || !currentEnvId) {
    if (environments.length === 0 && currentOrgId) {
      return (
        <div className="p-4 text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
          No environments available for this organization. Please create an environment first.
        </div>
      );
    }
    // Still loading or selecting
    return (
      <div className="p-4 text-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading...
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 text-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading tools...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <span className="font-semibold text-red-400">Error</span>
        </div>
        <p className="text-red-300 mb-3">{error}</p>
        <button
          onClick={loadTools}
          className="px-4 py-2 bg-red-500/20 text-red-300 rounded hover:bg-red-500/30 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Only show selectors if multiple options available
  const showOrgSelector = organizations.length > 1;
  const showEnvSelector = environments.length > 1;

  return (
    <div className="space-y-4">
      {/* Organization and Environment Selectors - only if multiple options */}
      {(showOrgSelector || showEnvSelector) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {showOrgSelector && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Organization
              </label>
              <select
                value={currentOrgId || ""}
                onChange={(e) => {
                  setCurrentOrg(e.target.value);
                  setCurrentEnv(null); // Reset environment when org changes
                }}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {organizations.map((org: any) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {showEnvSelector && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Environment
              </label>
              <select
                value={currentEnvId || ""}
                onChange={(e) => setCurrentEnv(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {environments.map((env: any) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.type})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">MCP Tools</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Tool
          </button>
          <button
            onClick={loadTools}
            className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>
      <div className="grid gap-4">
        {tools && tools.length > 0 ? (
          tools.map((tool) => (
            <MCPToolCard
              key={tool.name}
              tool={tool}
              onEdit={(tool) => setEditingTool(tool)}
            />
          ))
        ) : (
          <div className="p-8 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
            No tools available for this environment
          </div>
        )}
      </div>

      <MCPToolCreateDialog
        isOpen={showCreateDialog || !!editingTool}
        onClose={() => {
          setShowCreateDialog(false);
          setEditingTool(null);
        }}
        orgId={currentOrgId}
        envId={currentEnvId}
        tool={editingTool || undefined}
        onSuccess={() => {
          loadTools();
          setEditingTool(null);
        }}
      />
    </div>
  );
}

function MCPToolCard({
  tool,
  onEdit,
}: {
  tool: MCPTool;
  onEdit: (tool: MCPTool) => void;
}) {
  const { currentOrgId, currentEnvId } = useAppStore();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDialog, setShowDialog] = useState(false);

  const handleRun = async (args: Record<string, any>) => {
    if (!currentOrgId || !currentEnvId) return;

    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const response = await mcpFabric.runTool(
        currentOrgId,
        currentEnvId,
        tool.name,
        args
      );

      // runTool now always returns MCPRunResponse (never throws)
      if (response.isError) {
        // Combine all error content items
        const errorText = response.content
          ?.map((item) => item.text || "")
          .filter(Boolean)
          .join("\n") || "Unknown error";
        setError(errorText);
      } else {
        // Combine all result content items
        const resultText = response.content
          ?.map((item) => item.text || "")
          .filter(Boolean)
          .join("\n") || "Success";
        setResult(resultText);
      }
    } catch (err: any) {
      // Fallback error handling (should not happen, but just in case)
      if (err instanceof MCPFabricError) {
        setError(err.message);
      } else {
        setError(
          err.response?.data?.detail || err.message || "Failed to execute tool"
        );
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <h3 className="font-semibold text-lg text-white">{tool.name}</h3>
            {(tool.description || tool.inputSchema?.description) && (
              <p className="text-slate-400 text-sm mt-1">
                {tool.description || tool.inputSchema?.description || ""}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onEdit(tool)}
              className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-all flex items-center gap-2"
              title="Edit Tool"
            >
              <Edit className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowDialog(true)}
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={running}
            >
              {running ? "Running..." : "Run"}
            </button>
          </div>
        </div>
      </div>

      {showDialog && (
        <MCPToolRunDialog
          tool={tool}
          onRun={handleRun}
          onClose={() => {
            setShowDialog(false);
            setResult(null);
            setError(null);
          }}
          running={running}
          result={result}
          error={error}
        />
      )}
    </>
  );
}

