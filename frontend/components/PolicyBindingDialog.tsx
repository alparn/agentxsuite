"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { policyBindingsApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { X } from "lucide-react";
import type { PolicyBinding } from "@/lib/types";

interface PolicyBindingDialogProps {
  isOpen: boolean;
  onClose: () => void;
  binding?: PolicyBinding | Partial<PolicyBinding> | null;
  policyId: string;
  orgId: string | null;
  onSave?: (bindingData: Partial<PolicyBinding>) => void;
}

export function PolicyBindingDialog({
  isOpen,
  onClose,
  binding,
  policyId,
  orgId,
  onSave,
}: PolicyBindingDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { currentEnvId } = useAppStore();
  const [formData, setFormData] = useState({
    scope_type: "org" as "org" | "env" | "agent" | "tool" | "role" | "user" | "resource_ns",
    scope_id: "",
    priority: 100,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Fetch environments
  const { data: environmentsData } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen && (formData.scope_type === "env"),
  });

  // Fetch agents
  const { data: agentsData } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/agents/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen && (formData.scope_type === "agent"),
  });

  // Fetch tools
  const { data: toolsData } = useQuery({
    queryKey: ["tools", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/tools/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen && (formData.scope_type === "tool"),
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];
  const agents = Array.isArray(agentsData) ? agentsData : [];
  const tools = Array.isArray(toolsData) ? toolsData : [];

  useEffect(() => {
    if (binding) {
      setFormData({
        scope_type: binding.scope_type || "org",
        scope_id: binding.scope_id || "",
        priority: binding.priority || 100,
      });
    } else {
      setFormData({
        scope_type: "org",
        scope_id: "",
        priority: 100,
      });
    }
    setErrors({});
  }, [binding, isOpen]);

  const mutation = useMutation({
    mutationFn: async (data: Partial<PolicyBinding>) => {
      const payload = {
        ...data,
        policy_id: policyId, // For local state
      };
      
      // If onSave callback is provided, use it instead of API call
      if (onSave) {
        onSave(payload);
        return { data: payload };
      }
      
      // Validate policyId before API call
      if (!policyId || policyId === "temp") {
        throw new Error("Cannot save binding: Policy must be created first");
      }
      
      // Otherwise, use API
      if (binding && (binding as PolicyBinding).id && typeof (binding as PolicyBinding).id === "number") {
        return policyBindingsApi.update((binding as PolicyBinding).id.toString(), payload);
      } else {
        return policyBindingsApi.create(payload);
      }
    },
    onSuccess: () => {
      if (!onSave) {
        // Invalidate all policy-related queries to refresh the UI
        queryClient.invalidateQueries({ queryKey: ["policy-bindings"] });
        queryClient.invalidateQueries({ queryKey: ["policy-bindings", policyId] });
        queryClient.invalidateQueries({ queryKey: ["policies"] });
        queryClient.invalidateQueries({ queryKey: ["policies", orgId] });
      }
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
    
    // Validate scope_id - use orgId if scope_type is org and orgId is available
    let finalScopeId = formData.scope_id;
    if (formData.scope_type === "org" && orgId) {
      finalScopeId = orgId;
    }
    
    if (!finalScopeId || finalScopeId.trim() === "") {
      setErrors({ scope_id: "Scope ID is required" });
      return;
    }
    
    mutation.mutate({
      ...formData,
      scope_id: finalScopeId,
    });
  };

  if (!isOpen) return null;

  const scopeTypeOptions = [
    { value: "org", label: "Organization" },
    { value: "env", label: "Environment" },
    { value: "agent", label: "Agent" },
    { value: "tool", label: "Tool" },
    { value: "role", label: "Role" },
    { value: "user", label: "User" },
    { value: "resource_ns", label: "Resource Namespace" },
  ];

  const renderScopeIdInput = () => {
    if (formData.scope_type === "org") {
      const scopeIdValue = orgId || formData.scope_id;
      return (
        <input
          type="text"
          required
          value={scopeIdValue}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          placeholder="Organization ID"
          disabled={!!orgId}
        />
      );
    } else if (formData.scope_type === "env") {
      return (
        <select
          required
          value={formData.scope_id}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="">{t("common.select")}...</option>
          {environments.map((env: any) => (
            <option key={env.id} value={env.id}>
              {env.name} ({env.type})
            </option>
          ))}
        </select>
      );
    } else if (formData.scope_type === "agent") {
      return (
        <select
          required
          value={formData.scope_id}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="">{t("common.select")}...</option>
          {agents.map((agent: any) => (
            <option key={agent.id} value={agent.id}>
              {agent.name} ({agent.slug})
            </option>
          ))}
        </select>
      );
    } else if (formData.scope_type === "tool") {
      return (
        <select
          required
          value={formData.scope_id}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="">{t("common.select")}...</option>
          {tools.map((tool: any) => (
            <option key={tool.id} value={tool.id}>
              {tool.name}
            </option>
          ))}
        </select>
      );
    } else if (formData.scope_type === "resource_ns") {
      return (
        <input
          type="text"
          required
          value={formData.scope_id}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          placeholder="minio://org/env/path/*"
        />
      );
    } else {
      return (
        <input
          type="text"
          required
          value={formData.scope_id}
          onChange={(e) => setFormData({ ...formData, scope_id: e.target.value })}
          className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          placeholder={`${formData.scope_type} ID`}
        />
      );
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-2xl shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900 z-10">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {binding ? t("common.edit") : "New Binding"}
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
              Scope Type *
            </label>
            <select
              required
              value={formData.scope_type}
              onChange={(e) => {
                setFormData({
                  ...formData,
                  scope_type: e.target.value as PolicyBinding["scope_type"],
                  scope_id: "", // Reset scope_id when type changes
                });
              }}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {scopeTypeOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.scope_type && (
              <p className="mt-1 text-sm text-red-500">{errors.scope_type}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Scope ID *
            </label>
            {renderScopeIdInput()}
            {formData.scope_type === "org" && orgId && (
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Using current organization: {orgId}
              </p>
            )}
            {errors.scope_id && (
              <p className="mt-1 text-sm text-red-500">{errors.scope_id}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Priority *
            </label>
            <input
              type="number"
              required
              min="0"
              max="1000"
              value={formData.priority}
              onChange={(e) =>
                setFormData({ ...formData, priority: parseInt(e.target.value) || 100 })
              }
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="100"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Lower priority = more specific (evaluated first)
            </p>
            {errors.priority && (
              <p className="mt-1 text-sm text-red-500">{errors.priority}</p>
            )}
          </div>

          {errors.general && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400">{errors.general}</p>
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
                : binding
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

