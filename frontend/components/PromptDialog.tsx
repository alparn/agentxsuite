"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { promptsApi, api, resourcesApi } from "@/lib/api";
import { X } from "lucide-react";
import type { Prompt } from "@/lib/types";

interface PromptDialogProps {
  prompt?: Prompt | null;
  onClose: () => void;
  orgId: string;
  environments: any[];
}

export function PromptDialog({
  prompt,
  onClose,
  orgId,
  environments,
}: PromptDialogProps) {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    environment_id: "",
    description: "",
    input_schema: "{}",
    template_system: "",
    template_user: "",
    uses_resources: [] as string[],
    output_hints: "",
    enabled: true,
  });
  const [resourceInput, setResourceInput] = useState("");
  const [resourceDropdownOpen, setResourceDropdownOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const resourceDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch resources for the organization/environment
  const { data: resourcesData } = useQuery({
    queryKey: ["resources", orgId, formData.environment_id],
    queryFn: async () => {
      if (!orgId || !formData.environment_id) return [];
      const response = await resourcesApi.list(orgId);
      const resources = Array.isArray(response.data) 
        ? response.data 
        : response.data?.results || [];
      return resources.filter((r: any) => r.environment_id === formData.environment_id);
    },
    enabled: !!orgId && !!formData.environment_id,
  });

  const resources = Array.isArray(resourcesData) ? resourcesData : [];

  // Filter resources based on input
  const filteredResources = resources.filter((resource: any) =>
    resource.name.toLowerCase().includes(resourceInput.toLowerCase()) &&
    !formData.uses_resources.includes(resource.name)
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (resourceDropdownRef.current && !resourceDropdownRef.current.contains(event.target as Node)) {
        setResourceDropdownOpen(false);
      }
    };

    if (resourceDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [resourceDropdownOpen]);

  useEffect(() => {
    if (prompt) {
      const environmentId = prompt.environment_id || prompt.environment?.id || "";
      setFormData({
        name: prompt.name || "",
        environment_id: environmentId,
        description: prompt.description || "",
        input_schema: JSON.stringify(prompt.input_schema || {}, null, 2),
        template_system: prompt.template_system || "",
        template_user: prompt.template_user || "",
        uses_resources: Array.isArray(prompt.uses_resources) ? prompt.uses_resources : [],
        output_hints: prompt.output_hints ? JSON.stringify(prompt.output_hints, null, 2) : "",
        enabled: prompt.enabled ?? true,
      });
    } else {
      setFormData({
        name: "",
        environment_id: "",
        description: "",
        input_schema: "{}",
        template_system: "",
        template_user: "",
        uses_resources: [],
        output_hints: "",
        enabled: true,
      });
    }
    setResourceInput("");
    setResourceDropdownOpen(false);
    setErrors({});
  }, [prompt]);

  const addResource = (resourceName?: string) => {
    const nameToAdd = resourceName || resourceInput.trim();
    if (nameToAdd && !formData.uses_resources.includes(nameToAdd)) {
      setFormData({
        ...formData,
        uses_resources: [...formData.uses_resources, nameToAdd],
      });
      setResourceInput("");
      setResourceDropdownOpen(false);
    }
  };

  const removeResource = (index: number) => {
    setFormData({
      ...formData,
      uses_resources: formData.uses_resources.filter((_, i) => i !== index),
    });
  };

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Parse JSON fields
      let inputSchema: any;
      let outputHints: any = null;

      try {
        inputSchema = JSON.parse(data.input_schema);
      } catch (e) {
        throw new Error("Invalid JSON in input_schema field");
      }

      if (data.output_hints && data.output_hints.trim()) {
        try {
          outputHints = JSON.parse(data.output_hints);
        } catch (e) {
          throw new Error("Invalid JSON in output_hints field");
        }
      }

      const payload: any = {
        name: data.name,
        environment_id: data.environment_id,
        description: data.description,
        input_schema: inputSchema,
        template_system: data.template_system,
        template_user: data.template_user,
        uses_resources: data.uses_resources,
        enabled: data.enabled,
      };

      if (outputHints !== null) {
        payload.output_hints = outputHints;
      }

      if (prompt?.id) {
        return promptsApi.update(orgId, prompt.id, payload);
      } else {
        return promptsApi.create(orgId, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["prompts"] });
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
      <div className="bg-slate-900 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-xl sm:text-2xl font-bold text-white">
            {prompt ? t("common.edit") : t("prompts.newPrompt")}
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
              {t("prompts.environment")} *
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

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("common.description")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={3}
            />
            {errors.description && (
              <p className="text-red-400 text-xs mt-1">{errors.description}</p>
            )}
          </div>

          {/* Input Schema */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("prompts.inputSchema")} *
            </label>
            <textarea
              value={formData.input_schema}
              onChange={(e) => setFormData({ ...formData, input_schema: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={6}
              required
            />
            {errors.input_schema && (
              <p className="text-red-400 text-xs mt-1">{errors.input_schema}</p>
            )}
          </div>

          {/* Template System */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("prompts.templateSystem")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.template_system}
              onChange={(e) => setFormData({ ...formData, template_system: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={4}
              placeholder="Jinja2 template for system message"
            />
            {errors.template_system && (
              <p className="text-red-400 text-xs mt-1">{errors.template_system}</p>
            )}
          </div>

          {/* Template User */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("prompts.templateUser")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.template_user}
              onChange={(e) => setFormData({ ...formData, template_user: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={4}
              placeholder="Jinja2 template for user message"
            />
            {errors.template_user && (
              <p className="text-red-400 text-xs mt-1">{errors.template_user}</p>
            )}
          </div>

          {/* Uses Resources */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("prompts.usesResources")}
            </label>
            <div className="relative" ref={resourceDropdownRef}>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={resourceInput}
                  onChange={(e) => {
                    setResourceInput(e.target.value);
                    setResourceDropdownOpen(true);
                  }}
                  onFocus={() => setResourceDropdownOpen(true)}
                  placeholder={t("prompts.usesResources")}
                  className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <button
                  type="button"
                  onClick={() => addResource()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm"
                >
                  {t("common.add")}
                </button>
              </div>
              {resourceDropdownOpen && filteredResources.length > 0 && (
                <div className="absolute z-10 w-full mt-1 bg-slate-800 border border-slate-700 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {filteredResources.map((resource: any) => (
                    <button
                      key={resource.id}
                      type="button"
                      onClick={() => addResource(resource.name)}
                      className="w-full text-left px-3 py-2 text-white hover:bg-slate-700 text-sm"
                    >
                      {resource.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {formData.uses_resources.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {formData.uses_resources.map((resourceName, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-300 rounded text-sm"
                  >
                    {resourceName}
                    <button
                      type="button"
                      onClick={() => removeResource(index)}
                      className="text-purple-400 hover:text-purple-200"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
            {errors.uses_resources && (
              <p className="text-red-400 text-xs mt-1">{errors.uses_resources}</p>
            )}
          </div>

          {/* Output Hints */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              {t("prompts.outputHints")} ({t("common.optional")})
            </label>
            <textarea
              value={formData.output_hints}
              onChange={(e) => setFormData({ ...formData, output_hints: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
              rows={4}
              placeholder="{}"
            />
            {errors.output_hints && (
              <p className="text-red-400 text-xs mt-1">{errors.output_hints}</p>
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

