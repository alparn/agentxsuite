"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface ToolDialogProps {
  isOpen: boolean;
  onClose: () => void;
  tool?: any;
  orgId: string | null;
}

export function ToolDialog({
  isOpen,
  onClose,
  tool,
  orgId,
}: ToolDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    version: "1.0.0",
    enabled: true,
    environment_id: "",
    schema_json: "{}",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch environments for the organization
  const { data: environmentsData, isLoading: isLoadingEnvs, error: envError } = useQuery({
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
    enabled: !!orgId, // Allow pre-fetching even when dialog is closed
    staleTime: 30000, // Cache for 30 seconds
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  useEffect(() => {
    if (tool) {
      setFormData({
        name: tool.name || "",
        version: tool.version || "1.0.0",
        enabled: tool.enabled ?? true,
        environment_id: tool.environment_id || "",
        schema_json: JSON.stringify(tool.schema_json || {}, null, 2),
      });
    } else {
      setFormData({
        name: "",
        version: "1.0.0",
        enabled: true,
        environment_id: "",
        schema_json: "{}",
      });
    }
    setErrors({});
  }, [tool]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Parse schema_json
      let schemaJson: any;
      try {
        schemaJson = JSON.parse(data.schema_json);
      } catch (e) {
        throw new Error("Invalid JSON in schema_json field");
      }

      const payload: any = {
        name: data.name,
        version: data.version,
        environment_id: data.environment_id,
        schema_json: schemaJson,
        enabled: data.enabled,
      };

      if (tool) {
        return api.put(`/orgs/${orgId}/tools/${tool.id}/`, payload);
      } else {
        // organization_id is automatically set by backend from URL
        return api.post(`/orgs/${orgId}/tools/`, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools"] });
      setErrors({});
      onClose();
    },
    onError: (error: any) => {
      if (error.response?.data) {
        const backendErrors = error.response.data;
        const newErrors: Record<string, string> = {};

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
    if (!formData.version.trim()) {
      setErrors({ version: t("tools.version") + " is required" });
      return;
    }
    if (!formData.environment_id) {
      setErrors({ environment_id: t("agents.environment") + " is required" });
      return;
    }

    // Validate JSON
    try {
      JSON.parse(formData.schema_json);
    } catch (e) {
      setErrors({
        schema_json: "Invalid JSON format. Please check your schema.",
      });
      return;
    }

    mutation.mutate(formData);
  };

  const formatJSON = () => {
    try {
      const parsed = JSON.parse(formData.schema_json);
      setFormData({
        ...formData,
        schema_json: JSON.stringify(parsed, null, 2),
      });
      if (errors.schema_json) {
        setErrors({ ...errors, schema_json: "" });
      }
    } catch (e) {
      setErrors({
        schema_json: "Invalid JSON. Cannot format.",
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-3xl shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
            {tool ? t("common.edit") : t("tools.defineTool")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6 overflow-y-auto flex-1">
          {errors.general && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400">{errors.general}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
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
                placeholder="tool-name"
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-400">{errors.name}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                {t("tools.version")} *
              </label>
              <input
                type="text"
                value={formData.version}
                onChange={(e) => {
                  setFormData({ ...formData, version: e.target.value });
                  if (errors.version) setErrors({ ...errors, version: "" });
                }}
                required
                className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  errors.version
                    ? "border-red-500"
                    : "border-slate-300 dark:border-slate-700"
                }`}
                placeholder="1.0.0"
              />
              {errors.version && (
                <p className="mt-1 text-sm text-red-400">{errors.version}</p>
              )}
            </div>
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
              {isLoadingEnvs ? (
                <option value="" disabled>{t("common.loading")}...</option>
              ) : envError ? (
                <option value="" disabled>Error loading environments</option>
              ) : environments.length === 0 ? (
                <option value="" disabled>No environments available</option>
              ) : (
                environments.map((env: any) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.type})
                  </option>
                ))
              )}
            </select>
            {errors.environment_id && (
              <p className="mt-1 text-sm text-red-400">{errors.environment_id}</p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                Schema JSON *
              </label>
              <button
                type="button"
                onClick={formatJSON}
                className="text-xs text-purple-500 hover:text-purple-600 dark:hover:text-purple-400"
              >
                Format JSON
              </button>
            </div>
            <textarea
              value={formData.schema_json}
              onChange={(e) => {
                setFormData({ ...formData, schema_json: e.target.value });
                if (errors.schema_json)
                  setErrors({ ...errors, schema_json: "" });
              }}
              required
              rows={12}
              className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.schema_json
                  ? "border-red-500"
                  : "border-slate-300 dark:border-slate-700"
              }`}
              placeholder='{"type": "object", "properties": {...}}'
            />
            {errors.schema_json && (
              <p className="mt-1 text-sm text-red-400">{errors.schema_json}</p>
            )}
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              JSON Schema definition for the tool (e.g., OpenAPI schema)
            </p>
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
                : tool
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

