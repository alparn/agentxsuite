"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, Plus } from "lucide-react";
import { EnvironmentDialog } from "./EnvironmentDialog";
import { ConnectionDialog } from "./ConnectionDialog";

interface MCPToolCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  orgId: string | null;
  envId: string | null;
  tool?: { name: string }; // MCP Tool from MCP Fabric (only has name)
  onSuccess?: () => void;
}

export function MCPToolCreateDialog({
  isOpen,
  onClose,
  orgId,
  envId,
  tool,
  onSuccess,
}: MCPToolCreateDialogProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    name: "",
    version: "1.0.0",
    description: "",
    environment_id: envId || "",
    connection_id: "",
    schema_json: JSON.stringify(
      {
        type: "object",
        properties: {},
        required: [],
      },
      null,
      2
    ),
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showEnvironmentDialog, setShowEnvironmentDialog] = useState(false);
  const [showConnectionDialog, setShowConnectionDialog] = useState(false);
  const [loadingTool, setLoadingTool] = useState(false);
  const [toolData, setToolData] = useState<any>(null);

  // Fetch environments for the organization
  const { data: environmentsData, isLoading: isLoadingEnvs, refetch: refetchEnvironments } = useQuery({
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

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Fetch connections for the organization and selected environment
  const { data: connectionsData, isLoading: isLoadingConnections, refetch: refetchConnections } = useQuery({
    queryKey: ["connections", orgId, formData.environment_id],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/connections/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId && isOpen,
  });

  const allConnections = Array.isArray(connectionsData) ? connectionsData : [];
  // Filter connections by selected environment
  const connections = formData.environment_id
    ? allConnections.filter((conn: any) => conn.environment_id === formData.environment_id || conn.environment?.id === formData.environment_id)
    : [];

  // Load tool data from Django API when editing
  useEffect(() => {
    const loadToolData = async () => {
      if (!isOpen || !tool || !orgId || !envId) {
        setToolData(null);
        return;
      }

      setLoadingTool(true);
      try {
        // Fetch all tools and find the one matching the name
        const response = await api.get(`/orgs/${orgId}/tools/`);
        const tools = Array.isArray(response.data)
          ? response.data
          : response.data?.results || [];
        
        const foundTool = tools.find(
          (t: any) =>
            t.name === tool.name &&
            (t.environment_id === envId || t.environment?.id === envId)
        );

        if (foundTool) {
          setToolData(foundTool);
          // Extract description from schema_json if present
          const description =
            foundTool.schema_json?.description || foundTool.description || "";
          setFormData({
            name: foundTool.name || "",
            version: foundTool.version || "1.0.0",
            description: description,
            environment_id: foundTool.environment_id || envId,
            connection_id: foundTool.connection_id || "",
            schema_json: JSON.stringify(foundTool.schema_json || {}, null, 2),
          });
        } else {
          setErrors({ general: "Tool not found in database" });
        }
      } catch (error: any) {
        setErrors({
          general: error.response?.data?.detail || "Failed to load tool",
        });
      } finally {
        setLoadingTool(false);
      }
    };

    if (isOpen && tool) {
      loadToolData();
    } else if (!isOpen) {
      // Reset form when dialog closes
      setFormData({
        name: "",
        version: "1.0.0",
        description: "",
        environment_id: envId || "",
        connection_id: "",
        schema_json: JSON.stringify(
          {
            type: "object",
            properties: {},
            required: [],
          },
          null,
          2
        ),
      });
      setErrors({});
      setToolData(null);
    } else if (envId && !formData.environment_id) {
      // Set environment_id when dialog opens if envId prop is provided
      setFormData((prev) => ({ ...prev, environment_id: envId }));
    }
  }, [isOpen, envId, tool, orgId]);

  const mutation = useMutation({
    mutationFn: async (data: any) => {
      // Parse schema_json and add description
      let schemaJson: any;
      try {
        schemaJson = JSON.parse(data.schema_json);
      } catch (e) {
        throw new Error("Invalid JSON in schema_json field");
      }

      // Add description to schema if provided
      if (data.description) {
        schemaJson.description = data.description;
      }

      const payload: any = {
        name: data.name,
        version: data.version,
        environment_id: data.environment_id || envId,
        schema_json: schemaJson,
        enabled: true,
      };

      // Include connection_id if provided, otherwise backend will create local connection
      if (data.connection_id) {
        payload.connection_id = data.connection_id;
      }

      // Use PUT for update, POST for create
      if (toolData?.id) {
        return api.put(`/orgs/${orgId}/tools/${toolData.id}/`, payload);
      } else {
        return api.post(`/orgs/${orgId}/tools/`, payload);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tools", orgId] });
      setErrors({});
      onSuccess?.();
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
        setErrors({ general: error.message || "Failed to create tool" });
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!formData.name.trim()) {
      setErrors({ name: "Name is required" });
      return;
    }

    if (!formData.version.trim()) {
      setErrors({ version: "Version is required" });
      return;
    }

    if (!formData.environment_id) {
      setErrors({ environment_id: "Environment is required" });
      return;
    }

    try {
      JSON.parse(formData.schema_json);
    } catch (e) {
      setErrors({
        schema_json: "Invalid JSON format. Please check your schema.",
      });
      return;
    }

    mutation.mutate(formData);
  };

  const formatJSON = () => {
    try {
      const parsed = JSON.parse(formData.schema_json);
      setFormData({
        ...formData,
        schema_json: JSON.stringify(parsed, null, 2),
      });
      if (errors.schema_json) {
        setErrors({ ...errors, schema_json: "" });
      }
    } catch (e) {
      setErrors({
        schema_json: "Invalid JSON. Cannot format.",
      });
    }
  };

  const addProperty = () => {
    try {
      const schema = JSON.parse(formData.schema_json);
      if (!schema.properties) {
        schema.properties = {};
      }
      const propName = `property${Object.keys(schema.properties).length + 1}`;
      schema.properties[propName] = {
        type: "string",
        description: "",
      };
      setFormData({
        ...formData,
        schema_json: JSON.stringify(schema, null, 2),
      });
    } catch (e) {
      setErrors({
        schema_json: "Invalid schema. Cannot add property.",
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg w-full max-w-4xl shadow-xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-slate-800">
          <h2 className="text-xl font-semibold text-white">
            {toolData ? "Edit MCP Tool" : "Create MCP Tool"}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg transition-colors"
            disabled={mutation.isPending || loadingTool}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6 overflow-y-auto flex-1">
          {loadingTool && (
            <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <p className="text-sm text-blue-400">Loading tool data...</p>
            </div>
          )}
          {errors.general && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="text-sm text-red-400">{errors.general}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Tool Name *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => {
                  setFormData({ ...formData, name: e.target.value });
                  if (errors.name) setErrors({ ...errors, name: "" });
                }}
                required
                disabled={!!toolData} // Disable name field when editing
                className={`w-full px-3 py-2 bg-slate-800 border rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  errors.name ? "border-red-500" : "border-slate-700"
                } ${toolData ? "opacity-50 cursor-not-allowed" : ""}`}
                placeholder="my-tool"
              />
              {errors.name && (
                <p className="mt-1 text-xs text-red-400">{errors.name}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Version *
              </label>
              <input
                type="text"
                value={formData.version}
                onChange={(e) => {
                  setFormData({ ...formData, version: e.target.value });
                  if (errors.version) setErrors({ ...errors, version: "" });
                }}
                required
                className={`w-full px-3 py-2 bg-slate-800 border rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                  errors.version ? "border-red-500" : "border-slate-700"
                }`}
                placeholder="1.0.0"
              />
              {errors.version && (
                <p className="mt-1 text-xs text-red-400">{errors.version}</p>
              )}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-300">
                Environment *
              </label>
              <button
                type="button"
                onClick={() => setShowEnvironmentDialog(true)}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
              >
                <Plus className="w-3 h-3" />
                New Environment
              </button>
            </div>
            <select
              value={formData.environment_id}
              onChange={(e) => {
                setFormData({ 
                  ...formData, 
                  environment_id: e.target.value,
                  connection_id: "", // Reset connection when environment changes
                });
                if (errors.environment_id)
                  setErrors({ ...errors, environment_id: "" });
              }}
              required
              className={`w-full px-3 py-2 bg-slate-800 border rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.environment_id ? "border-red-500" : "border-slate-700"
              }`}
            >
              <option value="">Select environment...</option>
              {isLoadingEnvs ? (
                <option value="" disabled>
                  Loading...
                </option>
              ) : environments.length === 0 ? (
                <option value="" disabled>
                  No environments available
                </option>
              ) : (
                environments.map((env: any) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.type})
                  </option>
                ))
              )}
            </select>
            {errors.environment_id && (
              <p className="mt-1 text-xs text-red-400">{errors.environment_id}</p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-300">
                Connection ({formData.environment_id ? "optional" : "select environment first"})
              </label>
              {formData.environment_id && (
                <button
                  type="button"
                  onClick={() => setShowConnectionDialog(true)}
                  className="flex items-center gap-1 px-2 py-1 text-xs bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
                >
                  <Plus className="w-3 h-3" />
                  New Connection
                </button>
              )}
            </div>
            <select
              value={formData.connection_id}
              onChange={(e) => {
                setFormData({ ...formData, connection_id: e.target.value });
                if (errors.connection_id)
                  setErrors({ ...errors, connection_id: "" });
              }}
              disabled={!formData.environment_id}
              className={`w-full px-3 py-2 bg-slate-800 border rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.connection_id ? "border-red-500" : "border-slate-700"
              } ${!formData.environment_id ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <option value="">
                {!formData.environment_id 
                  ? "Select environment first..." 
                  : "Use default (mcp-fabric-local)..."}
              </option>
              {isLoadingConnections ? (
                <option value="" disabled>
                  Loading...
                </option>
              ) : connections.length === 0 && formData.environment_id ? (
                <option value="" disabled>
                  No connections available (will use default)
                </option>
              ) : (
                connections.map((conn: any) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.endpoint})
                  </option>
                ))
              )}
            </select>
            {errors.connection_id && (
              <p className="mt-1 text-xs text-red-400">{errors.connection_id}</p>
            )}
            <p className="mt-1 text-xs text-slate-500">
              {formData.connection_id 
                ? "Tool will be linked to the selected connection."
                : "If no connection is selected, a default 'mcp-fabric-local' connection will be created automatically."}
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description
            </label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="What does this tool do?"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-slate-300">
                JSON Schema (Input Parameters) *
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={addProperty}
                  className="px-3 py-1 text-xs bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
                >
                  Add Property
                </button>
                <button
                  type="button"
                  onClick={formatJSON}
                  className="px-3 py-1 text-xs bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
                >
                  Format JSON
                </button>
              </div>
            </div>
            <textarea
              value={formData.schema_json}
              onChange={(e) => {
                setFormData({ ...formData, schema_json: e.target.value });
                if (errors.schema_json)
                  setErrors({ ...errors, schema_json: "" });
              }}
              required
              rows={12}
              className={`w-full px-3 py-2 bg-slate-800 border rounded text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 ${
                errors.schema_json ? "border-red-500" : "border-slate-700"
              }`}
              placeholder='{"type": "object", "properties": {...}, "required": []}'
            />
            {errors.schema_json && (
              <p className="mt-1 text-xs text-red-400">{errors.schema_json}</p>
            )}
            <p className="mt-1 text-xs text-slate-500">
              Define the input parameters for your tool using JSON Schema format.
            </p>
          </div>

          <div className="flex gap-2 justify-end pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
              disabled={mutation.isPending}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={mutation.isPending || loadingTool}
            >
              {mutation.isPending
                ? toolData
                  ? "Updating..."
                  : "Creating..."
                : toolData
                ? "Update Tool"
                : "Create Tool"}
            </button>
          </div>
        </form>
      </div>

      {/* Environment Creation Dialog */}
      <EnvironmentDialog
        isOpen={showEnvironmentDialog}
        onClose={() => setShowEnvironmentDialog(false)}
        orgId={orgId}
        onSuccess={async () => {
          // Refetch environments and select the newly created one
          const { data: updatedEnvs } = await refetchEnvironments();
          const newEnvs = Array.isArray(updatedEnvs) ? updatedEnvs : updatedEnvs?.results || [];
          if (newEnvs.length > 0) {
            // Sort by created_at descending to get the newest first
            const sortedEnvs = [...newEnvs].sort((a, b) => {
              const aDate = new Date(a.created_at || 0).getTime();
              const bDate = new Date(b.created_at || 0).getTime();
              return bDate - aDate;
            });
            const newestEnv = sortedEnvs[0];
            setFormData((prev) => ({ 
              ...prev, 
              environment_id: newestEnv.id,
              connection_id: "", // Reset connection when environment changes
            }));
          }
        }}
      />

      {/* Connection Creation Dialog */}
      {showConnectionDialog && (
        <ConnectionDialog
          isOpen={showConnectionDialog}
          onClose={() => setShowConnectionDialog(false)}
          orgId={orgId}
          connection={formData.environment_id ? { environment_id: formData.environment_id } : undefined}
          onSuccess={async () => {
          // Refetch connections and select the newly created one
          const { data: updatedConns } = await refetchConnections();
          const newConns = Array.isArray(updatedConns) ? updatedConns : updatedConns?.results || [];
          if (newConns.length > 0 && formData.environment_id) {
            // Filter by current environment and sort by created_at descending
            const filteredConns = newConns.filter(
              (conn: any) => conn.environment_id === formData.environment_id || conn.environment?.id === formData.environment_id
            );
            if (filteredConns.length > 0) {
              const sortedConns = [...filteredConns].sort((a, b) => {
                const aDate = new Date(a.created_at || 0).getTime();
                const bDate = new Date(b.created_at || 0).getTime();
                return bDate - aDate;
              });
              const newestConn = sortedConns[0];
              setFormData((prev) => ({ ...prev, connection_id: newestConn.id }));
            }
          }
        }}
        />
      )}
    </div>
  );
}

