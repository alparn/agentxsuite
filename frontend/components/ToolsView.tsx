"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, Play, CheckCircle2, XCircle, Edit } from "lucide-react";
import { ToolDialog } from "./ToolDialog";
import { MCPToolsView } from "./MCPToolsView";
import { ToolRunDialog } from "./ToolRunDialog";

export function ToolsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const [selectedTool, setSelectedTool] = useState<any>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<any>(null);
  const [runningTool, setRunningTool] = useState<any>(null);
  const [runResult, setRunResult] = useState<any>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"registry" | "mcp">("registry");

  // Fetch organizations and auto-select first one if none selected
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      // Handle both old format (array) and new format (object with organizations)
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  const { data: toolsData, isLoading, error: toolsError } = useQuery({
    queryKey: ["tools", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/tools/`);
      // Handle paginated response (DRF returns {results: [...], count, next, previous})
      // or direct array response
      if (Array.isArray(response.data)) {
        return response.data;
      } else if (response.data?.results && Array.isArray(response.data.results)) {
        return response.data.results;
      }
      return [];
    },
    enabled: !!orgId,
  });

  const tools = Array.isArray(toolsData) ? toolsData : [];

  const runToolMutation = useMutation({
    mutationFn: async ({ toolId, inputJson }: { toolId: string; inputJson: Record<string, any> }) => {
      // Use Tool Registry API
      const url = orgId 
        ? `/orgs/${orgId}/tools/${toolId}/run/`
        : `/tools/${toolId}/run/`;
      const response = await api.post(url, {
        input_json: inputJson,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setRunResult(data);
      setRunError(null);
    },
    onError: (error: any) => {
      // Handle different error formats
      let errorMessage = "Failed to run tool";
      
      if (error.response?.data) {
        const data = error.response.data;
        
        // Check if response is HTML (Django error page)
        if (typeof data === "string" && data.includes("<!DOCTYPE html>")) {
          // Extract error from HTML if possible
          const match = data.match(/<pre class="exception_value">([\s\S]*?)<\/pre>/);
          if (match) {
            errorMessage = match[1].trim();
          } else {
            // Try to extract title
            const titleMatch = data.match(/<title>([\s\S]*?)<\/title>/);
            if (titleMatch) {
              errorMessage = titleMatch[1].replace(/at.*$/, "").trim();
            } else {
              errorMessage = "Server error occurred. Please check the backend logs.";
            }
          }
        } else if (typeof data === "string") {
          errorMessage = data;
        } else if (data.error) {
          errorMessage = typeof data.error === "string" ? data.error : JSON.stringify(data.error);
        } else if (data.detail) {
          errorMessage = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        } else if (Array.isArray(data)) {
          errorMessage = data.join(", ");
        } else if (typeof data === "object") {
          errorMessage = JSON.stringify(data, null, 2);
        } else {
          errorMessage = String(data);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      setRunError(errorMessage);
      setRunResult(null);
    },
  });

  const handleRunTool = (inputJson: Record<string, any>) => {
    if (!runningTool) return;
    setRunError(null);
    setRunResult(null);
    runToolMutation.mutate({
      toolId: runningTool.id,
      inputJson,
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("tools.title")}
          </h1>
          <p className="text-slate-400">Manage and test your tools</p>
        </div>
        {activeTab === "registry" && (
          <button
            onClick={() => {
              setEditingTool(null);
              setIsDialogOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
          >
            <Plus className="w-5 h-5" />
            {t("tools.defineTool")}
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-800">
        <div className="flex gap-4">
          <button
            onClick={() => setActiveTab("registry")}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === "registry"
                ? "text-white border-b-2 border-purple-500"
                : "text-slate-400 hover:text-slate-300"
            }`}
          >
            Tool Registry
          </button>
          <button
            onClick={() => setActiveTab("mcp")}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === "mcp"
                ? "text-white border-b-2 border-purple-500"
                : "text-slate-400 hover:text-slate-300"
            }`}
          >
            MCP Fabric
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "registry" && (
        <>
          {toolsError && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg mb-4">
              <p className="text-sm text-red-400">Error loading tools: {toolsError.message}</p>
            </div>
          )}
          {isLoading ? (
            <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-800">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {t("common.name")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {t("tools.version")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {t("tools.connection")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {t("common.status")}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {t("common.actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {tools?.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                          {t("common.noData")}
                        </td>
                      </tr>
                    ) : (
                      tools?.map((tool: any) => (
                        <tr key={tool.id} className="hover:bg-slate-800/50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-medium">
                            {tool.name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                            {tool.version}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                            {tool.connection?.name || "-"}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span
                              className={`px-2 py-1 text-xs rounded-full flex items-center gap-1 ${
                                tool.enabled
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-slate-500/20 text-slate-400"
                              }`}
                            >
                              {tool.enabled ? (
                                <CheckCircle2 className="w-3 h-3" />
                              ) : (
                                <XCircle className="w-3 h-3" />
                              )}
                              {tool.enabled ? "Enabled" : "Disabled"}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setEditingTool(tool);
                                  setIsDialogOpen(true);
                                }}
                                className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                                title={t("common.edit")}
                              >
                                <Edit className="w-4 h-4" />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setRunningTool(tool);
                                  setRunResult(null);
                                  setRunError(null);
                                }}
                                className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                                title={t("tools.testRun")}
                              >
                                <Play className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === "mcp" && <MCPToolsView />}

      {runningTool && (
        <ToolRunDialog
          tool={runningTool}
          onRun={handleRunTool}
          onClose={() => {
            setRunningTool(null);
            setRunResult(null);
            setRunError(null);
          }}
          running={runToolMutation.isPending}
          result={runResult}
          error={runError}
        />
      )}

      <ToolDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setEditingTool(null);
        }}
        tool={editingTool}
        orgId={orgId}
      />
    </div>
  );
}

