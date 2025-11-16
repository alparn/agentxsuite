"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { policiesApi, policyRulesApi, policyBindingsApi, policyEvaluateApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { X, Edit, Trash2, Plus, Play, CheckCircle, XCircle } from "lucide-react";
import { PolicyRuleDialog } from "./PolicyRuleDialog";
import { PolicyBindingDialog } from "./PolicyBindingDialog";
import type { Policy, PolicyRule, PolicyBinding, PolicyEvaluateRequest, PolicyEvaluateResponse } from "@/lib/types";

interface PolicyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  policy?: Policy | null;
  orgId: string | null;
  onSuccess?: (policy: any) => void;
  preselectedEnvironmentId?: string;
}

export function PolicyDialog({
  isOpen,
  onClose,
  policy,
  orgId,
  onSuccess,
  preselectedEnvironmentId,
}: PolicyDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { currentEnvId } = useAppStore();
  const [activeTab, setActiveTab] = useState<"overview" | "rules" | "bindings" | "test">("overview");
  const [formData, setFormData] = useState({
    name: "",
    environment_id: "",
    is_active: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [editingRule, setEditingRule] = useState<PolicyRule | null>(null);
  const [isRuleDialogOpen, setIsRuleDialogOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<PolicyBinding | null>(null);
  const [isBindingDialogOpen, setIsBindingDialogOpen] = useState(false);
  const [evaluateData, setEvaluateData] = useState<PolicyEvaluateRequest>({
    action: "tool.invoke",
    target: "",
    explain: false,
  });
  const [evaluateResult, setEvaluateResult] = useState<PolicyEvaluateResponse | null>(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  // Local state for rules and bindings during creation
  const [localRules, setLocalRules] = useState<Partial<PolicyRule>[]>([]);
  const [localBindings, setLocalBindings] = useState<Partial<PolicyBinding>[]>([]);

  // Fetch full policy data
  const { data: policyData } = useQuery({
    queryKey: ["policy", orgId, policy?.id],
    queryFn: async () => {
      if (!orgId || !policy?.id) return null;
      const response = await policiesApi.get(orgId, policy.id);
      return response.data;
    },
    enabled: !!orgId && !!policy?.id && isOpen,
  });

  // Fetch rules for this policy
  const { data: rulesData } = useQuery({
    queryKey: ["policy-rules", policy?.id],
    queryFn: async () => {
      if (!policy?.id) return [];
      const response = await policyRulesApi.list({ policy_id: policy.id });
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!policy?.id && isOpen,
  });

  // Fetch bindings for this policy
  const { data: bindingsData } = useQuery({
    queryKey: ["policy-bindings", policy?.id],
    queryFn: async () => {
      if (!policy?.id) return [];
      try {
        // Use policy_id filter if available, otherwise fetch all and filter
        const response = await policyBindingsApi.list({ policy_id: policy.id });
        if (Array.isArray(response.data)) {
          return response.data;
        }
        return response.data?.results || [];
      } catch (error) {
        console.error("Error fetching bindings:", error);
        return [];
      }
    },
    enabled: !!policy?.id && isOpen,
  });

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
    enabled: !!orgId && isOpen,
  });

  // Fetch agents and tools for evaluate tab
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
    enabled: !!orgId && isOpen && activeTab === "test",
  });

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
    enabled: !!orgId && isOpen && activeTab === "test",
  });

  const currentPolicy = policyData || policy;
  const rules = Array.isArray(rulesData) ? rulesData : [];
  const bindings = Array.isArray(bindingsData) ? bindingsData : [];
  const environments = Array.isArray(environmentsData) ? environmentsData : [];
  const agents = Array.isArray(agentsData) ? agentsData : [];
  const tools = Array.isArray(toolsData) ? toolsData : [];

  useEffect(() => {
    if (currentPolicy) {
      setFormData({
        name: currentPolicy.name || "",
        environment_id: currentPolicy.environment_id || "",
        is_active: currentPolicy.is_active ?? currentPolicy.enabled ?? true,
      });
    } else {
      setFormData({
        name: "",
        environment_id: preselectedEnvironmentId || "",
        is_active: true,
      });
    }
    setErrors({});
    setEvaluateResult(null);
  }, [currentPolicy, isOpen, preselectedEnvironmentId]);

  const createMutation = useMutation({
    mutationFn: async (data: Partial<Policy>) => {
      if (!orgId) throw new Error("Organization ID is required");
      const response = await policiesApi.create(orgId, data);
      const createdPolicy = response.data;
      
      // Create all rules for the new policy
      if (localRules.length > 0) {
        await Promise.all(
          localRules.map((rule) =>
            policyRulesApi.create({
              ...rule,
              policy_id: createdPolicy.id, // Backend expects 'policy_id' per OpenAPI/DRF convention
            })
          )
        );
      }
      
      // Create all bindings for the new policy
      if (localBindings.length > 0) {
        await Promise.all(
          localBindings.map((binding) =>
            policyBindingsApi.create({
              ...binding,
              policy_id: createdPolicy.id,
            })
          )
        );
      }
      
      return response;
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      queryClient.invalidateQueries({ queryKey: ["policy-rules"] });
      queryClient.invalidateQueries({ queryKey: ["policy-bindings"] });
      setErrors({});
      // Reset local state
      setLocalRules([]);
      setLocalBindings([]);
      // Reset form data
      setFormData({
        name: "",
        environment_id: "",
        is_active: true,
      });
      // Call onSuccess callback if provided
      if (onSuccess) {
        onSuccess(response.data);
      }
      // Close dialog and let parent refresh
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

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<Policy>) => {
      if (!orgId || !currentPolicy?.id) return;
      return policiesApi.update(orgId, currentPolicy.id, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      queryClient.invalidateQueries({ queryKey: ["policy", orgId, currentPolicy?.id] });
      setErrors({});
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

  const deleteRuleMutation = useMutation({
    mutationFn: async (ruleId: number) => {
      return policyRulesApi.delete(ruleId.toString());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policy-rules"] });
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const deleteBindingMutation = useMutation({
    mutationFn: async (bindingId: number) => {
      return policyBindingsApi.delete(bindingId.toString());
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policy-bindings"] });
      queryClient.invalidateQueries({ queryKey: ["policies"] });
    },
  });

  const deletePolicyMutation = useMutation({
    mutationFn: async () => {
      if (!orgId || !currentPolicy?.id) throw new Error("Policy ID is required");
      return policiesApi.delete(orgId, currentPolicy.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      queryClient.invalidateQueries({ queryKey: ["policy-rules"] });
      queryClient.invalidateQueries({ queryKey: ["policy-bindings"] });
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

  const handleEvaluate = async () => {
    if (!orgId || !currentPolicy?.id) return;
    setIsEvaluating(true);
    setEvaluateResult(null);
    try {
      const requestData: PolicyEvaluateRequest = {
        ...evaluateData,
        organization_id: orgId,
        environment_id: evaluateData.environment_id || currentPolicy.environment_id || undefined,
      };
      const response = await policyEvaluateApi.evaluate(requestData, evaluateData.explain);
      setEvaluateResult(response.data);
    } catch (error: any) {
      setErrors({ evaluate: error.response?.data?.detail || error.message || "Evaluation failed" });
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleUpdateField = (field: string, value: any) => {
    updateMutation.mutate({ [field]: value });
  };

  if (!isOpen) return null;

  const sortedBindings = [...bindings].sort((a, b) => a.priority - b.priority);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-4xl shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {currentPolicy ? currentPolicy.name : t("policies.newPolicy")}
          </h2>
          <div className="flex items-center gap-2">
            {currentPolicy && (
              <button
                onClick={() => {
                  if (confirm(`Are you sure you want to delete the policy "${currentPolicy.name}"? This action cannot be undone.`)) {
                    deletePolicyMutation.mutate();
                  }
                }}
                disabled={deletePolicyMutation.isPending}
                className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                title={t("common.delete")}
              >
                <Trash2 className="w-5 h-5" />
              </button>
            )}
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-slate-200 dark:border-slate-800">
          <div className="flex gap-2 px-4 sm:px-6">
            {(["overview", "rules", "bindings", "test"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "border-b-2 border-purple-500 text-purple-500"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  {t("common.name")} *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => {
                    setFormData({ ...formData, name: e.target.value });
                    if (currentPolicy) {
                      handleUpdateField("name", e.target.value);
                    }
                  }}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                {errors.name && <p className="mt-1 text-sm text-red-500">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Status
                </label>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      const newValue = !formData.is_active;
                      setFormData({ ...formData, is_active: newValue });
                      if (currentPolicy) {
                        handleUpdateField("is_active", newValue);
                      }
                    }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                      formData.is_active
                        ? "bg-green-500/20 text-green-400"
                        : "bg-red-500/20 text-red-400"
                    }`}
                  >
                    {formData.is_active ? (
                      <>
                        <CheckCircle className="w-4 h-4" />
                        Active
                      </>
                    ) : (
                      <>
                        <XCircle className="w-4 h-4" />
                        Inactive
                      </>
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  {t("agents.environment")} ({t("common.optional")})
                </label>
                <select
                  value={formData.environment_id}
                  onChange={(e) => {
                    setFormData({ ...formData, environment_id: e.target.value });
                    if (currentPolicy) {
                      handleUpdateField("environment_id", e.target.value || null);
                    }
                  }}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">{t("common.select")}...</option>
                  {environments.map((env: any) => (
                    <option key={env.id} value={env.id}>
                      {env.name} ({env.type})
                    </option>
                  ))}
                </select>
              </div>

              {currentPolicy && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Version
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {currentPolicy.version}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Created
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {new Date(currentPolicy.created_at).toLocaleString()}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Updated
                    </label>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      {new Date(currentPolicy.updated_at).toLocaleString()}
                    </p>
                  </div>
                </>
              )}

              {!currentPolicy && (
                <>
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
                      type="button"
                      onClick={() => {
                        if (!formData.name.trim()) {
                          setErrors({ name: "Name is required" });
                          return;
                        }
                        createMutation.mutate({
                          name: formData.name,
                          environment_id: formData.environment_id || null,
                          is_active: formData.is_active,
                        });
                      }}
                      disabled={createMutation.isPending || !formData.name.trim()}
                      className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm sm:text-base"
                    >
                      {createMutation.isPending
                        ? t("common.loading")
                        : t("common.create")}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === "rules" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Rules</h3>
                <button
                  type="button"
                  onClick={() => {
                    setEditingRule(null);
                    setIsRuleDialogOpen(true);
                  }}
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
                >
                  <Plus className="w-4 h-4" />
                  Add Rule
                </button>
              </div>

              {(() => {
                const displayRules = currentPolicy ? rules : localRules;
                return displayRules.length === 0 ? (
                  <p className="text-slate-400 text-center py-8">No rules defined</p>
                ) : (
                  <div className="space-y-2">
                    {displayRules.map((rule: PolicyRule | Partial<PolicyRule>, index: number) => {
                      const ruleId = (rule as PolicyRule).id || `local-${index}`;
                      const isLocal = !currentPolicy;
                      return (
                        <div
                          key={ruleId}
                          className="p-4 bg-slate-800 rounded-lg border border-slate-700 flex items-start justify-between"
                        >
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${
                                rule.effect === "allow"
                                  ? "bg-green-500/20 text-green-400"
                                  : "bg-red-500/20 text-red-400"
                              }`}>
                                {rule.effect?.toUpperCase()}
                              </span>
                              <span className="text-sm font-medium text-slate-300">{rule.action}</span>
                              {isLocal && (
                                <span className="text-xs text-slate-500">(pending)</span>
                              )}
                            </div>
                            <p className="text-sm text-slate-400 mb-1">Target: {rule.target}</p>
                            {rule.conditions && Object.keys(rule.conditions).length > 0 && (
                              <p className="text-xs text-slate-500">
                                Conditions: {JSON.stringify(rule.conditions)}
                              </p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                if (isLocal) {
                                  setEditingRule({ ...rule, id: -index } as any);
                                } else {
                                  setEditingRule(rule as PolicyRule);
                                }
                                setIsRuleDialogOpen(true);
                              }}
                              className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                if (confirm("Delete this rule?")) {
                                  if (isLocal) {
                                    setLocalRules(localRules.filter((_, i) => i !== index));
                                  } else {
                                    deleteRuleMutation.mutate((rule as PolicyRule).id);
                                  }
                                }
                              }}
                              className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </div>
          )}

          {activeTab === "bindings" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Bindings</h3>
                <button
                  type="button"
                  onClick={() => {
                    setEditingBinding(null);
                    setIsBindingDialogOpen(true);
                  }}
                  className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
                >
                  <Plus className="w-4 h-4" />
                  Add Binding
                </button>
              </div>

              {(() => {
                const displayBindings = currentPolicy ? sortedBindings : [...localBindings].sort((a, b) => (a.priority || 100) - (b.priority || 100));
                return displayBindings.length === 0 ? (
                  <p className="text-slate-400 text-center py-8">No bindings defined</p>
                ) : (
                <div className="space-y-2">
                  {displayBindings.map((binding: PolicyBinding | Partial<PolicyBinding>, index: number) => {
                    const bindingId = (binding as PolicyBinding).id || `local-${index}`;
                    const isLocal = !currentPolicy;
                    return (
                      <div
                        key={bindingId}
                        className="p-4 bg-slate-800 rounded-lg border border-slate-700 flex items-start justify-between"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-medium text-slate-300">
                              {binding.scope_type}
                            </span>
                            <span className="text-xs text-slate-500">Priority: {binding.priority || 100}</span>
                            {isLocal && (
                              <span className="text-xs text-slate-500">(pending)</span>
                            )}
                          </div>
                          <p className="text-sm text-slate-400">Scope ID: {binding.scope_id}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (isLocal) {
                                setEditingBinding({ ...binding, id: -index } as any);
                              } else {
                                setEditingBinding(binding as PolicyBinding);
                              }
                              setIsBindingDialogOpen(true);
                            }}
                            className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              if (confirm("Delete this binding?")) {
                                if (isLocal) {
                                  setLocalBindings(localBindings.filter((_, i) => i !== index));
                                } else {
                                  deleteBindingMutation.mutate((binding as PolicyBinding).id);
                                }
                              }
                            }}
                            className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
              })()}
            </div>
          )}

          {activeTab === "test" && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Policy Evaluate</h3>
              
              {!currentPolicy && (
                <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 mb-4">
                  <p className="text-slate-400 text-center">
                    Please create and save the policy first, then you can test it.
                  </p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Action *
                </label>
                <select
                  value={evaluateData.action}
                  onChange={(e) => setEvaluateData({ ...evaluateData, action: e.target.value })}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="tool.invoke">Tool Invoke</option>
                  <option value="agent.invoke">Agent Invoke</option>
                  <option value="resource.read">Resource Read</option>
                  <option value="resource.write">Resource Write</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Target *
                </label>
                <input
                  type="text"
                  required
                  value={evaluateData.target}
                  onChange={(e) => setEvaluateData({ ...evaluateData, target: e.target.value })}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="tool:pdf/*"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Subject ({t("common.optional")})
                </label>
                <input
                  type="text"
                  value={evaluateData.subject || ""}
                  onChange={(e) => setEvaluateData({ ...evaluateData, subject: e.target.value || undefined })}
                  className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  placeholder="user:123"
                />
              </div>

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Agent ({t("common.optional")})
                  </label>
                  <select
                    value={evaluateData.agent_id || ""}
                    onChange={(e) => setEvaluateData({ ...evaluateData, agent_id: e.target.value || undefined })}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="">{t("common.select")}...</option>
                    {agents.map((agent: any) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex-1">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                    Tool ({t("common.optional")})
                  </label>
                  <select
                    value={evaluateData.tool_id || ""}
                    onChange={(e) => setEvaluateData({ ...evaluateData, tool_id: e.target.value || undefined })}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="">{t("common.select")}...</option>
                    {tools.map((tool: any) => (
                      <option key={tool.id} value={tool.id}>
                        {tool.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={evaluateData.explain || false}
                    onChange={(e) => setEvaluateData({ ...evaluateData, explain: e.target.checked })}
                    className="w-4 h-4 text-purple-600 bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 rounded focus:ring-purple-500"
                  />
                  <span className="text-sm text-slate-700 dark:text-slate-300">Explain (show matched rules)</span>
                </label>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (!currentPolicy) {
                    setErrors({ general: "Please save the policy first before testing." });
                    setActiveTab("overview");
                    return;
                  }
                  handleEvaluate();
                }}
                disabled={isEvaluating || !evaluateData.target || !currentPolicy}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Play className="w-4 h-4" />
                {isEvaluating ? "Evaluating..." : "Evaluate"}
              </button>

              {errors.evaluate && (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-sm text-red-400">{errors.evaluate}</p>
                </div>
              )}

              {evaluateResult && (
                <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 space-y-4">
                  <div className="flex items-center gap-2">
                    <span className={`px-3 py-1 rounded text-sm font-medium ${
                      evaluateResult.decision === "allow"
                        ? "bg-green-500/20 text-green-400"
                        : "bg-red-500/20 text-red-400"
                    }`}>
                      {evaluateResult.decision.toUpperCase()}
                    </span>
                    {evaluateResult.rule_id && (
                      <span className="text-sm text-slate-400">Rule ID: {evaluateResult.rule_id}</span>
                    )}
                  </div>

                  {evaluateResult.matched_rules && evaluateResult.matched_rules.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-slate-300 mb-2">Matched Rules:</h4>
                      <div className="space-y-2">
                        {evaluateResult.matched_rules.map((rule, idx) => (
                          <div key={idx} className="p-2 bg-slate-700 rounded text-xs text-slate-300">
                            {rule.policy_name} - {rule.effect} - {rule.target} (Priority: {rule.priority})
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {evaluateResult.bindings_order && evaluateResult.bindings_order.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-slate-300 mb-2">Bindings Order:</h4>
                      <div className="space-y-2">
                        {evaluateResult.bindings_order.map((binding, idx) => (
                          <div key={idx} className="p-2 bg-slate-700 rounded text-xs text-slate-300">
                            {binding.policy_name} - {binding.scope_type}:{binding.scope_id} (Priority: {binding.priority})
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Rule Dialog */}
      <PolicyRuleDialog
        isOpen={isRuleDialogOpen}
        onClose={() => {
          setIsRuleDialogOpen(false);
          setEditingRule(null);
        }}
        rule={editingRule}
        policyId={currentPolicy?.id || "temp"}
        orgId={orgId}
        onSave={!currentPolicy ? (ruleData) => {
          // Only use onSave for new policies (before they're created)
          // For existing policies, PolicyRuleDialog will call API directly
            if (editingRule && typeof (editingRule as any).id === "number" && (editingRule as any).id < 0) {
              // Editing local rule
              const index = Math.abs((editingRule as any).id);
              setLocalRules(localRules.map((r, i) => i === index ? ruleData : r));
            } else {
              // New local rule
              setLocalRules([...localRules, ruleData]);
            }
        } : undefined}
      />

      {/* Binding Dialog */}
      <PolicyBindingDialog
        isOpen={isBindingDialogOpen}
        onClose={() => {
          setIsBindingDialogOpen(false);
          setEditingBinding(null);
        }}
        binding={editingBinding}
        policyId={currentPolicy?.id || "temp"}
        orgId={orgId}
        onSave={!currentPolicy ? (bindingData) => {
          // Only use onSave for new policies (before they're created)
          // For existing policies, PolicyBindingDialog will call API directly
            if (editingBinding && typeof (editingBinding as any).id === "number" && (editingBinding as any).id < 0) {
              // Editing local binding
              const index = Math.abs((editingBinding as any).id);
              setLocalBindings(localBindings.map((b, i) => i === index ? bindingData : b));
            } else {
              // New local binding
              setLocalBindings([...localBindings, bindingData]);
            }
        } : undefined}
      />
    </div>
  );
}
