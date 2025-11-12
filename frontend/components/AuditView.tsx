"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { auditApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Download, FileText, X } from "lucide-react";
import type { AuditEvent } from "@/lib/types";

export function AuditView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const [filters, setFilters] = useState({
    subject: "",
    action: "",
    target: "",
    decision: "" as "" | "allow" | "deny",
    ts_from: "",
    ts_to: "",
  });
  const [showFilters, setShowFilters] = useState(false);

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

  const { data: auditLogsData, isLoading, error: auditError } = useQuery({
    queryKey: ["audit", orgId, filters],
    queryFn: async () => {
      if (!orgId) {
        console.log("AuditView: orgId is null, skipping fetch");
        return [];
      }
      try {
        console.log("AuditView: Fetching audit logs for orgId:", orgId);
        
        // Build params object, only including non-empty filters
        const params: Record<string, string> = {};
        if (filters.subject) params.subject = filters.subject;
        if (filters.action) params.action = filters.action;
        if (filters.target) params.target = filters.target;
        if (filters.decision) params.decision = filters.decision;
        if (filters.ts_from) params.ts_from = filters.ts_from;
        if (filters.ts_to) params.ts_to = filters.ts_to;

        const response = await auditApi.list(orgId, params);
        console.log("AuditView: API response:", response.data);
        // Handle paginated response (DRF returns {results: [...], count, next, previous})
        // or direct array response
        if (Array.isArray(response.data)) {
          console.log("AuditView: Response is array, length:", response.data.length);
          return response.data;
        } else if (response.data?.results && Array.isArray(response.data.results)) {
          console.log("AuditView: Response is paginated, results length:", response.data.results.length);
          return response.data.results;
        }
        console.log("AuditView: Response format not recognized, returning empty array");
        return [];
      } catch (error: any) {
        console.error("AuditView: Error fetching audit logs:", error);
        console.error("AuditView: Error response:", error.response?.data);
        throw error;
      }
    },
    enabled: !!orgId,
  });

  const auditLogs = Array.isArray(auditLogsData) ? auditLogsData : [];

  const resetFilters = () => {
    setFilters({
      subject: "",
      action: "",
      target: "",
      decision: "",
      ts_from: "",
      ts_to: "",
    });
  };

  const hasActiveFilters = Object.values(filters).some((v) => v !== "");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("audit.title")}
          </h1>
          <p className="text-slate-400">System audit logs and events</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
          >
            <FileText className="w-5 h-5" />
            {showFilters ? "Hide Filters" : "Show Filters"}
            {hasActiveFilters && (
              <span className="ml-2 px-2 py-0.5 bg-purple-500 text-white text-xs rounded-full">
                {Object.values(filters).filter((v) => v !== "").length}
              </span>
            )}
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors">
            <Download className="w-5 h-5" />
            {t("audit.export")}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      {showFilters && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Subject
              </label>
              <input
                type="text"
                value={filters.subject}
                onChange={(e) => setFilters({ ...filters, subject: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="user:123"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Action
              </label>
              <select
                value={filters.action}
                onChange={(e) => setFilters({ ...filters, action: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="">All Actions</option>
                <option value="tool.invoke">Tool Invoke</option>
                <option value="agent.invoke">Agent Invoke</option>
                <option value="resource.read">Resource Read</option>
                <option value="resource.write">Resource Write</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Target
              </label>
              <input
                type="text"
                value={filters.target}
                onChange={(e) => setFilters({ ...filters, target: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="tool:pdf/*"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Decision
              </label>
              <select
                value={filters.decision}
                onChange={(e) => setFilters({ ...filters, decision: e.target.value as "" | "allow" | "deny" })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                <option value="">All Decisions</option>
                <option value="allow">Allow</option>
                <option value="deny">Deny</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                From Date
              </label>
              <input
                type="datetime-local"
                value={filters.ts_from}
                onChange={(e) => setFilters({ ...filters, ts_from: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                To Date
              </label>
              <input
                type="datetime-local"
                value={filters.ts_to}
                onChange={(e) => setFilters({ ...filters, ts_to: e.target.value })}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>

          {hasActiveFilters && (
            <div className="flex justify-end">
              <button
                onClick={resetFilters}
                className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
              >
                <X className="w-4 h-4" />
                Reset Filters
              </button>
            </div>
          )}
        </div>
      )}

      {auditError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg mb-4">
          <p className="text-sm text-red-400">
            Error loading audit logs: {auditError instanceof Error ? auditError.message : String(auditError)}
          </p>
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
                    {t("audit.time")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Subject
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.actor")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.action")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Target
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Decision
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Rule ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.details")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {auditLogs?.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  auditLogs?.map((log: AuditEvent) => (
                    <tr key={log.id} className="hover:bg-slate-800/50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.ts ? new Date(log.ts).toLocaleString() : new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.subject || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.actor || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.action || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.target || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {log.decision ? (
                          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                            log.decision === "allow"
                              ? "bg-green-500/20 text-green-400"
                              : "bg-red-500/20 text-red-400"
                          }`}>
                            {log.decision.toUpperCase()}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.rule_id ? (
                          <span className="text-purple-400 hover:text-purple-300 cursor-pointer">
                            {log.rule_id}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">
                        <div className="max-w-md">
                          {log.context && Object.keys(log.context).length > 0 ? (
                            <details className="cursor-pointer">
                              <summary className="text-purple-400 hover:text-purple-300">
                                View Context
                              </summary>
                              <pre className="mt-2 p-2 bg-slate-800 rounded text-xs overflow-x-auto">
                                {JSON.stringify(log.context, null, 2)}
                              </pre>
                            </details>
                          ) : (
                            log.details || "-"
                          )}
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
    </div>
  );
}
