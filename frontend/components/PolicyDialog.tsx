"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X } from "lucide-react";

interface PolicyDialogProps {
  isOpen: boolean;
  onClose: () => void;
  policy?: any;
  orgId: string | null;
}

export function PolicyDialog({
  isOpen,
  onClose,
  policy,
  orgId,
}: PolicyDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    environment_id: "",
    description: "",
    allow: [] as string[],
    deny: [] as string[],
    allow_resources: [] as string[],
    deny_resources: [] as string[],
    allow_prompts: [] as string[],
    deny_prompts: [] as string[],
    enabled: true,
  });
  const [activeTab, setActiveTab] = useState<"tools" | "resources" | "prompts">("tools");
  const [allowInput, setAllowInput] = useState("");
  const [denyInput, setDenyInput] = useState("");
  const [allowDropdownOpen, setAllowDropdownOpen] = useState(false);
  const [denyDropdownOpen, setDenyDropdownOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const allowDropdownRef = useRef<HTMLDivElement>(null);
  const denyDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch environments for the organization
  const { data: environmentsData } = useQuery({
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

  // Fetch tools for the organization
  const { data: toolsData } = useQuery({
    queryKey: ["tools", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/tools/`);
      // Handle paginated response
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  // Fetch resources for the organization
  const { data: resourcesData } = useQuery({
    queryKey: ["resources", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/resources/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  // Fetch prompts for the organization
  const { data: promptsData } = useQuery({
    queryKey: ["prompts", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/prompts/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];
  const tools = Array.isArray(toolsData) ? toolsData : [];
  const resources = Array.isArray(resourcesData) ? resourcesData : [];
  const prompts = Array.isArray(promptsData) ? promptsData : [];
  
  // Filter based on active tab and input
  const getFilteredAllowItems = () => {
    const input = allowInput.toLowerCase();
    if (activeTab === "tools") {
      return tools.filter((tool: any) => 
        tool.name.toLowerCase().includes(input) &&
        !formData.allow.includes(tool.name)
      );
    } else if (activeTab === "resources") {
      return resources.filter((resource: any) => 
        resource.name.toLowerCase().includes(input) &&
        !formData.allow_resources.includes(resource.name)
      );
    } else {
      return prompts.filter((prompt: any) => 
        prompt.name.toLowerCase().includes(input) &&
        !formData.allow_prompts.includes(prompt.name)
      );
    }
  };

  const getFilteredDenyItems = () => {
    const input = denyInput.toLowerCase();
    if (activeTab === "tools") {
      return tools.filter((tool: any) => 
        tool.name.toLowerCase().includes(input) &&
        !formData.deny.includes(tool.name)
      );
    } else if (activeTab === "resources") {
      return resources.filter((resource: any) => 
        resource.name.toLowerCase().includes(input) &&
        !formData.deny_resources.includes(resource.name)
      );
    } else {
      return prompts.filter((prompt: any) => 
        prompt.name.toLowerCase().includes(input) &&
        !formData.deny_prompts.includes(prompt.name)
      );
    }
  };

  const filteredAllowItems = getFilteredAllowItems();
  const filteredDenyItems = getFilteredDenyItems();

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (allowDropdownRef.current && !allowDropdownRef.current.contains(event.target as Node)) {
        setAllowDropdownOpen(false);
      }
      if (denyDropdownRef.current && !denyDropdownRef.current.contains(event.target as Node)) {
        setDenyDropdownOpen(false);
      }
    };

    if (allowDropdownOpen || denyDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [allowDropdownOpen, denyDropdownOpen]);

  useEffect(() => {
    if (policy) {
      // Parse rules_json to extract description, allow, deny
      const rulesJson = policy.rules_json || {};
      // Handle both environment_id (string) and environment (object)
      const environmentId = policy.environment_id || policy.environment?.id || "";
      setFormData({
        name: policy.name || "",
        environment_id: environmentId,
        description: rulesJson.description || "",
        allow: Array.isArray(rulesJson.allow) ? rulesJson.allow : [],
        deny: Array.isArray(rulesJson.deny) ? rulesJson.deny : [],
        allow_resources: Array.isArray(rulesJson.allow_resources) ? rulesJson.allow_resources : [],
        deny_resources: Array.isArray(rulesJson.deny_resources) ? rulesJson.deny_resources : [],
        allow_prompts: Array.isArray(rulesJson.allow_prompts) ? rulesJson.allow_prompts : [],
        deny_prompts: Array.isArray(rulesJson.deny_prompts) ? rulesJson.deny_prompts : [],
        enabled: policy.enabled ?? true,
      });
    } else {
      setFormData({
        name: "",
        environment_id: "",
        description: "",
        allow: [],
        deny: [],
        allow_resources: [],
        deny_resources: [],
        allow_prompts: [],
        deny_prompts: [],
        enabled: true,
      });
    }
    setAllowInput("");
    setDenyInput("");
    setAllowDropdownOpen(false);
    setDenyDropdownOpen(false);
    setErrors({});
  }, [policy, isOpen]);

  const addToAllow = (name?: string) => {
    const nameToAdd = name || allowInput.trim();
    if (!nameToAdd) return;

    if (activeTab === "tools") {
      if (!formData.allow.includes(nameToAdd)) {
        setFormData({
          ...formData,
          allow: [...formData.allow, nameToAdd],
        });
      }
    } else if (activeTab === "resources") {
      if (!formData.allow_resources.includes(nameToAdd)) {
        setFormData({
          ...formData,
          allow_resources: [...formData.allow_resources, nameToAdd],
        });
      }
    } else {
      if (!formData.allow_prompts.includes(nameToAdd)) {
        setFormData({
          ...formData,
          allow_prompts: [...formData.allow_prompts, nameToAdd],
        });
      }
    }
    setAllowInput("");
    setAllowDropdownOpen(false);
  };

  const removeFromAllow = (index: number) => {
    if (activeTab === "tools") {
      setFormData({
        ...formData,
        allow: formData.allow.filter((_, i) => i !== index),
      });
    } else if (activeTab === "resources") {
      setFormData({
        ...formData,
        allow_resources: formData.allow_resources.filter((_, i) => i !== index),
      });
    } else {
      setFormData({
        ...formData,
        allow_prompts: formData.allow_prompts.filter((_, i) => i !== index),
      });
    }
  };

  const addToDeny = (name?: string) => {
    const nameToAdd = name || denyInput.trim();
    if (!nameToAdd) return;

    if (activeTab === "tools") {
      if (!formData.deny.includes(nameToAdd)) {
        setFormData({
          ...formData,
          deny: [...formData.deny, nameToAdd],
        });
      }
    } else if (activeTab === "resources") {
      if (!formData.deny_resources.includes(nameToAdd)) {
        setFormData({
          ...formData,
          deny_resources: [...formData.deny_resources, nameToAdd],
        });
      }
    } else {
      if (!formData.deny_prompts.includes(nameToAdd)) {
        setFormData({
          ...formData,
          deny_prompts: [...formData.deny_prompts, nameToAdd],
        });
      }
    }
    setDenyInput("");
    setDenyDropdownOpen(false);
  };

  const removeFromDeny = (index: number) => {
    if (activeTab === "tools") {
      setFormData({
        ...formData,
        deny: formData.deny.filter((_, i) => i !== index),
      });
    } else if (activeTab === "resources") {
      setFormData({
        ...formData,
        deny_resources: formData.deny_resources.filter((_, i) => i !== index),
      });
    } else {
      setFormData({
        ...formData,
        deny_prompts: formData.deny_prompts.filter((_, i) => i !== index),
      });
    }
  };

  const getAllowList = () => {
    if (activeTab === "tools") return formData.allow;
    if (activeTab === "resources") return formData.allow_resources;
    return formData.allow_prompts;
  };

  const getDenyList = () => {
    if (activeTab === "tools") return formData.deny;
    if (activeTab === "resources") return formData.deny_resources;
    return formData.deny_prompts;
  };

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Build rules_json from form data
      const rulesJson: any = {};
      if (data.description) {
        rulesJson.description = data.description;
      }
      if (data.allow.length > 0) {
        rulesJson.allow = data.allow;
      }
      if (data.deny.length > 0) {
        rulesJson.deny = data.deny;
      }
      if (data.allow_resources.length > 0) {
        rulesJson.allow_resources = data.allow_resources;
      }
      if (data.deny_resources.length > 0) {
        rulesJson.deny_resources = data.deny_resources;
      }
      if (data.allow_prompts.length > 0) {
        rulesJson.allow_prompts = data.allow_prompts;
      }
      if (data.deny_prompts.length > 0) {
        rulesJson.deny_prompts = data.deny_prompts;
      }

      const payload: any = {
        name: data.name,
        rules_json: rulesJson,
        enabled: data.enabled,
      };

      // Only include environment_id if it's set
      if (data.environment_id) {
        payload.environment_id = data.environment_id;
      }

      if (policy) {
        return api.put(`/orgs/${orgId}/policies/${policy.id}/`, payload);
      } else {
        return api.post(`/orgs/${orgId}/policies/`, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["policies"] });
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
    mutation.mutate(formData);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-2 sm:p-4">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-3xl shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-800 sticky top-0 bg-white dark:bg-slate-900 z-10">
          <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-white">
            {policy ? t("common.edit") : t("policies.newPolicy")}
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
              {t("common.name")} *
            </label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder={t("common.name")}
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-500">{errors.name}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("agents.environment")} ({t("common.optional")})
            </label>
            <select
              value={formData.environment_id}
              onChange={(e) =>
                setFormData({ ...formData, environment_id: e.target.value })
              }
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="">{t("common.select")}...</option>
              {environments?.map((env: any) => (
                <option key={env.id} value={env.id}>
                  {env.name} ({env.type})
                </option>
              ))}
            </select>
            {errors.environment_id && (
              <p className="mt-1 text-sm text-red-500">{errors.environment_id}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("common.description")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={3}
              className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder={t("common.description")}
            />
          </div>

          {/* Tabs */}
          <div className="border-b border-slate-200 dark:border-slate-700">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("tools")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "tools"
                    ? "border-b-2 border-purple-500 text-purple-500"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                {t("tools.title")}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("resources")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "resources"
                    ? "border-b-2 border-purple-500 text-purple-500"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                {t("resources.title")}
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("prompts")}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === "prompts"
                    ? "border-b-2 border-purple-500 text-purple-500"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200"
                }`}
              >
                {t("prompts.title")}
              </button>
            </div>
          </div>

          {/* Allow List */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("policies.allow")}
            </label>
            <div className="relative">
              <div className="flex gap-2 mb-2">
                <div className="flex-1 relative" ref={allowDropdownRef}>
                  <input
                    type="text"
                    value={allowInput}
                    onChange={(e) => {
                      setAllowInput(e.target.value);
                      setAllowDropdownOpen(true);
                    }}
                    onFocus={() => setAllowDropdownOpen(true)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        if (filteredAllowItems.length > 0) {
                          const item = filteredAllowItems[0];
                          addToAllow(item.name);
                        } else {
                          addToAllow();
                        }
                      }
                    }}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder={
                      activeTab === "tools"
                        ? t("policies.enterToolName")
                        : activeTab === "resources"
                        ? t("resources.name")
                        : t("prompts.name")
                    }
                  />
                  {allowDropdownOpen && filteredAllowItems.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                      {filteredAllowItems.map((item: any) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => addToAllow(item.name)}
                          className="w-full text-left px-4 py-2 hover:bg-purple-500/10 text-slate-900 dark:text-white text-sm"
                        >
                          {item.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => addToAllow()}
                  className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors"
                >
                  {t("common.add")}
                </button>
              </div>
              {getAllowList().length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {getAllowList().map((item, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm"
                    >
                      {item}
                      <button
                        type="button"
                        onClick={() => removeFromAllow(index)}
                        className="hover:text-green-300"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Deny List */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
              {t("policies.deny")}
            </label>
            <div className="relative">
              <div className="flex gap-2 mb-2">
                <div className="flex-1 relative" ref={denyDropdownRef}>
                  <input
                    type="text"
                    value={denyInput}
                    onChange={(e) => {
                      setDenyInput(e.target.value);
                      setDenyDropdownOpen(true);
                    }}
                    onFocus={() => setDenyDropdownOpen(true)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        if (filteredDenyItems.length > 0) {
                          const item = filteredDenyItems[0];
                          addToDeny(item.name);
                        } else {
                          addToDeny();
                        }
                      }
                    }}
                    className="w-full px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder={
                      activeTab === "tools"
                        ? t("policies.enterToolName")
                        : activeTab === "resources"
                        ? t("resources.name")
                        : t("prompts.name")
                    }
                  />
                  {denyDropdownOpen && filteredDenyItems.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                      {filteredDenyItems.map((item: any) => (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => addToDeny(item.name)}
                          className="w-full text-left px-4 py-2 hover:bg-red-500/10 text-slate-900 dark:text-white text-sm"
                        >
                          {item.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => addToDeny()}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                >
                  {t("common.add")}
                </button>
              </div>
              {getDenyList().length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {getDenyList().map((item, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-red-500/20 text-red-400 rounded-full text-sm"
                    >
                      {item}
                      <button
                        type="button"
                        onClick={() => removeFromDeny(index)}
                        className="hover:text-red-300"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
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
                : policy
                  ? t("common.save")
                  : t("common.create")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

