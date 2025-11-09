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
}

export function ConnectionDialog({
  isOpen,
  onClose,
  connection,
  orgId,
}: ConnectionDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    endpoint: "",
    auth_method: "none" as "none" | "bearer" | "basic",
    secret_ref: "",
    environment_id: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch environments for the organization
  const { data: environments } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      return response.data;
    },
    enabled: !!orgId && isOpen,
  });

  useEffect(() => {
    if (connection) {
      setFormData({
        name: connection.name || "",
        endpoint: connection.endpoint || "",
        auth_method: connection.auth_method || "none",
        secret_ref: "",
        environment_id: connection.environment_id || "",
      });
    } else {
      setFormData({
        name: "",
        endpoint: "",
        auth_method: "none",
        secret_ref: "",
        environment_id: "",
      });
    }
  }, [connection]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Prepare payload according to backend serializer
      const payload: any = {
        name: data.name,
        endpoint: data.endpoint,
        auth_method: data.auth_method,
        environment_id: data.environment_id,
      };

      // Only include secret_ref if auth_method is not "none"
      if (data.auth_method !== "none" && data.secret_ref) {
        payload.secret_ref = data.secret_ref;
      } else if (data.auth_method !== "none" && !data.secret_ref) {
        // This will be validated by backend, but we can show error here too
        throw new Error("Secret reference is required for bearer or basic auth");
      }

      if (connection) {
        return api.put(`/orgs/${orgId}/connections/${connection.id}/`, payload);
      } else {
        return api.post(`/orgs/${orgId}/connections/`, {
          ...payload,
          organization_id: orgId,
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      setErrors({});
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
    if (formData.auth_method !== "none" && !formData.secret_ref.trim()) {
      setErrors({ secret_ref: "Secret reference is required for " + formData.auth_method + " auth" });
      return;
    }

    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
            {connection ? t("common.edit") : t("connections.newConnection")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
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
                Secret Reference *
              </label>
              <input
                type="text"
                value={formData.secret_ref}
                onChange={(e) => {
                  setFormData({ ...formData, secret_ref: e.target.value });
                  if (errors.secret_ref)
                    setErrors({ ...errors, secret_ref: "" });
                }}
                required
                className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  errors.secret_ref
                    ? "border-red-500"
                    : "border-slate-300 dark:border-slate-700"
                }`}
                placeholder="secret:key"
              />
              {errors.secret_ref && (
                <p className="mt-1 text-sm text-red-400">{errors.secret_ref}</p>
              )}
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Reference to secret stored in secret store (e.g., "secret:key")
              </p>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
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

