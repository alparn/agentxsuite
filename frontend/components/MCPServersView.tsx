"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mcpServersApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { MCPServerRegistration } from "@/lib/types";
import { Plus, Edit, Trash2, Activity, Download, Server, Terminal, Globe, Radio, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { MCPServerDialog } from "./MCPServerDialog";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error";
}

export function MCPServersView() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServerRegistration | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

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

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  // Fetch environments
  const { data: environmentsData } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Fetch MCP servers
  const { data: serversData, isLoading, error: serversError } = useQuery({
    queryKey: ["mcp-servers", orgId, envId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
        const response = await mcpServersApi.list(orgId);
        let servers: MCPServerRegistration[] = [];
        if (Array.isArray(response.data)) {
          servers = response.data;
        } else if ((response.data as any)?.results && Array.isArray((response.data as any).results)) {
          servers = (response.data as any).results;
        }
        
        // Filter by environment if selected
        if (envId) {
          const filtered = servers.filter((s: MCPServerRegistration) => {
            const sEnvId = typeof s.environment_id === "string" 
              ? s.environment_id 
              : s.environment?.id || "";
            return String(sEnvId).toLowerCase() === String(envId).toLowerCase();
          });
          return filtered;
        }
        return servers;
      } catch (error: any) {
        console.error("Error fetching MCP servers:", error);
        throw error;
      }
    },
    enabled: !!orgId,
  });

  const servers = Array.isArray(serversData) ? serversData : [];

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!orgId) throw new Error("Organization ID is required");
      return mcpServersApi.delete(orgId, id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      addToast("MCP Server deleted successfully", "success");
    },
    onError: () => {
      addToast("Failed to delete MCP server", "error");
    },
  });

  const healthCheckMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!orgId) throw new Error("Organization ID is required");
      return mcpServersApi.healthCheck(orgId, id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      addToast("Health check completed", "success");
    },
    onError: () => {
      addToast("Health check failed", "error");
    },
  });

  const addToast = (message: string, type: "success" | "error") => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  };

  const getServerTypeIcon = (type: string) => {
    switch (type) {
      case "stdio":
        return Terminal;
      case "http":
        return Globe;
      case "ws":
        return Radio;
      default:
        return Server;
    }
  };

  const getHealthStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return CheckCircle2;
      case "unhealthy":
        return XCircle;
      default:
        return AlertCircle;
    }
  };

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "text-green-600";
      case "unhealthy":
        return "text-red-600";
      default:
        return "text-gray-400";
    }
  };

  const handleEdit = (server: MCPServerRegistration) => {
    setEditingServer(server);
    setIsDialogOpen(true);
  };

  const handleCreate = () => {
    setEditingServer(null);
    setIsDialogOpen(true);
  };

  const handleHealthCheck = (id: string) => {
    healthCheckMutation.mutate(id);
  };

  const handleDownloadConfig = async () => {
    if (!orgId) return;
    try {
      const response = await mcpServersApi.getClaudeConfig(orgId);
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "claude_desktop_config.json";
      a.click();
      URL.revokeObjectURL(url);
      addToast("Claude Desktop config downloaded", "success");
    } catch (error) {
      addToast("Failed to download config", "error");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">{t("common.loading")}</div>
      </div>
    );
  }

  if (serversError) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-500">Error loading MCP servers</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            MCP Server Registry
          </h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            Manage MCP servers for Claude Desktop and other AI assistants
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleDownloadConfig}
            disabled={!orgId || servers.length === 0}
            className="inline-flex items-center px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-4 w-4 mr-2" />
            Download Claude Config
          </button>
          <button
            onClick={handleCreate}
            disabled={!orgId}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="h-5 w-5 mr-2" />
            Add MCP Server
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="flex-1">
          <label htmlFor="org-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Organization
          </label>
          <select
            id="org-select"
            value={orgId || ""}
            onChange={(e) => setCurrentOrg(e.target.value)}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md dark:bg-gray-800 dark:text-white"
          >
            <option value="">Select organization</option>
            {organizations.map((org: any) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label htmlFor="env-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
            Environment (optional)
          </label>
          <select
            id="env-select"
            value={envId || ""}
            onChange={(e) => setCurrentEnv(e.target.value || null)}
            disabled={!orgId}
            className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md dark:bg-gray-800 dark:text-white disabled:opacity-50"
          >
            <option value="">All environments</option>
            {environments.map((env: any) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Server List */}
      <div className="bg-white dark:bg-gray-800 shadow overflow-hidden sm:rounded-md">
        {servers.length === 0 ? (
          <div className="text-center py-12">
            <Server className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">No MCP servers</h3>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Get started by adding a new MCP server.
            </p>
            <div className="mt-6">
              <button
                onClick={handleCreate}
                disabled={!orgId}
                className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="h-5 w-5 mr-2" />
                Add MCP Server
              </button>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-gray-200 dark:divide-gray-700">
            {servers.map((server) => {
              const TypeIcon = getServerTypeIcon(server.server_type);
              const HealthIcon = getHealthStatusIcon(server.health_status);
              const healthColor = getHealthStatusColor(server.health_status);
              return (
                <li key={server.id}>
                  <div className="px-4 py-4 flex items-center sm:px-6 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <div className="min-w-0 flex-1 sm:flex sm:items-center sm:justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <TypeIcon className="flex-shrink-0 mr-3 h-5 w-5 text-gray-400" />
                          <p className="text-sm font-medium text-blue-600 dark:text-blue-400 truncate">
                            {server.name}
                          </p>
                          <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
                            {server.slug}
                          </span>
                          {server.enabled ? (
                            <CheckCircle2 className="ml-2 h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="ml-2 h-4 w-4 text-gray-400" />
                          )}
                        </div>
                        <div className="mt-2 flex">
                          <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                            <HealthIcon className={`flex-shrink-0 mr-1.5 h-4 w-4 ${healthColor}`} />
                            {server.health_status || "unknown"}
                            {server.server_type === "stdio" && server.command && (
                              <span className="ml-4 text-xs text-gray-400">
                                {server.command}
                              </span>
                            )}
                            {server.server_type === "http" && server.endpoint && (
                              <span className="ml-4 text-xs text-gray-400">
                                {server.endpoint}
                              </span>
                            )}
                          </div>
                        </div>
                        {server.description && (
                          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            {server.description}
                          </p>
                        )}
                      </div>
                      <div className="mt-4 flex-shrink-0 sm:mt-0 sm:ml-5">
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleHealthCheck(server.id)}
                            className="inline-flex items-center px-3 py-1 border border-gray-300 dark:border-gray-600 shadow-sm text-xs font-medium rounded text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700"
                            title="Health Check"
                          >
                            <Activity className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleEdit(server)}
                            className="inline-flex items-center px-3 py-1 border border-gray-300 dark:border-gray-600 shadow-sm text-xs font-medium rounded text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700"
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm("Are you sure you want to delete this MCP server?")) {
                                deleteMutation.mutate(server.id);
                              }
                            }}
                            className="inline-flex items-center px-3 py-1 border border-red-300 dark:border-red-600 shadow-sm text-xs font-medium rounded text-red-700 dark:text-red-400 bg-white dark:bg-gray-800 hover:bg-red-50 dark:hover:bg-red-900/20"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Dialog */}
      {isDialogOpen && (
        <MCPServerDialog
          server={editingServer}
          orgId={orgId || ""}
          environments={environments}
          onClose={() => {
            setIsDialogOpen(false);
            setEditingServer(null);
          }}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
            setIsDialogOpen(false);
            setEditingServer(null);
            addToast(editingServer ? "MCP server updated" : "MCP server created", "success");
          }}
        />
      )}

      {/* Toast notifications */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`rounded-lg p-4 shadow-lg ${
              toast.type === "success"
                ? "bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200"
                : "bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200"
            }`}
          >
            <p className="text-sm font-medium">{toast.message}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

