"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Globe } from "lucide-react";

export function EnvironmentsView() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);

  const { data: environments, isLoading } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      return response.data;
    },
    enabled: !!orgId,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">
          {t("nav.environments")}
        </h1>
        <p className="text-slate-400">Manage environments</p>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {environments?.map((env: any) => (
            <div
              key={env.id}
              className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors"
            >
              <div className="flex items-center gap-3 mb-4">
                <Globe className="w-5 h-5 text-purple-400" />
                <h3 className="text-lg font-semibold text-white">{env.name}</h3>
              </div>
              <p className="text-slate-400 text-sm">{env.description || "-"}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

