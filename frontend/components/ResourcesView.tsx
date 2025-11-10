"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { resourcesApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { Resource } from "@/lib/types";
import { Plus, Edit, Trash2, Eye, Database, FileText, Globe, HardDrive, Server, CheckCircle2, XCircle } from "lucide-react";
import { ResourceDialog } from "./ResourceDialog";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error";
}

export function ResourcesView() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingResource, setEditingResource] = useState<Resource | null>(null);
  const [viewingResource, setViewingResource] = useState<Resource | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

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

  // Fetch resources
  const { data: resourcesData, isLoading, error: resourcesError } = useQuery({
    queryKey: ["resources", orgId, envId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
        const response = await resourcesApi.list(orgId);
        // Handle paginated response (DRF returns {results: [...], count, next, previous})
        // or direct array response
        let resources: Resource[] = [];
        if (Array.isArray(response.data)) {
          resources = response.data;
        } else if (response.data?.results && Array.isArray(response.data.results)) {
          resources = response.data.results;
        }
        
        // Filter by environment if selected
        if (envId) {
          const filtered = resources.filter((r: Resource) => {
            // Handle both string and object formats
            const rEnvId = typeof r.environment_id === "string" 
              ? r.environment_id 
              : r.environment?.id || "";
            // Compare UUIDs (both should be strings)
            const match = String(rEnvId).toLowerCase() === String(envId).toLowerCase();
            return match;
          });
          return filtered;
        }
        return resources;
      } catch (error: any) {
        console.error("Error fetching resources:", error);
        throw error;
      }
    },
    enabled: !!orgId,
  });

  const resources = Array.isArray(resourcesData) ? resourcesData : [];

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      if (!orgId) throw new Error("Organization ID is required");
      return resourcesApi.delete(orgId, id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
      addToast(t("resources.deleteSuccess"), "success");
    },
    onError: () => {
      addToast(t("resources.deleteError"), "error");
    },
  });

  const addToast = (message: string, type: "success" | "error") => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 5000);
  };

  const getResourceTypeIcon = (type: string) => {
    switch (type) {
      case "static":
        return FileText;
      case "http":
        return Globe;
      case "sql":
        return Database;
      case "s3":
        return HardDrive;
      case "file":
        return Server;
      default:
        return Database;
    }
  };

  const handleEdit = (resource: Resource) => {
    setEditingResource(resource);
    setIsDialogOpen(true);
  };

  const handleDelete = (resource: Resource) => {
    if (confirm(t("resources.confirmDelete", { name: resource.name }))) {
      deleteMutation.mutate(resource.id);
    }
  };

  const handleCloseDialog = () => {
    setIsDialogOpen(false);
    setEditingResource(null);
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
          <h1 className="text-2xl sm:text-3xl font-bold text-white">{t("resources.title")}</h1>
          <p className="text-slate-400 mt-1">{t("resources.subtitle")}</p>
        </div>
        <button
          onClick={() => {
            setEditingResource(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">{t("resources.newResource")}</span>
        </button>
      </div>

      {/* Environment Filter */}
      {environments.length > 0 && (
        <div className="flex items-center gap-4">
          <label className="text-slate-300 text-sm">{t("resources.environment")}:</label>
          <select
            value={envId || ""}
            onChange={(e) => {
              const newEnvId = e.target.value || null;
              setCurrentEnv(newEnvId);
            }}
            className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm"
          >
            <option value="">{t("resources.allEnvironments")}</option>
            {environments.map((env: any) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
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

      {/* Error Display */}
      {resourcesError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-red-400 text-sm">
            {t("common.error")}: {resourcesError instanceof Error ? resourcesError.message : String(resourcesError)}
          </p>
        </div>
      )}

      {/* Resources List */}
      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : resourcesError ? (
        <div className="text-center py-12 text-red-400">
          {t("common.error")}: {resourcesError instanceof Error ? resourcesError.message : String(resourcesError)}
        </div>
      ) : !resourcesData ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : resources.length === 0 ? (
        <div className="text-center py-12 text-slate-400">
          {envId 
            ? t("resources.noResources") + ` (${t("resources.environment")}: ${environments.find((e: any) => e.id === envId)?.name || envId})`
            : t("resources.noResources")
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
                  <th className="text-left p-4 text-slate-300">{t("resources.type")}</th>
                  <th className="text-left p-4 text-slate-300">{t("resources.environment")}</th>
                  <th className="text-left p-4 text-slate-300">{t("resources.mimeType")}</th>
                  <th className="text-left p-4 text-slate-300">{t("common.status")}</th>
                  <th className="text-right p-4 text-slate-300">{t("common.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((resource: Resource) => {
                  const TypeIcon = getResourceTypeIcon(resource.type);
                  return (
                    <tr key={resource.id} className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <TypeIcon className="w-4 h-4 text-purple-400" />
                          <span className="text-white">{resource.name}</span>
                        </div>
                      </td>
                      <td className="p-4 text-slate-300 capitalize">{resource.type}</td>
                      <td className="p-4 text-slate-300">{resource.environment?.name || "-"}</td>
                      <td className="p-4 text-slate-400 text-sm">{resource.mime_type}</td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            resource.enabled
                              ? "bg-green-500/20 text-green-400"
                              : "bg-red-500/20 text-red-400"
                          }`}
                        >
                          {resource.enabled ? t("common.enabled") : t("common.disabled")}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleEdit(resource)}
                            className="p-2 text-slate-400 hover:text-purple-400 rounded-lg hover:bg-slate-800"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(resource)}
                            className="p-2 text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-800"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-4">
            {resources.map((resource: Resource) => {
              const TypeIcon = getResourceTypeIcon(resource.type);
              return (
                <div
                  key={resource.id}
                  className="bg-slate-800 rounded-lg p-4 border border-slate-700"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <TypeIcon className="w-5 h-5 text-purple-400" />
                      <div>
                        <h3 className="text-white font-medium">{resource.name}</h3>
                        <p className="text-slate-400 text-sm capitalize">{resource.type}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEdit(resource)}
                        className="p-2 text-slate-400 hover:text-purple-400 rounded-lg hover:bg-slate-700"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(resource)}
                        className="p-2 text-slate-400 hover:text-red-400 rounded-lg hover:bg-slate-700"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">{t("resources.environment")}:</span>
                      <span className="text-slate-300">{resource.environment?.name || "-"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">{t("resources.mimeType")}:</span>
                      <span className="text-slate-300">{resource.mime_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">{t("common.status")}:</span>
                      <span
                        className={`${
                          resource.enabled ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {resource.enabled ? t("common.enabled") : t("common.disabled")}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Dialog */}
      {isDialogOpen && (
        <ResourceDialog
          resource={editingResource}
          onClose={handleCloseDialog}
          orgId={orgId || ""}
          environments={environments}
        />
      )}
    </div>
  );
}

