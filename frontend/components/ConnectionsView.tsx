"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, TestTube, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { ConnectionDialog } from "./ConnectionDialog";

export function ConnectionsView() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedConnection, setSelectedConnection] = useState<any>(null);

  const { data: connections, isLoading } = useQuery({
    queryKey: ["connections", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/connections/`);
      return response.data;
    },
    enabled: !!orgId,
  });

  const testMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await api.post(`/connections/${id}/test/`);
      return response.data;
    },
  });

  const syncMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await api.post(`/connections/${id}/sync/`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      queryClient.invalidateQueries({ queryKey: ["tools"] });
    },
  });

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { color: string; icon: any }> = {
      active: { color: "bg-green-500/20 text-green-400", icon: CheckCircle2 },
      inactive: { color: "bg-red-500/20 text-red-400", icon: XCircle },
      testing: { color: "bg-yellow-500/20 text-yellow-400", icon: RefreshCw },
    };
    const statusInfo = statusMap[status] || statusMap.inactive;
    const Icon = statusInfo.icon;
    return (
      <span className={`px-2 py-1 text-xs rounded-full flex items-center gap-1 ${statusInfo.color}`}>
        <Icon className="w-3 h-3" />
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("connections.title")}
          </h1>
          <p className="text-slate-400">Manage your MCP server connections</p>
        </div>
        <button
          onClick={() => {
            setSelectedConnection(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
        >
          <Plus className="w-5 h-5" />
          {t("connections.newConnection")}
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
                    {t("connections.endpoint")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("connections.authMethod")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.status")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("connections.lastSync")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {connections?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  connections?.map((conn: any) => (
                    <tr key={conn.id} className="hover:bg-slate-800/50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {conn.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {conn.endpoint}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {conn.auth_method}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(conn.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {conn.last_seen_at
                          ? new Date(conn.last_seen_at).toLocaleString()
                          : "Never"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => testMutation.mutate(conn.id)}
                            disabled={testMutation.isPending}
                            className="p-2 text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                            title={t("connections.testConnection")}
                          >
                            <TestTube className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => syncMutation.mutate(conn.id)}
                            disabled={syncMutation.isPending}
                            className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                            title={t("connections.syncTools")}
                          >
                            <RefreshCw className="w-4 h-4" />
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

      <ConnectionDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        connection={selectedConnection}
        orgId={orgId}
      />
    </div>
  );
}

