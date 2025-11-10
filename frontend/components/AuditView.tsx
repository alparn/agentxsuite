"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Download, FileText } from "lucide-react";

export function AuditView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();

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
    queryKey: ["audit", orgId],
    queryFn: async () => {
      if (!orgId) {
        console.log("AuditView: orgId is null, skipping fetch");
        return [];
      }
      try {
        console.log("AuditView: Fetching audit logs for orgId:", orgId);
        const response = await api.get(`/orgs/${orgId}/audit/`);
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("audit.title")}
          </h1>
          <p className="text-slate-400">System audit logs and events</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors">
          <Download className="w-5 h-5" />
          {t("audit.export")}
        </button>
      </div>

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
                    {t("audit.actor")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.action")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.object")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("audit.details")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {auditLogs?.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  auditLogs?.map((log: any) => (
                    <tr key={log.id} className="hover:bg-slate-800/50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.actor || "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.action}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {log.object_type}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-300">
                        {log.details || "-"}
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

