"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, runsApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { RunList, RunDetail } from "@/lib/types";
import { Filter, CheckCircle2, XCircle, Clock, RefreshCw } from "lucide-react";
import { formatDuration } from "@/lib/utils";

export function RunsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: "",
    agent: "",
    tool: "",
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

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

  const { data: runsResponse, isLoading, refetch } = useQuery({
    queryKey: ["runs", orgId, filters],
    queryFn: async () => {
      if (!orgId) return { count: 0, results: [] };
      return runsApi.list(orgId, filters).then(res => res.data);
    },
    enabled: !!orgId,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["runs", orgId] }),
        refetch(),
      ]);
      if (selectedRunId) {
        queryClient.invalidateQueries({ queryKey: ["run-detail", orgId, selectedRunId] });
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const runs: RunList[] = runsResponse?.results || [];

  // Fetch detailed run data when selected
  const { data: selectedRunDetail } = useQuery({
    queryKey: ["run-detail", orgId, selectedRunId],
    queryFn: async () => {
      if (!orgId || !selectedRunId) return null;
      return runsApi.get(orgId, selectedRunId).then(res => res.data);
    },
    enabled: !!orgId && !!selectedRunId,
  });

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { color: string; icon: any }> = {
      succeeded: { color: "bg-green-500/20 text-green-400", icon: CheckCircle2 },
      failed: { color: "bg-red-500/20 text-red-400", icon: XCircle },
      running: { color: "bg-yellow-500/20 text-yellow-400", icon: Clock },
      pending: { color: "bg-slate-500/20 text-slate-400", icon: Clock },
    };
    const statusInfo = statusMap[status] || statusMap.pending;
    const Icon = statusInfo.icon;
    return (
      <span
        className={`px-2 py-1 text-xs rounded-full flex items-center gap-1 ${statusInfo.color}`}
      >
        <Icon className="w-3 h-3" />
        {status}
      </span>
    );
  };

  const calculateDuration = (run: RunList): number | null => {
    if (!run.started_at) return null;
    const start = new Date(run.started_at).getTime();
    const end = run.ended_at ? new Date(run.ended_at).getTime() : Date.now();
    return Math.floor((end - start) / 1000); // Duration in seconds
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("runs.title")}
          </h1>
          <p className="text-slate-400">Monitor tool executions</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing || isLoading}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title={t("common.refresh") || "Refresh"}
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
          <span>{t("common.refresh") || "Refresh"}</span>
        </button>
      </div>

      {/* Filters */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <div className="flex items-center gap-4">
          <Filter className="w-5 h-5 text-slate-400" />
          <select
            value={filters.status}
            onChange={(e) =>
              setFilters({ ...filters, status: e.target.value })
            }
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="">All Status</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
          <input
            type="text"
            placeholder="Filter by agent..."
            value={filters.agent}
            onChange={(e) =>
              setFilters({ ...filters, agent: e.target.value })
            }
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <input
            type="text"
            placeholder="Filter by tool..."
            value={filters.tool}
            onChange={(e) =>
              setFilters({ ...filters, tool: e.target.value })
            }
            className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
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
                    {t("runs.runId")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("runs.tool")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("runs.agent")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("runs.started")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("runs.duration")}
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
                {runs?.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  runs?.map((run: RunList) => {
                    const duration = calculateDuration(run);
                    return (
                      <tr
                        key={run.id}
                        className="hover:bg-slate-800/50 cursor-pointer"
                        onClick={() => setSelectedRunId(run.id)}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-mono">
                          {run.id.slice(0, 8)}...
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                          {run.tool_name || "-"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                          {run.agent_name || "-"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                          {run.started_at 
                            ? new Date(run.started_at).toLocaleString()
                            : new Date(run.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                          {duration !== null ? formatDuration(duration) : "-"}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {getStatusBadge(run.status)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedRunId(run.id);
                            }}
                            className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedRunId && selectedRunDetail && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Run Details</h2>
              <button
                onClick={() => setSelectedRunId(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            
            {/* Quick Summary */}
            <div className="grid grid-cols-2 gap-3 mb-6 p-3 bg-slate-900/30 rounded-lg">
              <div>
                <div className="text-slate-500 text-xs mb-1">Status</div>
                {getStatusBadge(selectedRunDetail.status)}
              </div>
              <div>
                <div className="text-slate-500 text-xs mb-1">Duration</div>
                <div className="text-white font-medium">
                  {selectedRunDetail.started_at && selectedRunDetail.ended_at
                    ? formatDuration(
                        Math.floor(
                          (new Date(selectedRunDetail.ended_at).getTime() -
                            new Date(selectedRunDetail.started_at).getTime()) /
                            1000
                        )
                      )
                    : "-"}
                </div>
              </div>
              <div className="col-span-2">
                <div className="text-slate-500 text-xs mb-1">Run ID</div>
                <div className="text-white font-mono text-xs break-all">{selectedRunDetail.id}</div>
              </div>
            </div>

            {/* Agent Details */}
            <details open className="mb-3 p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
              <summary className="cursor-pointer font-medium text-white hover:text-purple-400 transition-colors">
                🤖 Agent: <span className="text-purple-400">{selectedRunDetail.agent.name}</span>
              </summary>
              <div className="mt-3 space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-500">Version:</span> <span className="text-white">{selectedRunDetail.agent.version}</span></div>
                  <div><span className="text-slate-500">Mode:</span> <span className="text-white">{selectedRunDetail.agent.mode}</span></div>
                  <div><span className="text-slate-500">Enabled:</span> <span className={selectedRunDetail.agent.enabled ? "text-green-400" : "text-red-400"}>{selectedRunDetail.agent.enabled ? "✓ Yes" : "✗ No"}</span></div>
                  <div><span className="text-slate-500">Slug:</span> <span className="text-white font-mono text-xs">{selectedRunDetail.agent.slug}</span></div>
                </div>
                {selectedRunDetail.agent.connection && (
                  <div className="mt-2 p-2 bg-slate-900/50 rounded border border-slate-700/30">
                    <div className="text-slate-400 text-xs font-semibold mb-1">🔗 Connection</div>
                    <div className="text-white text-sm">{selectedRunDetail.agent.connection.name}</div>
                    <div className="text-slate-400 text-xs font-mono mt-1">{selectedRunDetail.agent.connection.endpoint}</div>
                    <div className="flex gap-3 text-xs mt-2">
                      <span><span className="text-slate-500">Status:</span> <span className={selectedRunDetail.agent.connection.status === 'ok' ? 'text-green-400' : 'text-red-400'}>{selectedRunDetail.agent.connection.status}</span></span>
                      <span><span className="text-slate-500">Auth:</span> <span className="text-white">{selectedRunDetail.agent.connection.auth_method}</span></span>
                    </div>
                  </div>
                )}
              </div>
            </details>

            {/* Tool Details */}
            <details open className="mb-3 p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
              <summary className="cursor-pointer font-medium text-white hover:text-purple-400 transition-colors">
                🔧 Tool: <span className="text-purple-400">{selectedRunDetail.tool.name}</span>
              </summary>
              <div className="mt-3 space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-500">Version:</span> <span className="text-white">{selectedRunDetail.tool.version}</span></div>
                  <div><span className="text-slate-500">Enabled:</span> <span className={selectedRunDetail.tool.enabled ? "text-green-400" : "text-red-400"}>{selectedRunDetail.tool.enabled ? "✓ Yes" : "✗ No"}</span></div>
                  <div><span className="text-slate-500">Sync:</span> <span className="text-white">{selectedRunDetail.tool.sync_status}</span></div>
                  <div><span className="text-slate-500">Synced:</span> <span className="text-white text-xs">{selectedRunDetail.tool.synced_at ? new Date(selectedRunDetail.tool.synced_at).toLocaleDateString("de-DE") : "-"}</span></div>
                </div>
                {selectedRunDetail.tool.connection && (
                  <div className="mt-2 p-2 bg-slate-900/50 rounded border border-slate-700/30">
                    <div className="text-slate-400 text-xs font-semibold mb-1">🔗 Connection</div>
                    <div className="text-white text-sm">{selectedRunDetail.tool.connection.name}</div>
                    <div className="text-slate-400 text-xs font-mono mt-1">{selectedRunDetail.tool.connection.endpoint}</div>
                  </div>
                )}
                {selectedRunDetail.tool.schema_json && Object.keys(selectedRunDetail.tool.schema_json).length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-slate-400 hover:text-white">
                      📋 Schema {selectedRunDetail.tool.schema_json.properties && `(${Object.keys(selectedRunDetail.tool.schema_json.properties).length} properties)`}
                    </summary>
                    <pre className="mt-2 bg-slate-950 p-3 rounded text-xs overflow-x-auto max-h-48 border border-slate-700/30">
                      {JSON.stringify(selectedRunDetail.tool.schema_json, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            </details>

            {/* Environment & Org */}
            <details className="mb-3 p-3 bg-slate-800/40 rounded-lg border border-slate-700/50">
              <summary className="cursor-pointer font-medium text-white hover:text-purple-400 transition-colors">
                🌍 Environment & Organization
              </summary>
              <div className="mt-3 space-y-2 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-slate-500">Environment:</span> <span className="text-white">{selectedRunDetail.environment.name}</span></div>
                  <div><span className="text-slate-500">Type:</span> <span className="text-white">{selectedRunDetail.environment.type}</span></div>
                  <div><span className="text-slate-500">Organization:</span> <span className="text-white">{selectedRunDetail.organization.name}</span></div>
                  <div><span className="text-slate-500">Org ID:</span> <span className="text-white font-mono text-xs">{selectedRunDetail.organization.id.slice(0, 12)}...</span></div>
                </div>
              </div>
            </details>

            {/* Timestamps */}
            <div className="mb-4 p-3 bg-slate-900/30 rounded-lg border border-slate-700/30">
              <div className="text-slate-400 text-xs font-semibold mb-2">⏱️ Timestamps</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-slate-500">Started:</span> <span className="text-white text-xs">{selectedRunDetail.started_at ? new Date(selectedRunDetail.started_at).toLocaleString("de-DE") : "-"}</span></div>
                <div><span className="text-slate-500">Ended:</span> <span className="text-white text-xs">{selectedRunDetail.ended_at ? new Date(selectedRunDetail.ended_at).toLocaleString("de-DE") : "-"}</span></div>
                <div><span className="text-slate-500">Created:</span> <span className="text-white text-xs">{selectedRunDetail.created_at ? new Date(selectedRunDetail.created_at).toLocaleString("de-DE") : "-"}</span></div>
                <div><span className="text-slate-500">Updated:</span> <span className="text-white text-xs">{selectedRunDetail.updated_at ? new Date(selectedRunDetail.updated_at).toLocaleString("de-DE") : "-"}</span></div>
              </div>
            </div>

            {/* Error */}
            {selectedRunDetail.error_text && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-red-400 mb-2">❌ Error</h3>
                <pre className="bg-red-900/20 border border-red-500/30 p-4 rounded-lg text-sm text-red-300 overflow-x-auto">
                  {selectedRunDetail.error_text}
                </pre>
              </div>
            )}

            {/* Input */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">📥 {t("tools.input")}</h3>
              <pre className="bg-slate-900/50 border border-slate-700/50 p-4 rounded-lg text-sm text-slate-300 overflow-x-auto max-h-48">
                {JSON.stringify(selectedRunDetail.input_json || {}, null, 2)}
              </pre>
            </div>

            {/* Output */}
            <div className="mb-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">📤 {t("tools.output")}</h3>
              <pre className="bg-slate-900/50 border border-slate-700/50 p-4 rounded-lg text-sm text-slate-300 overflow-x-auto max-h-48">
                {JSON.stringify(selectedRunDetail.output_json || {}, null, 2)}
              </pre>
            </div>
            <button
              onClick={() => setSelectedRunId(null)}
              className="w-full px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

