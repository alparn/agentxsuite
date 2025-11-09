"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, Power, PowerOff, Edit, Radio } from "lucide-react";
import { AgentDialog } from "./AgentDialog";

export function AgentsView() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);
  const queryClient = useQueryClient();
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<any>(null);

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

  const pingMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.post(`/orgs/${orgId}/agents/${id}/ping/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("agents.title")}
          </h1>
          <p className="text-slate-400">Manage your AI agents</p>
        </div>
        <button
          onClick={() => {
            setEditingAgent(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
        >
          <Plus className="w-5 h-5" />
          {t("agents.newAgent")}
        </button>
      </div>

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
                    {t("agents.environment")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("agents.version")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("agents.connection")}
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
                {agents?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  agents?.map((agent: any) => (
                    <tr
                      key={agent.id}
                      className="hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => setSelectedAgent(agent)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-medium">
                        {agent.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.environment?.name || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.version}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {agent.connection?.name || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
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
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              pingMutation.mutate(agent.id);
                            }}
                            className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                            title={t("agents.pingAgent")}
                          >
                            <Radio className="w-4 h-4" />
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
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
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
                <span className="text-slate-400 dark:text-slate-500">Connection:</span>{" "}
                <span className="text-slate-900 dark:text-white">
                  {selectedAgent.connection?.name || "-"}
                </span>
              </div>
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

