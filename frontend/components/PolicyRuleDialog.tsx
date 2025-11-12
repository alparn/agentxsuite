"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { policyRulesApi, api, resourcesApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { X } from "lucide-react";
import type { PolicyRule } from "@/lib/types";

interface PolicyRuleDialogProps {
  isOpen: boolean;
  onClose: () => void;
  rule?: PolicyRule | Partial<PolicyRule> | null;
  policyId: string;
  onSave?: (ruleData: Partial<PolicyRule>) => void;
  orgId?: string | null;
}

export function PolicyRuleDialog({
  isOpen,
  onClose,
  rule,
  policyId,
  onSave,
  orgId: propOrgId,
}: PolicyRuleDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { currentOrgId } = useAppStore();
  const orgId = propOrgId || currentOrgId;
  const [formData, setFormData] = useState({
    action: "tool.invoke" as string,
    target: "",
    effect: "allow" as "allow" | "deny",
    conditions: {} as Record<string, any>,
  });
  const [conditionsJson, setConditionsJson] = useState("{}");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [targetInput, setTargetInput] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const targetInputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  // Fetch tools for autocomplete
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
    enabled: !!orgId && isOpen && formData.action === "tool.invoke",
  });

  // Fetch agents for autocomplete
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
    enabled: !!orgId && isOpen && formData.action === "agent.invoke",
  });

  // Fetch resources for autocomplete
  const { data: resourcesData } = useQuery({
    queryKey: ["resources", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await resourcesApi.list(orgId);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen && formData.action.startsWith("resource."),
  });

  const tools = Array.isArray(toolsData) ? toolsData : [];
  const agents = Array.isArray(agentsData) ? agentsData : [];
  const resources = Array.isArray(resourcesData) ? resourcesData : [];

  // Extract namespace from various sources
  const getToolNamespace = (tool: any): string => {
    // Try connection.name first (most common)
    if (tool.connection?.name) {
      return tool.connection.name;
    }
    // Fallback to connection.namespace if available
    if (tool.connection?.namespace) {
      return tool.connection.namespace;
    }
    // Fallback to tool name as namespace
    return tool.name || "default";
  };

  const getResourceNamespace = (resource: any): string => {
    // Try config_json.uri first
    if (resource.config_json?.uri) {
      const uri = resource.config_json.uri;
      // Extract namespace from URI (e.g., "minio://org/env/path" -> "minio://org/env")
      const match = uri.match(/^([^:]+:\/\/[^\/]+(?:\/[^\/]+)?)/);
      if (match) return match[1];
    }
    // Try config_json.path
    if (resource.config_json?.path) {
      const path = resource.config_json.path;
      const match = path.match(/^([^\/]+(?:\/[^\/]+)?)/);
      if (match) return match[1];
    }
    // Try config_json.namespace
    if (resource.config_json?.namespace) {
      return resource.config_json.namespace;
    }
    // Fallback to resource name
    return resource.name || "default";
  };

  // Get target suggestions based on action and input
  const getTargetSuggestions = (): string[] => {
    const input = targetInput.toLowerCase().trim();
    const suggestions: string[] = [];

    if (formData.action === "tool.invoke") {
      // Format: tool:{namespace}/{name} or tool:*
      if (input === "" || input.startsWith("tool:")) {
        const prefix = input.startsWith("tool:") ? input.substring(5) : "";
        const [namespacePart, namePart] = prefix.split("/");
        
        tools.forEach((tool: any) => {
          const namespace = getToolNamespace(tool);
          const toolName = tool.name || "";
          
          // Match namespace
          if (!namespacePart || namespace.toLowerCase().includes(namespacePart.toLowerCase())) {
            // Match name
            if (!namePart || toolName.toLowerCase().includes(namePart.toLowerCase())) {
              suggestions.push(`tool:${namespace}/${toolName}`);
            }
          }
        });
        
        // Add wildcard option if input matches
        if (prefix === "" || prefix === "*" || prefix.startsWith("*")) {
          suggestions.push("tool:*");
        }
      }
    } else if (formData.action === "agent.invoke") {
      // Format: agent:{slug} or agent:*
      if (input === "" || input.startsWith("agent:")) {
        const prefix = input.startsWith("agent:") ? input.substring(6) : "";
        
        agents.forEach((agent: any) => {
          const identifier = agent.slug || agent.name || "";
          if (!prefix || identifier.toLowerCase().includes(prefix.toLowerCase())) {
            suggestions.push(`agent:${identifier}`);
          }
        });
        
        // Add wildcard option
        if (prefix === "" || prefix === "*") {
          suggestions.push("agent:*");
        }
      }
    } else if (formData.action.startsWith("resource.")) {
      // Format: resource:{namespace}/*
      if (input === "" || input.startsWith("resource:")) {
        const prefix = input.startsWith("resource:") ? input.substring(9).replace("/*", "") : "";
        
        resources.forEach((resource: any) => {
          const namespace = getResourceNamespace(resource);
          if (!prefix || namespace.toLowerCase().includes(prefix.toLowerCase())) {
            suggestions.push(`resource:${namespace}/*`);
          }
        });
        
        // Add wildcard option
        if (prefix === "" || prefix === "*") {
          suggestions.push("resource:*");
        }
      }
    }

    // Remove duplicates and limit to 10 suggestions
    return Array.from(new Set(suggestions)).slice(0, 10);
  };

  const suggestions = getTargetSuggestions();

  const handleSelectSuggestion = (suggestion: string) => {
    setTargetInput(suggestion);
    setFormData({ ...formData, target: suggestion });
    setShowSuggestions(false);
    setSelectedSuggestionIndex(-1);
    targetInputRef.current?.focus();
  };

  const handleTargetChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setTargetInput(value);
    setFormData({ ...formData, target: value });
    setShowSuggestions(true);
    setSelectedSuggestionIndex(-1);
  };

  const handleTargetFocus = () => {
    if (suggestions.length > 0) {
      setShowSuggestions(true);
    }
  };

  useEffect(() => {
    if (rule) {
      setFormData({
        action: rule.action || "tool.invoke",
        target: rule.target || "",
        effect: rule.effect || "allow",
        conditions: rule.conditions || {},
      });
      setTargetInput(rule.target || "");
      setConditionsJson(JSON.stringify(rule.conditions || {}, null, 2));
    } else {
      setFormData({
        action: "tool.invoke",
        target: "",
        effect: "allow",
        conditions: {},
      });
      setTargetInput("");
      setConditionsJson("{}");
    }
    setErrors({});
    setShowSuggestions(false);
    setSelectedSuggestionIndex(-1);
  }, [rule, isOpen]);

  // Update target input when formData.target changes externally
  useEffect(() => {
    if (formData.target !== targetInput) {
      setTargetInput(formData.target);
    }
  }, [formData.target]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!showSuggestions || suggestions.length === 0) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedSuggestionIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedSuggestionIndex((prev) => (prev > 0 ? prev - 1 : -1));
      } else if (e.key === "Enter" && selectedSuggestionIndex >= 0) {
        e.preventDefault();
        handleSelectSuggestion(suggestions[selectedSuggestionIndex]);
      } else if (e.key === "Escape") {
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
      }
    };

    if (showSuggestions) {
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }
  }, [showSuggestions, suggestions, selectedSuggestionIndex, handleSelectSuggestion]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        targetInputRef.current &&
        !targetInputRef.current.contains(event.target as Node) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
      }
    };

    if (showSuggestions) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showSuggestions]);

  const mutation = useMutation({
    mutationFn: async (data: Partial<PolicyRule>) => {
      const payload = {
        ...data,
        policy_id: policyId,
        conditions: data.conditions || {},
      };
      // If onSave callback is provided, use it instead of API call
      if (onSave) {
        onSave(payload);
        return { data: payload };
      }
      // Otherwise, use API
      if (rule && (rule as PolicyRule).id && typeof (rule as PolicyRule).id === "number") {
        return policyRulesApi.update((rule as PolicyRule).id.toString(), payload);
      } else {
        return policyRulesApi.create(payload);
      }
    },
    onSuccess: () => {
      if (!onSave) {
        queryClient.invalidateQueries({ queryKey: ["policy-rules"] });
        queryClient.invalidateQueries({ queryKey: ["policies"] });
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
    
    let parsedConditions = {};
    try {
      parsedConditions = JSON.parse(conditionsJson);
    } catch (err) {
      setErrors({ conditions: "Invalid JSON format" });
      return;
    }

    mutation.mutate({
      ...formData,
      conditions: parsedConditions,
    });
  };

  if (!isOpen) return null;

  const actionOptions = [
    { value: "tool.invoke", label: "Tool Invoke" },
    { value: "agent.invoke", label: "Agent Invoke" },
    { value: "resource.read", label: "Resource Read" },
    { value: "resource.write", label: "Resource Write" },
  ];

  const getTargetPlaceholder = () => {
    if (formData.action === "tool.invoke") {
      return "tool:{namespace}/{name} or tool:*";
    } else if (formData.action === "agent.invoke") {
      return "agent:{slug} or agent:*";
    } else if (formData.action.startsWith("resource.")) {
      return "resource:{namespace}/*";
    }
    return "Target pattern";
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-2xl shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900 z-10">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {rule ? t("common.edit") : "New Rule"}
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
              Action *
            </label>
            <select
              required
              value={formData.action}
              onChange={(e) => setFormData({ ...formData, action: e.target.value })}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {actionOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.action && (
              <p className="mt-1 text-sm text-red-500">{errors.action}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Target *
            </label>
            <div className="relative" ref={targetInputRef}>
              <input
                type="text"
                required
                value={targetInput}
                onChange={handleTargetChange}
                onFocus={handleTargetFocus}
                ref={targetInputRef}
                className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder={getTargetPlaceholder()}
                autoComplete="off"
              />
              {showSuggestions && suggestions.length > 0 && (
                <div
                  ref={suggestionsRef}
                  className="absolute z-50 w-full mt-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg shadow-lg max-h-60 overflow-y-auto"
                >
                  {suggestions.map((suggestion, index) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => handleSelectSuggestion(suggestion)}
                      className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                        index === selectedSuggestionIndex
                          ? "bg-purple-500/20 text-purple-400"
                          : "text-slate-900 dark:text-white hover:bg-purple-500/10"
                      }`}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {getTargetPlaceholder()}
              {suggestions.length > 0 && showSuggestions && (
                <span className="ml-2">({suggestions.length} suggestions)</span>
              )}
            </p>
            {errors.target && (
              <p className="mt-1 text-sm text-red-500">{errors.target}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Effect *
            </label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  value="allow"
                  checked={formData.effect === "allow"}
                  onChange={(e) => setFormData({ ...formData, effect: e.target.value as "allow" | "deny" })}
                  className="w-4 h-4 text-purple-600 bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 focus:ring-purple-500"
                />
                <span className="text-sm text-slate-700 dark:text-slate-300">Allow</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  value="deny"
                  checked={formData.effect === "deny"}
                  onChange={(e) => setFormData({ ...formData, effect: e.target.value as "allow" | "deny" })}
                  className="w-4 h-4 text-purple-600 bg-slate-100 dark:bg-slate-800 border-slate-300 dark:border-slate-700 focus:ring-purple-500"
                />
                <span className="text-sm text-slate-700 dark:text-slate-300">Deny</span>
              </label>
            </div>
            {errors.effect && (
              <p className="mt-1 text-sm text-red-500">{errors.effect}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              Conditions ({t("common.optional")})
            </label>
            <textarea
              value={conditionsJson}
              onChange={(e) => setConditionsJson(e.target.value)}
              rows={8}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
              placeholder='{"env": "production", "time_window": "09:00-17:00"}'
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Supported conditions: env==, time_window, tags, risk_level&lt;=, content_type, max_size_mb&lt;=, allowed_tools, allowed_resource_ns, depth&lt;=, budget_left_cents&gt;=, ttl_valid
            </p>
            {errors.conditions && (
              <p className="mt-1 text-sm text-red-500">{errors.conditions}</p>
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
                : rule
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

