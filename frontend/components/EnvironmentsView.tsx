"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Globe, Plus, Edit, Trash2 } from "lucide-react";
import { EnvironmentDialog } from "./EnvironmentDialog";

export function EnvironmentsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingEnvironment, setEditingEnvironment] = useState<any>(null);

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

  const { data: environmentsData, isLoading } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
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

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/environments/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments", orgId] });
    },
  });

  const handleDelete = (env: any) => {
    if (window.confirm(t("environments.confirmDelete", { name: env.name }))) {
      deleteMutation.mutate(env.id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white dark:text-slate-100 mb-2">
            {t("nav.environments")}
          </h1>
          <p className="text-slate-400">Manage environments</p>
        </div>
        <button
          onClick={() => {
            setEditingEnvironment(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
        >
          <Plus className="w-5 h-5" />
          {t("environments.newEnvironment")}
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {environments?.length === 0 ? (
            <div className="col-span-full text-center py-12 text-slate-400">
              {t("common.noData")}
            </div>
          ) : (
            environments?.map((env: any) => (
            <div
              key={env.id}
              className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors relative group"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Globe className="w-5 h-5 text-purple-400" />
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    {env.name}
                  </h3>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => {
                      setEditingEnvironment(env);
                      setIsDialogOpen(true);
                    }}
                    className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-all"
                    title={t("common.edit")}
                  >
                    <Edit className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(env)}
                    disabled={deleteMutation.isPending}
                    className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-all disabled:opacity-50"
                    title={t("common.delete")}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                    Type:
                  </span>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      env.type === "prod"
                        ? "bg-red-500/20 text-red-400"
                        : env.type === "stage"
                          ? "bg-yellow-500/20 text-yellow-400"
                          : "bg-green-500/20 text-green-400"
                    }`}
                  >
                    {env.type === "prod"
                      ? "Production"
                      : env.type === "stage"
                        ? "Staging"
                        : "Development"}
                  </span>
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400">
                  Created: {new Date(env.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
            ))
          )}
        </div>
      )}

      <EnvironmentDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setEditingEnvironment(null);
        }}
        environment={editingEnvironment}
        orgId={orgId}
      />
    </div>
  );
}

