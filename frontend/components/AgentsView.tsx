"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, Power, PowerOff, Edit, Radio, X, CheckCircle2, AlertCircle, AlertTriangle } from "lucide-react";
import { AgentDialog } from "./AgentDialog";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "warning";
}

export function AgentsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<any>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

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

  const { data: agentsData, isLoading } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/agents/`);
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

  const agents = Array.isArray(agentsData) ? agentsData : [];

  const toggleMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: string; enabled: boolean }) => {
      return api.patch(`/orgs/${orgId}/agents/${id}/`, { enabled });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });

  const addToast = (message: string, type: "success" | "error" | "warning") => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type }]);
    // Auto-remove after 5 seconds
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  const pingMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.post(`/orgs/${orgId}/agents/${id}/ping/`);
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      
      // Show feedback based on response
      const data = response.data;
      const status = data?.status || "unknown";
      const message = data?.message || t("agents.pingSuccess");
      
      if (status === "success") {
        addToast(message, "success");
      } else if (status === "warning") {
        addToast(message, "warning");
      } else if (status === "error") {
        addToast(message, "error");
      } else {
        addToast(message, "success");
      }
    },
    onError: (error: any) => {
      const errorMessage = error.response?.data?.message || error.message || t("agents.pingError");
      addToast(errorMessage, "error");
    },
  });

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Toast Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border min-w-[300px] max-w-[500px] animate-in slide-in-from-right ${
              toast.type === "success"
                ? "bg-green-500/10 border-green-500/20 text-green-300"
                : toast.type === "error"
                ? "bg-red-500/10 border-red-500/20 text-red-300"
                : "bg-yellow-500/10 border-yellow-500/20 text-yellow-300"
            }`}
          >
            {toast.type === "success" && <CheckCircle2 className="w-5 h-5 flex-shrink-0" />}
            {toast.type === "error" && <AlertCircle className="w-5 h-5 flex-shrink-0" />}
            {toast.type === "warning" && <AlertTriangle className="w-5 h-5 flex-shrink-0" />}
            <p className="flex-1 text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1 sm:mb-2">
            {t("agents.title")}
          </h1>
          <p className="text-sm sm:text-base text-slate-400">Manage your AI agents</p>
        </div>
        <button
          onClick={() => {
            setEditingAgent(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all text-sm sm:text-base"
        >
          <Plus className="w-4 h-4 sm:w-5 sm:h-5" />
          {t("agents.newAgent")}
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : agents?.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center text-slate-400">
          {t("common.noData")}
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-800">
                  <tr>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("common.name")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("agents.environment")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("agents.version")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("agents.mode")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("agents.connection")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("common.status")}
                    </th>
                    <th className="px-4 lg:px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                      {t("common.actions")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {agents?.map((agent: any) => (
                    <tr
                      key={agent.id}
                      className="hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => setSelectedAgent(agent)}
                    >
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-medium">
                        {agent.name}
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.environment?.name || "-"}
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.version}
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          agent.mode === "runner"
                            ? "bg-blue-500/20 text-blue-400"
                            : "bg-purple-500/20 text-purple-400"
                        }`}>
                          {agent.mode === "runner" ? t("agents.modeRunner") : t("agents.modeCaller")}
                        </span>
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.connection?.name || "-"}
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs rounded-full ${
                            agent.enabled
                              ? "bg-green-500/20 text-green-400"
                              : "bg-slate-500/20 text-slate-400"
                          }`}
                        >
                          {agent.enabled ? t("agents.enabled") : t("agents.disabled")}
                        </span>
                      </td>
                      <td className="px-4 lg:px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              pingMutation.mutate(agent.id);
                            }}
                            disabled={pingMutation.isPending}
                            className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            title={pingMutation.isPending ? t("common.loading") : t("agents.pingAgent")}
                          >
                            <Radio className={`w-4 h-4 ${pingMutation.isPending ? "animate-pulse" : ""}`} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleMutation.mutate({
                                id: agent.id,
                                enabled: !agent.enabled,
                              });
                            }}
                            className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                            title={agent.enabled ? t("agents.disable") : t("agents.enable")}
                          >
                            {agent.enabled ? (
                              <PowerOff className="w-4 h-4" />
                            ) : (
                              <Power className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingAgent(agent);
                              setIsDialogOpen(true);
                            }}
                            className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                            title={t("common.edit")}
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-3">
            {agents?.map((agent: any) => (
              <div
                key={agent.id}
                onClick={() => setSelectedAgent(agent)}
                className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3 cursor-pointer hover:bg-slate-800/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-base font-medium text-slate-300 mb-1">{agent.name}</h3>
                    <div className="space-y-1 text-sm text-slate-400">
                      <div>
                        <span className="font-medium">{t("agents.environment")}:</span> {agent.environment?.name || "-"}
                      </div>
                      <div>
                        <span className="font-medium">{t("agents.version")}:</span> {agent.version}
                      </div>
                      <div>
                        <span className="font-medium">{t("agents.mode")}:</span>{" "}
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          agent.mode === "runner"
                            ? "bg-blue-500/20 text-blue-400"
                            : "bg-purple-500/20 text-purple-400"
                        }`}>
                          {agent.mode === "runner" ? t("agents.modeRunner") : t("agents.modeCaller")}
                        </span>
                      </div>
                      <div>
                        <span className="font-medium">{t("agents.connection")}:</span> {agent.connection?.name || "-"}
                      </div>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-1 text-xs rounded-full flex-shrink-0 ${
                      agent.enabled
                        ? "bg-green-500/20 text-green-400"
                        : "bg-slate-500/20 text-slate-400"
                    }`}
                  >
                    {agent.enabled ? t("agents.enabled") : t("agents.disabled")}
                  </span>
                </div>
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      pingMutation.mutate(agent.id);
                    }}
                    disabled={pingMutation.isPending}
                    className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title={pingMutation.isPending ? t("common.loading") : t("agents.pingAgent")}
                  >
                    <Radio className={`w-4 h-4 ${pingMutation.isPending ? "animate-pulse" : ""}`} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleMutation.mutate({
                        id: agent.id,
                        enabled: !agent.enabled,
                      });
                    }}
                    className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                    title={agent.enabled ? t("agents.disable") : t("agents.enable")}
                  >
                    {agent.enabled ? (
                      <PowerOff className="w-4 h-4" />
                    ) : (
                      <Power className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingAgent(agent);
                      setIsDialogOpen(true);
                    }}
                    className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                    title={t("common.edit")}
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {selectedAgent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-2xl p-6">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-4">
              {selectedAgent.name}
            </h2>
            <div className="space-y-4">
              <div>
                <span className="text-slate-400 dark:text-slate-500">Version:</span>{" "}
                <span className="text-slate-900 dark:text-white">{selectedAgent.version}</span>
              </div>
              <div>
                <span className="text-slate-400 dark:text-slate-500">Environment:</span>{" "}
                <span className="text-slate-900 dark:text-white">
                  {selectedAgent.environment?.name || "-"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 dark:text-slate-500">Mode:</span>{" "}
                <span className={`px-2 py-1 text-xs rounded-full ${
                  selectedAgent.mode === "runner"
                    ? "bg-blue-500/20 text-blue-400"
                    : "bg-purple-500/20 text-purple-400"
                }`}>
                  {selectedAgent.mode === "runner" ? t("agents.modeRunner") : t("agents.modeCaller")}
                </span>
              </div>
              <div>
                <span className="text-slate-400 dark:text-slate-500">Connection:</span>{" "}
                <span className="text-slate-900 dark:text-white">
                  {selectedAgent.connection?.name || "-"}
                </span>
              </div>
              {selectedAgent.mode === "caller" && (
                <>
                  <div>
                    <span className="text-slate-400 dark:text-slate-500">Inbound Auth Method:</span>{" "}
                    <span className="text-slate-900 dark:text-white">
                      {selectedAgent.inbound_auth_method || "-"}
                    </span>
                  </div>
                  {selectedAgent.inbound_auth_method !== "none" && (
                    <div>
                      <span className="text-slate-400 dark:text-slate-500">Inbound Secret Ref:</span>{" "}
                      <span className="text-slate-900 dark:text-white font-mono text-sm">
                        {selectedAgent.inbound_secret_ref ? "***" : "-"}
                      </span>
                    </div>
                  )}
                </>
              )}
              <div>
                <span className="text-slate-400 dark:text-slate-500">Status:</span>{" "}
                <span className={`px-2 py-1 text-xs rounded-full ${
                  selectedAgent.enabled
                    ? "bg-green-500/20 text-green-400"
                    : "bg-slate-500/20 text-slate-400"
                }`}>
                  {selectedAgent.enabled ? t("agents.enabled") : t("agents.disabled")}
                </span>
              </div>
              <button
                onClick={() => setSelectedAgent(null)}
                className="mt-4 px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      <AgentDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setEditingAgent(null);
        }}
        agent={editingAgent}
        orgId={orgId}
      />
    </div>
  );
}

