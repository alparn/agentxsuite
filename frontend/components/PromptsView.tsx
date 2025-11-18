"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { promptsApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { Prompt } from "@/lib/types";
import { Plus, Edit, Trash2, Play, MessageSquare, CheckCircle2, XCircle } from "lucide-react";
import { PromptDialog } from "./PromptDialog";
import { PromptInvokeDialog } from "./PromptInvokeDialog";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error";
}

export function PromptsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
  const [invokingPrompt, setInvokingPrompt] = useState<Prompt | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [agentToken, setAgentToken] = useState<string | null>(null);

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

  // Don't auto-select environment - let user choose or show all
  // useEffect(() => {
  //   if (!envId && environments && environments.length > 0) {
  //     setCurrentEnv(environments[0].id);
  //   }
  // }, [environments, envId, setCurrentEnv]);

  // Fetch prompts
  const { data: promptsData, isLoading, error: promptsError } = useQuery({
    queryKey: ["prompts", orgId, envId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
        const response = await promptsApi.list(orgId);
        // Handle paginated response (DRF returns {results: [...], count, next, previous})
        // or direct array response
        let prompts: Prompt[] = [];
        if (Array.isArray(response.data)) {
          prompts = response.data;
        } else if (response.data?.results && Array.isArray(response.data.results)) {
          prompts = response.data.results;
        }
        // Filter by environment if selected
        if (envId) {
          return prompts.filter((p: Prompt) => {
            // Handle both string and object formats
            const pEnvId = typeof p.environment_id === "string" 
              ? p.environment_id 
              : p.environment?.id || "";
            // Compare UUIDs (both should be strings)
            return String(pEnvId).toLowerCase() === String(envId).toLowerCase();
          });
        }
        return prompts;
      } catch (error: any) {
        console.error("Error fetching prompts:", error);
        throw error;
      }
    },
    enabled: !!orgId,
  });

  const prompts = Array.isArray(promptsData) ? promptsData : [];

  // Fetch agents to get default agent for token generation
  const { data: agentsData } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/agents/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const agents = Array.isArray(agentsData) ? agentsData : [];
  const defaultAgent = agents.find((a: any) => a.name === "AgentCore" || a.enabled);

  // Generate agent token for MCP Fabric calls (if we have a default agent)
  const { data: agentTokenData } = useQuery({
    queryKey: ["agent-token-for-prompts", orgId, envId, defaultAgent?.id],
    queryFn: async () => {
      if (!orgId || !envId || !defaultAgent?.id) return null;
      try {
        const response = await api.post(`/orgs/${orgId}/agents/${defaultAgent.id}/tokens/`, {
          ttl_minutes: 60,
          scopes: ["mcp:prompts", "mcp:prompt:invoke", "mcp:manifest"],
        });
        return response.data?.token || null;
      } catch (error: any) {
        console.error("Failed to generate agent token for prompts:", error);
        return null;
      }
    },
    enabled: !!orgId && !!envId && !!defaultAgent?.id,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  // Update agentToken when data changes
  useEffect(() => {
    setAgentToken(agentTokenData || null);
  }, [agentTokenData]);

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!orgId) throw new Error("Organization ID is required");
      return promptsApi.delete(orgId, id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
      addToast(t("prompts.deleteSuccess"), "success");
    },
    onError: () => {
      addToast(t("prompts.deleteError"), "error");
    },
  });

  const addToast = (message: string, type: "success" | "error") => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  };

  const handleEdit = (prompt: Prompt) => {
    setEditingPrompt(prompt);
    setIsDialogOpen(true);
  };

  const handleInvoke = (prompt: Prompt) => {
    setInvokingPrompt(prompt);
  };

  const handleDelete = (prompt: Prompt) => {
    if (confirm(t("prompts.confirmDelete", { name: prompt.name }))) {
      deleteMutation.mutate(prompt.id);
    }
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingPrompt(null);
  };

  if (!orgId) {
    return (
      <div className="p-6 text-center text-slate-400">
        {t("common.noData")}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white">{t("prompts.title")}</h1>
          <p className="text-slate-400 mt-1">{t("prompts.subtitle")}</p>
        </div>
        <button
          onClick={() => {
            setEditingPrompt(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">{t("prompts.newPrompt")}</span>
        </button>
      </div>

      {/* Environment Filter */}
      {environments.length > 0 && (
        <div className="flex items-center gap-4">
          <label className="text-slate-300 text-sm">{t("prompts.environment")}:</label>
          <select
            value={envId || ""}
            onChange={(e) => {
              const newEnvId = e.target.value || null;
              setCurrentEnv(newEnvId);
            }}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm"
          >
            <option value="">{t("prompts.allEnvironments")}</option>
            {environments.map((env: any) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Error Display */}
      {promptsError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-red-400 text-sm">
            {t("common.error")}: {promptsError instanceof Error ? promptsError.message : String(promptsError)}
          </p>
        </div>
      )}

      {/* Toast Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => {
          const Icon = toast.type === "success" ? CheckCircle2 : XCircle;
          return (
            <div
              key={toast.id}
              className={`flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg ${
                toast.type === "success" ? "bg-green-600" : "bg-red-600"
              } text-white`}
            >
              <Icon className="w-5 h-5" />
              <span>{toast.message}</span>
            </div>
          );
        })}
      </div>

      {/* Prompts List */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : promptsError ? (
        <div className="text-center py-12 text-red-400">
          {t("common.error")}: {promptsError instanceof Error ? promptsError.message : String(promptsError)}
        </div>
      ) : !promptsData ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : prompts.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          {envId 
            ? t("prompts.noPrompts") + ` (${t("prompts.environment")}: ${environments.find((e: any) => e.id === envId)?.name || envId})`
            : t("prompts.noPrompts")
          }
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left p-4 text-slate-300">{t("common.name")}</th>
                  <th className="text-left p-4 text-slate-300">{t("common.description")}</th>
                  <th className="text-left p-4 text-slate-300">{t("prompts.environment")}</th>
                  <th className="text-left p-4 text-slate-300">{t("prompts.usesResources")}</th>
                  <th className="text-left p-4 text-slate-300">{t("common.status")}</th>
                  <th className="text-right p-4 text-slate-300">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {prompts.map((prompt: Prompt) => (
                  <tr key={prompt.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <MessageSquare className="w-4 h-4 text-purple-400" />
                        <span className="text-white">{prompt.name}</span>
                      </div>
                    </td>
                    <td className="p-4 text-slate-300 text-sm max-w-md truncate">
                      {prompt.description || "-"}
                    </td>
                    <td className="p-4 text-slate-300">{prompt.environment?.name || "-"}</td>
                    <td className="p-4 text-slate-400 text-sm">
                      {prompt.uses_resources?.length > 0
                        ? `${prompt.uses_resources.length} ${t("common.add")}`
                        : "-"}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          prompt.enabled
                            ? "bg-green-500/20 text-green-400"
                            : "bg-red-500/20 text-red-400"
                        }`}
                      >
                        {prompt.enabled ? t("common.enabled") : t("common.disabled")}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleInvoke(prompt)}
                          className="p-2 text-slate-400 hover:text-green-400 rounded-lg hover:bg-slate-800"
                          title={t("prompts.invoke")}
                        >
                          <Play className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleEdit(prompt)}
                          className="p-2 text-slate-400 hover:text-purple-400 rounded-lg hover:bg-slate-800"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(prompt)}
                          className="p-2 text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-800"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-4">
            {prompts.map((prompt: Prompt) => (
              <div
                key={prompt.id}
                className="bg-slate-800 rounded-lg p-4 border border-slate-700"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="w-5 h-5 text-purple-400" />
                    <div>
                      <h3 className="text-white font-medium">{prompt.name}</h3>
                      {prompt.description && (
                        <p className="text-slate-400 text-sm mt-1">{prompt.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleInvoke(prompt)}
                      className="p-2 text-slate-400 hover:text-green-400 rounded-lg hover:bg-slate-700"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleEdit(prompt)}
                      className="p-2 text-slate-400 hover:text-purple-400 rounded-lg hover:bg-slate-700"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(prompt)}
                      className="p-2 text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">{t("prompts.environment")}:</span>
                    <span className="text-slate-300">{prompt.environment?.name || "-"}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">{t("prompts.usesResources")}:</span>
                    <span className="text-slate-300">
                      {prompt.uses_resources?.length > 0
                        ? `${prompt.uses_resources.length}`
                        : "-"}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">{t("common.status")}:</span>
                    <span
                      className={`${
                        prompt.enabled ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      {prompt.enabled ? t("common.enabled") : t("common.disabled")}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Dialogs */}
      <PromptDialog
        isOpen={isDialogOpen}
        prompt={editingPrompt}
        onClose={handleCloseDialog}
        orgId={orgId || ""}
        environments={environments}
      />

      {invokingPrompt && (
        <PromptInvokeDialog
          prompt={invokingPrompt}
          onClose={() => setInvokingPrompt(null)}
          orgId={orgId || ""}
          envId={envId || ""}
          agentToken={agentToken}
        />
      )}
    </div>
  );
}

