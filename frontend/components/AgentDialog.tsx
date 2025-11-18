"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { X } from "lucide-react";

interface AgentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  agent?: any;
  orgId: string | null;
  onSuccess?: (agent: any) => void;
  preselectedEnvironmentId?: string;
}

export function AgentDialog({
  isOpen,
  onClose,
  agent,
  orgId: propOrgId,
  onSuccess,
  preselectedEnvironmentId,
}: AgentDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { currentOrgId: storeOrgId } = useAppStore();
  // Use prop orgId if provided, otherwise fall back to store
  const orgId = propOrgId || storeOrgId;
  const [formData, setFormData] = useState({
    name: "",
    version: "1.0.0",
    enabled: true,
    environment_id: "",
    connection_id: "",
    mode: "runner" as "runner" | "caller",
    inbound_auth_method: "bearer" as "bearer" | "mtls" | "none",
    inbound_secret_ref: "",
    is_axcore: false,
    default_budget_cents: 0,
    default_max_depth: 1,
    default_ttl_seconds: 600,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showTokenDialog, setShowTokenDialog] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);

  // Fetch environments for the organization
  const { data: environmentsData, isLoading: environmentsLoading } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
      const response = await api.get(`/orgs/${orgId}/environments/`);
      // Handle paginated response
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
      } catch (error) {
        console.error("Failed to fetch environments:", error);
        return [];
      }
    },
    enabled: !!orgId && isOpen,
    staleTime: 30000, // Cache for 30 seconds
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Fetch connections for the organization
  const { data: connectionsData, isLoading: connectionsLoading } = useQuery({
    queryKey: ["connections", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
      const response = await api.get(`/orgs/${orgId}/connections/`);
      // Handle paginated response
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
      } catch (error) {
        console.error("Failed to fetch connections:", error);
        return [];
      }
    },
    enabled: !!orgId && isOpen,
    staleTime: 30000, // Cache for 30 seconds
  });

  const connections = Array.isArray(connectionsData) ? connectionsData : [];

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
        is_axcore: agent.is_axcore || agent.tags?.includes("axcore") || false,
        default_budget_cents: agent.default_budget_cents || 0,
        default_max_depth: agent.default_max_depth || 1,
        default_ttl_seconds: agent.default_ttl_seconds || 600,
      });
    } else {
      setFormData({
        name: "",
        version: "1.0.0",
        enabled: true,
        environment_id: preselectedEnvironmentId || "",
        connection_id: "",
        mode: "runner",
        inbound_auth_method: "bearer",
        inbound_secret_ref: "",
        is_axcore: false,
        default_budget_cents: 0,
        default_max_depth: 1,
        default_ttl_seconds: 600,
      });
    }
    setErrors({});
  }, [agent, preselectedEnvironmentId]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      if (agent) {
        return api.put(`/orgs/${orgId}/agents/${agent.id}/`, data);
      } else {
        // Wenn AxCore: Spezieller Endpoint für vollständige Erstellung
        if (data.is_axcore) {
          return api.post(`/orgs/${orgId}/agents/create-axcore/`, data);
        }
        // organization_id is automatically set by backend from URL
        return api.post(`/orgs/${orgId}/agents/`, data);
      }
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      
      // Wenn AxCore erstellt wurde und Token zurückkommt
      if (response.data?.token) {
        setNewToken(response.data.token);
        setShowTokenDialog(true);
      } else {
        // Call onSuccess callback if provided (for canvas integration)
        if (onSuccess && response.data) {
          onSuccess(response.data);
        }
      onClose();
      }
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
      default_budget_cents: formData.default_budget_cents,
      default_max_depth: formData.default_max_depth,
      default_ttl_seconds: formData.default_ttl_seconds,
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
    
    // AxCore: Tags hinzufügen (nur bei Erstellung)
    if (!agent && formData.is_axcore) {
      submitData.is_axcore = true; // Flag für Backend
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
              disabled={environmentsLoading}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">{environmentsLoading ? t("common.loading") : `${t("common.select")}...`}</option>
              {environments.map((env: any) => (
                <option key={env.id} value={env.id}>
                  {env.name} ({env.type})
                </option>
              ))}
            </select>
            {!environmentsLoading && environments.length === 0 && orgId && (
              <p className="mt-1 text-xs text-red-500 dark:text-red-400">
                {t("agents.noEnvironments") || "No environments found. Please create an environment first."}
              </p>
            )}
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
              disabled={connectionsLoading}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">{connectionsLoading ? t("common.loading") : `${t("common.select")}...`}</option>
              {connections.map((conn: any) => (
                <option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.endpoint})
                </option>
              ))}
            </select>
            {!connectionsLoading && connections.length === 0 && formData.mode === "runner" && orgId && (
              <p className="mt-1 text-xs text-red-500 dark:text-red-400">
                {t("agents.noConnections") || "No connections found. Please create a connection first."}
              </p>
            )}
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

          {/* Delegation Settings Section */}
          <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">
              Delegation Settings
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Default Budget (Cents) *
                </label>
                <input
                  type="number"
                  required
                  min="0"
                  step="1"
                  value={formData.default_budget_cents}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      default_budget_cents: parseInt(e.target.value) || 0,
                    })
                  }
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="0 (unlimited)"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Budget in cents for delegation (0 = unlimited). Example: 1000 = $10.00
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Default Max Depth *
                </label>
                <input
                  type="number"
                  required
                  min="1"
                  max="10"
                  step="1"
                  value={formData.default_max_depth}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      default_max_depth: parseInt(e.target.value) || 1,
                    })
                  }
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="1"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Maximum delegation depth (1-10)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Default TTL (Seconds) *
                </label>
                <input
                  type="number"
                  required
                  min="1"
                  step="1"
                  value={formData.default_ttl_seconds}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      default_ttl_seconds: parseInt(e.target.value) || 600,
                    })
                  }
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="600"
                />
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Time-to-live in seconds for delegation (default: 600 = 10 minutes)
                </p>
              </div>
            </div>
          </div>

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

          {!agent && (
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_axcore"
                checked={formData.is_axcore ?? false}
                onChange={(e) =>
                  setFormData({ ...formData, is_axcore: e.target.checked })
                }
                className="w-4 h-4 text-purple-600 bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 rounded focus:ring-purple-500"
              />
              <label
                htmlFor="is_axcore"
                className="text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                AxCore Agent (automatische System-Tools-Konfiguration)
              </label>
            </div>
          )}

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
      
      {showTokenDialog && newToken && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-2xl w-full">
            <h3 className="text-xl font-bold text-white mb-4">AxCore Agent erstellt</h3>
            <p className="text-slate-300 mb-4">
              Der Agent wurde erfolgreich erstellt. Hier ist der Initial Token:
            </p>
            <div className="bg-slate-800 p-4 rounded mb-4">
              <code className="text-sm text-green-400 break-all">{newToken}</code>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(newToken);
                  alert("Token kopiert!");
                }}
                className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600"
              >
                Token kopieren
              </button>
              <button
                onClick={() => {
                  setShowTokenDialog(false);
                  setNewToken(null);
                  onClose();
                }}
                className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600"
              >
                Schließen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

