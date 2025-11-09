"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Filter, Download, CheckCircle2, XCircle, Clock } from "lucide-react";
import { formatDuration } from "@/lib/utils";

export function RunsView() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);
  const [selectedRun, setSelectedRun] = useState<any>(null);
  const [filters, setFilters] = useState({
    status: "",
    agent: "",
    tool: "",
  });

  const { data: runs, isLoading } = useQuery({
    queryKey: ["runs", orgId, filters],
    queryFn: async () => {
      if (!orgId) return [];
      const params = new URLSearchParams();
      if (filters.status) params.append("status", filters.status);
      if (filters.agent) params.append("agent", filters.agent);
      if (filters.tool) params.append("tool", filters.tool);
      const response = await api.get(
        `/orgs/${orgId}/runs/?${params.toString()}`
      );
      return response.data;
    },
    enabled: !!orgId,
  });

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { color: string; icon: any }> = {
      succeeded: { color: "bg-green-500/20 text-green-400", icon: CheckCircle2 },
      failed: { color: "bg-red-500/20 text-red-400", icon: XCircle },
      running: { color: "bg-yellow-500/20 text-yellow-400", icon: Clock },
    };
    const statusInfo = statusMap[status] || statusMap.succeeded;
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("runs.title")}
          </h1>
          <p className="text-slate-400">Monitor tool executions</p>
        </div>
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
                  runs?.map((run: any) => (
                    <tr
                      key={run.id}
                      className="hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => setSelectedRun(run)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-mono">
                        {run.id.slice(0, 8)}...
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {run.tool?.name || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {run.agent?.name || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {new Date(run.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {run.duration ? formatDuration(run.duration) : "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(run.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedRun(run);
                          }}
                          className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedRun && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-y-auto p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Run Details</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="text-slate-400">Status:</span>{" "}
                {getStatusBadge(selectedRun.status)}
              </div>
              <div>
                <span className="text-slate-400">Duration:</span>{" "}
                <span className="text-white">
                  {selectedRun.duration
                    ? formatDuration(selectedRun.duration)
                    : "-"}
                </span>
              </div>
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-400 mb-2">
                {t("runs.logs")}
              </h3>
              <pre className="bg-slate-800 p-4 rounded-lg text-sm text-slate-300 overflow-x-auto">
                {selectedRun.logs || "No logs available"}
              </pre>
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-400 mb-2">
                {t("tools.input")}
              </h3>
              <pre className="bg-slate-800 p-4 rounded-lg text-sm text-slate-300 overflow-x-auto">
                {JSON.stringify(selectedRun.input || {}, null, 2)}
              </pre>
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-400 mb-2">
                {t("tools.output")}
              </h3>
              <pre className="bg-slate-800 p-4 rounded-lg text-sm text-slate-300 overflow-x-auto">
                {JSON.stringify(selectedRun.output || {}, null, 2)}
              </pre>
            </div>
            <button
              onClick={() => setSelectedRun(null)}
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

