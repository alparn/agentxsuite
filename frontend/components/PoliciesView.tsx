"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { policiesApi, policyRulesApi, policyBindingsApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, Shield, Edit, Trash2 } from "lucide-react";
import { PolicyDialog } from "./PolicyDialog";
import type { Policy, PolicyRule, PolicyBinding } from "@/lib/types";

export function PoliciesView() {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const [selectedPolicy, setSelectedPolicy] = useState<Policy | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null);

  // Fetch organizations and auto-select first one if none selected
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      // Handle both old format (array) and new format (object with organizations)
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  const { data: policiesData, isLoading } = useQuery({
    queryKey: ["policies", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await policiesApi.list(orgId);
      // Handle paginated response (DRF returns {results: [...], count, next, previous})
      // or direct array response
      if (Array.isArray(response.data)) {
        return response.data;
      } else if (response.data?.results && Array.isArray(response.data.results)) {
        return response.data.results;
      }
      return [];
    },
    enabled: !!orgId,
  });

  // Fetch rules and bindings for all policies
  const { data: allRulesData } = useQuery({
    queryKey: ["policy-rules"],
    queryFn: async () => {
      const response = await policyRulesApi.list();
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: allBindingsData } = useQuery({
    queryKey: ["policy-bindings"],
    queryFn: async () => {
      const response = await policyBindingsApi.list();
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const policies = Array.isArray(policiesData) ? policiesData : [];
  const allRules = Array.isArray(allRulesData) ? allRulesData : [];
  const allBindings = Array.isArray(allBindingsData) ? allBindingsData : [];

  // Helper function to get rules count for a policy
  const getRulesCount = (policyId: string) => {
    return allRules.filter((r: PolicyRule) => r.policy_id === policyId).length;
  };

  // Helper function to get bindings count for a policy
  const getBindingsCount = (policyId: string) => {
    return allBindings.filter((b: PolicyBinding) => b.policy_id === policyId).length;
  };

  // Helper function to get most common scope type for a policy
  const getMostCommonScopeType = (policyId: string) => {
    const policyBindings = allBindings.filter((b: PolicyBinding) => b.policy_id === policyId);
    if (policyBindings.length === 0) return "-";
    
    const scopeTypes = policyBindings.map((b: PolicyBinding) => b.scope_type);
    const counts: Record<string, number> = {};
    scopeTypes.forEach((type) => {
      counts[type] = (counts[type] || 0) + 1;
    });
    
    const mostCommon = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
    return mostCommon ? mostCommon[0] : "-";
  };

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (policyId: string) => {
      if (!orgId) throw new Error("Organization ID is required");
      return policiesApi.delete(orgId, policyId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      queryClient.invalidateQueries({ queryKey: ["policy-rules"] });
      queryClient.invalidateQueries({ queryKey: ["policy-bindings"] });
    },
    onError: (error: any) => {
      console.error("Error deleting policy:", error);
      alert(error.response?.data?.detail || error.message || "Failed to delete policy");
    },
  });

  const handleDelete = (policy: Policy) => {
    if (confirm(`Are you sure you want to delete the policy "${policy.name}"? This action cannot be undone.`)) {
      deleteMutation.mutate(policy.id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("policies.title")}
          </h1>
          <p className="text-slate-400">Manage access control policies</p>
        </div>
        <button
          onClick={() => {
            setEditingPolicy(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
        >
          <Plus className="w-5 h-5" />
          {t("policies.newPolicy")}
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.name")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Rules
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Bindings
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    Scope
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {policies?.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  policies?.map((policy: Policy) => (
                    <tr
                      key={policy.id}
                      className="hover:bg-slate-800/50 cursor-pointer"
                      onClick={() => setSelectedPolicy(policy)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-medium flex items-center gap-2">
                        <Shield className="w-4 h-4 text-purple-400" />
                        {policy.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          policy.is_active ?? policy.enabled
                            ? "bg-green-500/20 text-green-400"
                            : "bg-red-500/20 text-red-400"
                        }`}>
                          {policy.is_active ?? policy.enabled ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {getRulesCount(policy.id)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {getBindingsCount(policy.id)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {getMostCommonScopeType(policy.id)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingPolicy(policy);
                              setIsDialogOpen(true);
                            }}
                            className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                            title={t("common.edit")}
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedPolicy(policy);
                            }}
                            className="text-purple-400 hover:text-purple-300 text-sm"
                          >
                            View
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDelete(policy);
                            }}
                            disabled={deleteMutation.isPending}
                            className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors disabled:opacity-50"
                            title={t("common.delete")}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Policy Detail Dialog */}
      {selectedPolicy && (
        <PolicyDialog
          isOpen={!!selectedPolicy}
          onClose={() => setSelectedPolicy(null)}
          policy={selectedPolicy}
          orgId={orgId}
        />
      )}

      {/* Policy Edit/Create Dialog */}
      <PolicyDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setEditingPolicy(null);
        }}
        policy={editingPolicy}
        orgId={orgId}
      />
    </div>
  );
}
