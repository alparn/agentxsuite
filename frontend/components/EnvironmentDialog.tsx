"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface EnvironmentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  environment?: any;
  orgId: string | null;
}

export function EnvironmentDialog({
  isOpen,
  onClose,
  environment,
  orgId,
}: EnvironmentDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    type: "dev" as "dev" | "stage" | "prod",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (environment) {
      setFormData({
        name: environment.name || "",
        type: environment.type || "dev",
      });
    } else {
      setFormData({
        name: "",
        type: "dev",
      });
    }
    setErrors({});
  }, [environment]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      const payload: any = {
        name: data.name,
        type: data.type,
        // organization_id is automatically set by backend from URL
      };

      if (environment) {
        return api.put(`/environments/${environment.id}/`, payload);
      } else {
        return api.post(`/orgs/${orgId}/environments/`, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["environments"] });
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

    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
            {environment ? t("common.edit") : t("environments.newEnvironment")}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
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
              placeholder="production"
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-400">{errors.name}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("environments.type")} *
            </label>
            <select
              value={formData.type}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  type: e.target.value as "dev" | "stage" | "prod",
                });
                if (errors.type) setErrors({ ...errors, type: "" });
              }}
              required
              className={`w-full px-4 py-2 bg-white dark:bg-slate-800 border rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.type
                  ? "border-red-500"
                  : "border-slate-300 dark:border-slate-700"
              }`}
            >
              <option value="dev">Development</option>
              <option value="stage">Staging</option>
              <option value="prod">Production</option>
            </select>
            {errors.type && (
              <p className="mt-1 text-sm text-red-400">{errors.type}</p>
            )}
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Environment type determines deployment and access policies
            </p>
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
                : environment
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

