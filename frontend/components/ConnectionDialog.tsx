"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface ConnectionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  connection?: any;
  orgId: string | null;
  onSuccess?: () => void;
}

export function ConnectionDialog({
  isOpen,
  onClose,
  connection,
  orgId,
  onSuccess,
}: ConnectionDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    endpoint: "",
    auth_method: "none" as "none" | "bearer" | "basic",
    secret_value: "", // User enters the actual secret value
    secret_ref: "", // Used for updates or if user provides ref directly
    environment_id: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

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

  useEffect(() => {
    if (connection) {
      // Handle both environment_id (string) and environment (object)
      const environmentId = connection.environment_id || connection.environment?.id || "";
      setFormData({
        name: connection.name || "",
        endpoint: connection.endpoint || "",
        auth_method: connection.auth_method || "none",
        secret_value: "", // Never pre-fill secret value for security reasons
        secret_ref: "", // Never pre-fill secret_ref for security reasons
        environment_id: environmentId,
      });
    } else {
      setFormData({
        name: "",
        endpoint: "",
        auth_method: "none",
        secret_value: "",
        secret_ref: "",
        environment_id: "",
      });
    }
    setErrors({});
  }, [connection, isOpen]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      let secretRef = data.secret_ref;

      // If secret_value is provided, store it first and get secret_ref
      if (data.auth_method !== "none" && data.secret_value && data.secret_value.trim()) {
        if (!orgId || !data.environment_id) {
          throw new Error("Organization and environment are required to store secrets");
        }

        // Store secret and get reference
        const secretResponse = await api.post(
          `/orgs/${orgId}/connections/store-secret/`,
          {
            environment_id: data.environment_id,
            key: `connection_${data.name || "auth"}_token`,
            value: data.secret_value.trim(),
          }
        );
        secretRef = secretResponse.data.secret_ref;
      }

      // Prepare payload according to backend serializer
      const payload: any = {
        name: data.name,
        endpoint: data.endpoint,
        auth_method: data.auth_method,
        environment_id: data.environment_id,
      };

      // Include secret_ref if auth_method requires it
      if (data.auth_method !== "none") {
        if (!secretRef) {
          throw new Error("Secret value or reference is required for bearer or basic auth");
        }
        payload.secret_ref = secretRef;
      }

      // Only treat as update if connection has an id
      if (connection?.id) {
        // For updates, only send secret_ref if a new secret_value was provided
        // If neither secret_value nor secret_ref is provided, don't send secret_ref (keeps existing)
        const updatePayload: any = {
          name: payload.name,
          endpoint: payload.endpoint,
          auth_method: payload.auth_method,
          environment_id: payload.environment_id,
        };
        // Only include secret_ref if user provided a new secret value
        if (secretRef) {
          updatePayload.secret_ref = secretRef;
        }
        return api.put(`/orgs/${orgId}/connections/${connection.id}/`, updatePayload);
      } else {
        // organization_id is automatically set by backend from URL
        return api.post(`/orgs/${orgId}/connections/`, payload);
      }
    },
    onSuccess: () => {
      // Invalidate all connection queries (with and without orgId)
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      if (orgId) {
        queryClient.invalidateQueries({ queryKey: ["connections", orgId] });
      }
      setErrors({});
      onSuccess?.();
      onClose();
    },
    onError: (error: any) => {
      if (error.response?.data) {
        const backendErrors = error.response.data;
        const newErrors: Record<string, string> = {};
        
        // Handle field-specific errors
        Object.keys(backendErrors).forEach((key) => {
          if (Array.isArray(backendErrors[key])) {
            newErrors[key] = backendErrors[key].join(", ");
          } else {
            newErrors[key] = backendErrors[key];
          }
        });
        
        setErrors(newErrors);
      } else {
        setErrors({ general: error.message || t("common.error") });
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    // Client-side validation
    if (!formData.name.trim()) {
      setErrors({ name: t("common.name") + " is required" });
      return;
    }
    if (!formData.endpoint.trim()) {
      setErrors({ endpoint: t("connections.endpoint") + " is required" });
      return;
    }
    if (!formData.environment_id) {
      setErrors({ environment_id: t("agents.environment") + " is required" });
      return;
    }
    // For new connections, secret_value is required if auth_method is not "none"
    if (!connection && formData.auth_method !== "none" && !formData.secret_value.trim()) {
      setErrors({ secret_value: "Secret value is required for " + formData.auth_method + " auth" });
      return;
    }
    // For updates: secret_ref validation is handled by backend
    // User can leave it empty to keep existing secret_ref, or provide new one to update it
    // Backend will validate that secret_ref exists (either existing or new) when auth_method requires it

    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-md shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900 z-10">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {connection ? t("common.edit") : t("connections.newConnection")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          {errors.general && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400">{errors.general}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("common.name")} *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => {
                setFormData({ ...formData, name: e.target.value });
                if (errors.name) setErrors({ ...errors, name: "" });
              }}
              required
              className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.name
                  ? "border-red-500"
                  : "border-slate-300 dark:border-slate-700"
              }`}
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-400">{errors.name}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("connections.endpoint")} *
            </label>
            <input
              type="url"
              value={formData.endpoint}
              onChange={(e) => {
                setFormData({ ...formData, endpoint: e.target.value });
                if (errors.endpoint) setErrors({ ...errors, endpoint: "" });
              }}
              required
              className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.endpoint
                  ? "border-red-500"
                  : "border-slate-300 dark:border-slate-700"
              }`}
              placeholder="https://mcp-server.example.com"
            />
            {errors.endpoint && (
              <p className="mt-1 text-sm text-red-400">{errors.endpoint}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.environment")} *
            </label>
            <select
              value={formData.environment_id}
              onChange={(e) => {
                setFormData({ ...formData, environment_id: e.target.value });
                if (errors.environment_id)
                  setErrors({ ...errors, environment_id: "" });
              }}
              required
              className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.environment_id
                  ? "border-red-500"
                  : "border-slate-300 dark:border-slate-700"
              }`}
            >
              <option value="">{t("common.select")}...</option>
              {environments?.map((env: any) => (
                <option key={env.id} value={env.id}>
                  {env.name} ({env.type})
                </option>
              ))}
            </select>
            {errors.environment_id && (
              <p className="mt-1 text-sm text-red-400">{errors.environment_id}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("connections.authMethod")} *
            </label>
            <select
              value={formData.auth_method}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  auth_method: e.target.value as "none" | "bearer" | "basic",
                  secret_value: "", // Clear secret_value when changing auth method
                  secret_ref: "", // Clear secret_ref when changing auth method
                });
                if (errors.auth_method)
                  setErrors({ ...errors, auth_method: "" });
              }}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="none">None</option>
              <option value="bearer">Bearer Token</option>
              <option value="basic">Basic Auth</option>
            </select>
          </div>

          {(formData.auth_method === "bearer" ||
            formData.auth_method === "basic") && (
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                Secret Value {!connection && "*"}
              </label>
              <input
                type="password"
                value={formData.secret_value}
                onChange={(e) => {
                  setFormData({ ...formData, secret_value: e.target.value });
                  if (errors.secret_value)
                    setErrors({ ...errors, secret_value: "" });
                }}
                required={!connection}
                className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  errors.secret_value
                    ? "border-red-500"
                    : "border-slate-300 dark:border-slate-700"
                }`}
                placeholder={connection ? "Enter new secret value to update" : "Enter secret token or password"}
              />
              {errors.secret_value && (
                <p className="mt-1 text-sm text-red-400">{errors.secret_value}</p>
              )}
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {connection
                  ? "Leave empty to keep existing secret, or enter new value to update"
                  : "The secret will be securely stored and encrypted. Enter the actual token or password value."}
              </p>
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
                : connection
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

