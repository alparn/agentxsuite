"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
    auth_method: "none",
    secret_ref: "",
    environment_id: "",
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
      if (connection) {
        return api.put(`/orgs/${orgId}/connections/${connection.id}/`, data);
      } else {
        return api.post(`/orgs/${orgId}/connections/`, {
          ...data,
          organization_id: orgId,
        });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["connections"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg w-full max-w-md p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">
            {connection ? t("common.edit") : t("connections.newConnection")}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {t("common.name")}
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              required
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {t("connections.endpoint")}
            </label>
            <input
              type="url"
              value={formData.endpoint}
              onChange={(e) =>
                setFormData({ ...formData, endpoint: e.target.value })
              }
              required
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="https://mcp-server.example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {t("connections.authMethod")}
            </label>
            <select
              value={formData.auth_method}
              onChange={(e) =>
                setFormData({ ...formData, auth_method: e.target.value })
              }
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="none">None</option>
              <option value="bearer">Bearer Token</option>
              <option value="basic">Basic Auth</option>
            </select>
          </div>

          {(formData.auth_method === "bearer" ||
            formData.auth_method === "basic") && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Secret Reference
              </label>
              <input
                type="text"
                value={formData.secret_ref}
                onChange={(e) =>
                  setFormData({ ...formData, secret_ref: e.target.value })
                }
                required
                className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="secret:key"
              />
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50"
            >
              {mutation.isPending ? t("common.loading") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

