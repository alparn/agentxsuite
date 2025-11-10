"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resourcesApi } from "@/lib/api";
import { X } from "lucide-react";
import type { Resource } from "@/lib/types";

interface ResourceDialogProps {
  resource?: Resource | null;
  onClose: () => void;
  orgId: string;
  environments: any[];
}

export function ResourceDialog({
  resource,
  onClose,
  orgId,
  environments,
}: ResourceDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    environment_id: "",
    type: "static" as "static" | "http" | "sql" | "s3" | "file",
    config_json: "{}",
    mime_type: "application/json",
    schema_json: "",
    secret_ref: "",
    enabled: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (resource) {
      setFormData({
        name: resource.name || "",
        environment_id: resource.environment_id || resource.environment?.id || "",
        type: resource.type || "static",
        config_json: JSON.stringify(resource.config_json || {}, null, 2),
        mime_type: resource.mime_type || "application/json",
        schema_json: resource.schema_json ? JSON.stringify(resource.schema_json, null, 2) : "",
        secret_ref: resource.secret_ref || "",
        enabled: resource.enabled ?? true,
      });
    } else {
      setFormData({
        name: "",
        environment_id: "",
        type: "static",
        config_json: "{}",
        mime_type: "application/json",
        schema_json: "",
        secret_ref: "",
        enabled: true,
      });
    }
    setErrors({});
  }, [resource]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Parse JSON fields
      let configJson: any;
      let schemaJson: any = null;

      try {
        configJson = JSON.parse(data.config_json);
      } catch (e) {
        throw new Error("Invalid JSON in config_json field");
      }

      if (data.schema_json && data.schema_json.trim()) {
        try {
          schemaJson = JSON.parse(data.schema_json);
        } catch (e) {
          throw new Error("Invalid JSON in schema_json field");
        }
      }

      const payload: any = {
        name: data.name,
        environment_id: data.environment_id,
        type: data.type,
        config_json: configJson,
        mime_type: data.mime_type,
        enabled: data.enabled,
      };

      if (schemaJson !== null) {
        payload.schema_json = schemaJson;
      }

      if (data.secret_ref && data.secret_ref.trim()) {
        payload.secret_ref = data.secret_ref.trim();
      }

      if (resource?.id) {
        return resourcesApi.update(orgId, resource.id, payload);
      } else {
        return resourcesApi.create(orgId, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
      setErrors({});
      onClose();
    },
    onError: (error: any) => {
      if (error.response?.data) {
        const backendErrors = error.response.data;
        const newErrors: Record<string, string> = {};

        Object.keys(backendErrors).forEach((key) => {
          if (Array.isArray(backendErrors[key])) {
            newErrors[key] = backendErrors[key][0];
          } else if (typeof backendErrors[key] === "string") {
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
    mutation.mutate(formData);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-xl sm:text-2xl font-bold text-white">
            {resource ? t("common.edit") : t("resources.newResource")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {errors.general && (
            <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
              {errors.general}
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("common.name")} *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
              maxLength={120}
            />
            {errors.name && <p className="text-red-400 text-xs mt-1">{errors.name}</p>}
          </div>

          {/* Environment */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.environment")} *
            </label>
            <select
              value={formData.environment_id}
              onChange={(e) => setFormData({ ...formData, environment_id: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            >
              <option value="">{t("common.select")}</option>
              {environments.map((env) => (
                <option key={env.id} value={env.id}>
                  {env.name}
                </option>
              ))}
            </select>
            {errors.environment_id && (
              <p className="text-red-400 text-xs mt-1">{errors.environment_id}</p>
            )}
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.type")} *
            </label>
            <select
              value={formData.type}
              onChange={(e) =>
                setFormData({ ...formData, type: e.target.value as Resource["type"] })
              }
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            >
              <option value="static">{t("resources.typeStatic")}</option>
              <option value="http">{t("resources.typeHttp")}</option>
              <option value="sql">{t("resources.typeSql")}</option>
              <option value="s3">{t("resources.typeS3")}</option>
              <option value="file">{t("resources.typeFile")}</option>
            </select>
            {errors.type && <p className="text-red-400 text-xs mt-1">{errors.type}</p>}
          </div>

          {/* Config JSON */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.configJson")} *
            </label>
            <textarea
              value={formData.config_json}
              onChange={(e) => setFormData({ ...formData, config_json: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={6}
              required
            />
            {errors.config_json && (
              <p className="text-red-400 text-xs mt-1">{errors.config_json}</p>
            )}
          </div>

          {/* MIME Type */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.mimeType")} *
            </label>
            <input
              type="text"
              value={formData.mime_type}
              onChange={(e) => setFormData({ ...formData, mime_type: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
              maxLength={80}
            />
            {errors.mime_type && (
              <p className="text-red-400 text-xs mt-1">{errors.mime_type}</p>
            )}
          </div>

          {/* Schema JSON */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.schemaJson")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.schema_json}
              onChange={(e) => setFormData({ ...formData, schema_json: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={4}
              placeholder="{}"
            />
            {errors.schema_json && (
              <p className="text-red-400 text-xs mt-1">{errors.schema_json}</p>
            )}
          </div>

          {/* Secret Ref */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("resources.secretRef")} ({t("common.optional")})
            </label>
            <input
              type="text"
              value={formData.secret_ref}
              onChange={(e) => setFormData({ ...formData, secret_ref: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="secret-ref-name"
              maxLength={255}
            />
            {errors.secret_ref && (
              <p className="text-red-400 text-xs mt-1">{errors.secret_ref}</p>
            )}
          </div>

          {/* Enabled */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="enabled"
              checked={formData.enabled}
              onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
              className="w-4 h-4 text-purple-600 bg-slate-800 border-slate-700 rounded focus:ring-purple-500"
            />
            <label htmlFor="enabled" className="text-sm text-slate-300">
              {t("common.enabled")}
            </label>
          </div>

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {mutation.isPending ? t("common.loading") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

