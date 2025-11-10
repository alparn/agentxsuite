"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface AgentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  agent?: any;
  orgId: string | null;
}

export function AgentDialog({
  isOpen,
  onClose,
  agent,
  orgId,
}: AgentDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    version: "1.0.0",
    enabled: true,
    environment_id: "",
    connection_id: "",
    mode: "runner" as "runner" | "caller",
    inbound_auth_method: "bearer" as "bearer" | "mtls" | "none",
    inbound_secret_ref: "",
  });

  // Fetch environments for the organization
  const { data: environments } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      // Handle paginated response
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  // Fetch connections for the organization
  const { data: connections } = useQuery({
    queryKey: ["connections", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/connections/`);
      // Handle paginated response
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  useEffect(() => {
    if (agent) {
      setFormData({
        name: agent.name || "",
        version: agent.version || "1.0.0",
        enabled: agent.enabled ?? true,
        environment_id: agent.environment?.id || agent.environment_id || "",
        connection_id: agent.connection?.id || agent.connection_id || "",
        mode: agent.mode || "runner",
        inbound_auth_method: agent.inbound_auth_method || "bearer",
        inbound_secret_ref: agent.inbound_secret_ref || "",
      });
    } else {
      setFormData({
        name: "",
        version: "1.0.0",
        enabled: true,
        environment_id: "",
        connection_id: "",
        mode: "runner",
        inbound_auth_method: "bearer",
        inbound_secret_ref: "",
      });
    }
  }, [agent]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      if (agent) {
        return api.put(`/orgs/${orgId}/agents/${agent.id}/`, data);
      } else {
        // organization_id is automatically set by backend from URL
        return api.post(`/orgs/${orgId}/agents/`, data);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Prepare data for submission
    const submitData: any = {
      name: formData.name,
      version: formData.version,
      enabled: formData.enabled,
      environment_id: formData.environment_id,
      mode: formData.mode,
    };
    
    // Connection is required for RUNNER, optional for CALLER
    if (formData.connection_id) {
      submitData.connection_id = formData.connection_id;
    } else if (formData.mode === "runner") {
      // Required for runner, set to null if empty
      submitData.connection_id = null;
    }
    // For CALLER mode, omit connection_id if empty (optional)
    
    // Inbound auth fields for CALLER mode
    if (formData.mode === "caller") {
      submitData.inbound_auth_method = formData.inbound_auth_method;
      if (formData.inbound_auth_method !== "none") {
        submitData.inbound_secret_ref = formData.inbound_secret_ref || null;
      }
    }
    
    mutation.mutate(submitData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-2xl shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900 z-10">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {agent ? t("common.edit") : t("agents.newAgent")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4 sm:space-y-6">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("common.name")} *
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder={t("common.name")}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.version")} *
            </label>
            <input
              type="text"
              required
              value={formData.version}
              onChange={(e) =>
                setFormData({ ...formData, version: e.target.value })
              }
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="1.0.0"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.environment")} *
            </label>
            <select
              required
              value={formData.environment_id}
              onChange={(e) =>
                setFormData({ ...formData, environment_id: e.target.value })
              }
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">{t("common.select")}...</option>
              {environments?.map((env: any) => (
                <option key={env.id} value={env.id}>
                  {env.name} ({env.type})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.mode")} *
            </label>
            <select
              required
              value={formData.mode}
              onChange={(e) => {
                const newMode = e.target.value as "runner" | "caller";
                setFormData({
                  ...formData,
                  mode: newMode,
                  // Don't reset connection_id - it's optional for both modes now
                  // Reset inbound fields for RUNNER mode
                  inbound_auth_method: newMode === "runner" ? "bearer" : formData.inbound_auth_method,
                  inbound_secret_ref: newMode === "runner" ? "" : formData.inbound_secret_ref,
                });
              }}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="runner">{t("agents.modeRunner")}</option>
              <option value="caller">{t("agents.modeCaller")}</option>
            </select>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {formData.mode === "runner"
                ? t("agents.modeRunnerDescription")
                : t("agents.modeCallerDescription")}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.connection")}
              {formData.mode === "runner" && " *"}
            </label>
            <select
              required={formData.mode === "runner"}
              value={formData.connection_id}
              onChange={(e) =>
                setFormData({ ...formData, connection_id: e.target.value })
              }
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">{t("common.select")}...</option>
              {connections?.map((conn: any) => (
                <option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.endpoint})
                </option>
              ))}
            </select>
            {formData.mode === "caller" && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {t("agents.connectionOptional")}
              </p>
            )}
          </div>

          {formData.mode === "caller" && (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  {t("agents.inboundAuthMethod")} *
                </label>
                <select
                  required
                  value={formData.inbound_auth_method}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      inbound_auth_method: e.target.value as "bearer" | "mtls" | "none",
                      // Reset secret_ref if auth_method is "none"
                      inbound_secret_ref:
                        e.target.value === "none" ? "" : formData.inbound_secret_ref,
                    })
                  }
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="bearer">{t("agents.authBearer")}</option>
                  <option value="mtls">{t("agents.authMtls")}</option>
                  <option value="none">{t("agents.authNone")}</option>
                </select>
              </div>

              {formData.inbound_auth_method !== "none" && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    {t("agents.inboundSecretRef")} *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.inbound_secret_ref}
                    onChange={(e) =>
                      setFormData({ ...formData, inbound_secret_ref: e.target.value })
                    }
                    className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder={t("agents.inboundSecretRefPlaceholder")}
                  />
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {t("agents.inboundSecretRefHint")}
                  </p>
                </div>
              )}
            </>
          )}

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled"
              checked={formData.enabled}
              onChange={(e) =>
                setFormData({ ...formData, enabled: e.target.checked })
              }
              className="w-4 h-4 text-purple-600 bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 rounded focus:ring-purple-500"
            />
            <label
              htmlFor="enabled"
              className="text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              {t("agents.enabled")}
            </label>
          </div>

          {mutation.error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400 font-semibold mb-1">Error:</p>
              {mutation.error instanceof Error ? (
                <p className="text-sm text-red-300">{mutation.error.message}</p>
              ) : (
                <div className="text-sm text-red-300">
                  {typeof mutation.error === "object" && mutation.error !== null && "response" in mutation.error ? (
                    <div>
                      <p>Status: {(mutation.error as any).response?.status}</p>
                      {(mutation.error as any).response?.data && (
                        <pre className="mt-2 text-xs overflow-x-auto">
                          {JSON.stringify((mutation.error as any).response.data, null, 2)}
                        </pre>
                      )}
                    </div>
                  ) : (
                    <p>{String(mutation.error)}</p>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-sm sm:text-base"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm sm:text-base"
            >
              {mutation.isPending
                ? t("common.loading")
                : agent
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

