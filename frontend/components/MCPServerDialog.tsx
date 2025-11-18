"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { mcpServersApi } from "@/lib/api";
import { X } from "lucide-react";
import type { MCPServerRegistration } from "@/lib/types";

interface MCPServerDialogProps {
  server?: MCPServerRegistration | null;
  onClose: () => void;
  orgId: string;
  environments: any[];
  onSuccess?: (server: any) => void;
}

export function MCPServerDialog({
  server,
  onClose,
  orgId,
  environments,
  onSuccess,
}: MCPServerDialogProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    description: "",
    environment_id: "",
    server_type: "http" as "stdio" | "http" | "ws",
    endpoint: "",
    command: "",
    args: "[]",
    env_vars: "{}",
    auth_method: "none" as "none" | "bearer" | "basic" | "api_key" | "oauth2",
    secret_ref: "",
    enabled: true,
    tags: "[]",
    metadata: "{}",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (server) {
      setFormData({
        name: server.name || "",
        slug: server.slug || "",
        description: server.description || "",
        environment_id: server.environment_id || server.environment?.id || "",
        server_type: server.server_type || "http",
        endpoint: server.endpoint || "",
        command: server.command || "",
        args: JSON.stringify(server.args || [], null, 2),
        env_vars: JSON.stringify(server.env_vars || {}, null, 2),
        auth_method: server.auth_method || "none",
        secret_ref: server.secret_ref || "",
        enabled: server.enabled ?? true,
        tags: JSON.stringify(server.tags || [], null, 2),
        metadata: JSON.stringify(server.metadata || {}, null, 2),
      });
    } else {
      setFormData({
        name: "",
        slug: "",
        description: "",
        environment_id: environments[0]?.id || "",
        server_type: "http",
        endpoint: "",
        command: "",
        args: "[]",
        env_vars: "{}",
        auth_method: "none",
        secret_ref: "",
        enabled: true,
        tags: "[]",
        metadata: "{}",
      });
    }
    setErrors({});
  }, [server, environments]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Parse JSON fields
      let args: string[];
      let envVars: Record<string, string>;
      let tags: string[];
      let metadata: Record<string, any>;

      try {
        args = JSON.parse(data.args);
      } catch (e) {
        throw new Error("Invalid JSON in args field");
      }

      try {
        envVars = JSON.parse(data.env_vars);
      } catch (e) {
        throw new Error("Invalid JSON in env_vars field");
      }

      try {
        tags = JSON.parse(data.tags);
      } catch (e) {
        throw new Error("Invalid JSON in tags field");
      }

      try {
        metadata = JSON.parse(data.metadata);
      } catch (e) {
        throw new Error("Invalid JSON in metadata field");
      }

      const payload: any = {
        name: data.name,
        slug: data.slug,
        description: data.description,
        environment_id: data.environment_id,
        server_type: data.server_type,
        endpoint: data.endpoint,
        command: data.command,
        args,
        env_vars: envVars,
        auth_method: data.auth_method,
        secret_ref: data.secret_ref,
        enabled: data.enabled,
        tags,
        metadata,
      };

      if (server?.id) {
        return mcpServersApi.update(orgId, server.id, payload);
      } else {
        return mcpServersApi.create(orgId, payload);
      }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      onSuccess?.(data.data);
    },
    onError: (error: any) => {
      const err = error?.response?.data || {};
      const newErrors: Record<string, string> = {};
      Object.keys(err).forEach((key) => {
        if (Array.isArray(err[key])) {
          newErrors[key] = err[key].join(", ");
        } else if (typeof err[key] === "string") {
          newErrors[key] = err[key];
        } else if (typeof err[key] === "object" && err[key] !== null) {
          newErrors[key] = JSON.stringify(err[key]);
        }
      });
      setErrors(newErrors);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field
    setErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-black bg-opacity-25" onClick={onClose} />

        <div className="relative w-full max-w-2xl bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {server ? "Edit MCP Server" : "Add MCP Server"}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            >
              <X className="h-6 w-6" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Basic Information */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Name *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleChange("name", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  required
                />
                {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Slug *
                </label>
                <input
                  type="text"
                  value={formData.slug}
                  onChange={(e) => handleChange("slug", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  placeholder="github"
                  required
                />
                {errors.slug && <p className="mt-1 text-sm text-red-600">{errors.slug}</p>}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => handleChange("description", e.target.value)}
                rows={2}
                className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Environment *
                </label>
                <select
                  value={formData.environment_id}
                  onChange={(e) => handleChange("environment_id", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  required
                >
                  <option value="">Select environment</option>
                  {environments.map((env: any) => (
                    <option key={env.id} value={env.id}>
                      {env.name}
                    </option>
                  ))}
                </select>
                {errors.environment_id && (
                  <p className="mt-1 text-sm text-red-600">{errors.environment_id}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Server Type *
                </label>
                <select
                  value={formData.server_type}
                  onChange={(e) => handleChange("server_type", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  required
                >
                  <option value="http">HTTP</option>
                  <option value="stdio">stdio (native)</option>
                  <option value="ws">WebSocket</option>
                </select>
              </div>
            </div>

            {/* Connection Details */}
            {(formData.server_type === "http" || formData.server_type === "ws") && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Endpoint URL *
                </label>
                <input
                  type="url"
                  value={formData.endpoint}
                  onChange={(e) => handleChange("endpoint", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  placeholder="https://api.example.com/.well-known/mcp"
                  required={formData.server_type === "http" || formData.server_type === "ws"}
                />
                {errors.endpoint && <p className="mt-1 text-sm text-red-600">{errors.endpoint}</p>}
              </div>
            )}

            {formData.server_type === "stdio" && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Command *
                  </label>
                  <input
                    type="text"
                    value={formData.command}
                    onChange={(e) => handleChange("command", e.target.value)}
                    className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                    placeholder="npx"
                    required={formData.server_type === "stdio"}
                  />
                  {errors.command && <p className="mt-1 text-sm text-red-600">{errors.command}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Arguments (JSON array)
                  </label>
                  <textarea
                    value={formData.args}
                    onChange={(e) => handleChange("args", e.target.value)}
                    rows={3}
                    className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white font-mono"
                    placeholder='["-y", "@modelcontextprotocol/server-github"]'
                  />
                  {errors.args && <p className="mt-1 text-sm text-red-600">{errors.args}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    Environment Variables (JSON object)
                  </label>
                  <textarea
                    value={formData.env_vars}
                    onChange={(e) => handleChange("env_vars", e.target.value)}
                    rows={3}
                    className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white font-mono"
                    placeholder='{"GITHUB_TOKEN": "secret://github-pat"}'
                  />
                  {errors.env_vars && <p className="mt-1 text-sm text-red-600">{errors.env_vars}</p>}
                </div>
              </>
            )}

            {/* Authentication */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Auth Method
                </label>
                <select
                  value={formData.auth_method}
                  onChange={(e) => handleChange("auth_method", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                >
                  <option value="none">None</option>
                  <option value="bearer">Bearer Token</option>
                  <option value="basic">Basic Auth</option>
                  <option value="api_key">API Key</option>
                  <option value="oauth2">OAuth2</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Secret Reference
                </label>
                <input
                  type="text"
                  value={formData.secret_ref}
                  onChange={(e) => handleChange("secret_ref", e.target.value)}
                  className="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm dark:bg-gray-700 dark:text-white"
                  placeholder="github-pat"
                />
                {errors.secret_ref && <p className="mt-1 text-sm text-red-600">{errors.secret_ref}</p>}
              </div>
            </div>

            {/* Status */}
            <div className="flex items-center">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => handleChange("enabled", e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label className="ml-2 block text-sm text-gray-900 dark:text-white">
                Enabled
              </label>
            </div>

            {/* Buttons */}
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-700 hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {mutation.isPending ? "Saving..." : server ? "Update" : "Create"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
