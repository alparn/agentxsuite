"use client";

import { useEffect, useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { mcpFabric, MCPTool, MCPFabricError } from "@/lib/mcpFabric";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { MCPToolRunDialog } from "./MCPToolRunDialog";
import { MCPToolCreateDialog } from "./MCPToolCreateDialog";
import { AlertCircle, RefreshCw, Plus, Edit } from "lucide-react";

export function MCPToolsView() {
  const { currentOrgId, currentEnvId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingTool, setEditingTool] = useState<MCPTool | null>(null);
  const [agentToken, setAgentToken] = useState<string | null>(null);

  // Fetch organizations
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  // Auto-select first organization if none selected
  useEffect(() => {
    if (!currentOrgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, currentOrgId, setCurrentOrg]);

  // Fetch environments for selected organization
  const { data: environmentsData } = useQuery({
    queryKey: ["environments", currentOrgId],
    queryFn: async () => {
      if (!currentOrgId) return [];
      const response = await api.get(`/orgs/${currentOrgId}/environments/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!currentOrgId,
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Auto-select first environment if none selected
  useEffect(() => {
    if (currentOrgId && !currentEnvId && environments && environments.length > 0) {
      setCurrentEnv(environments[0].id);
    }
  }, [currentOrgId, currentEnvId, environments, setCurrentEnv]);

  // Fetch agents to get a token
  const { data: agentsData } = useQuery({
    queryKey: ["agents", currentOrgId],
    queryFn: async () => {
      if (!currentOrgId) return [];
      const response = await api.get(`/orgs/${currentOrgId}/agents/`);
      if (Array.isArray(response.data)) {
        return response.data;
      } else if (response.data?.results && Array.isArray(response.data.results)) {
        return response.data.results;
      }
      return [];
    },
    enabled: !!currentOrgId,
  });

  const agents = Array.isArray(agentsData) ? agentsData : [];

  // Find first enabled agent with ServiceAccount (prefer AxCore agent)
  const defaultAgent = agents.find((a: any) => 
    a.enabled && 
    a.service_account && // Must have ServiceAccount
    (a.is_axcore || a.tags?.includes("axcore")) &&
    (a.environment?.id === currentEnvId || a.environment_id === currentEnvId)
  ) || agents.find((a: any) => 
    a.enabled && 
    a.service_account && // Must have ServiceAccount
    (a.environment?.id === currentEnvId || a.environment_id === currentEnvId)
  );

  // Generate agent token if we have an agent
  // IMPORTANT: Include currentEnvId in queryKey so token is regenerated when environment changes
  const { data: tokenData, error: tokenError, refetch: refetchToken } = useQuery({
    queryKey: ["agent-token", currentOrgId, currentEnvId, defaultAgent?.id],
    queryFn: async () => {
      if (!currentOrgId || !currentEnvId || !defaultAgent?.id) return null;
      try {
        const response = await api.post(`/orgs/${currentOrgId}/agents/${defaultAgent.id}/tokens/`, {
          ttl_minutes: 60,
          scopes: ["mcp:run", "mcp:tools", "mcp:manifest"],
        });
        
        // Extract token from response - handle different response formats
        // API returns: { token: "eyJ...", token_info: {...} }
        let token: string | null = null;
        
        if (!response.data) {
          console.error("Empty response.data from token generation");
          return null;
        }
        
        if (typeof response.data === 'string') {
          // Direct string response
          token = response.data;
        } else if (response.data?.token && typeof response.data.token === 'string') {
          // Standard format: { token: "..." }
          token = response.data.token;
        } else if (response.data && typeof response.data === 'object') {
          // Try to find token in any property (fallback)
          const tokenValue = Object.values(response.data).find(
            (v) => typeof v === 'string' && v.length > 50 // Tokens are usually long strings
          );
          if (tokenValue && typeof tokenValue === 'string') {
            token = tokenValue;
          }
        }
        
        // Validate token before returning
        if (!token || typeof token !== 'string' || token.trim().length === 0) {
          console.error("Invalid token format in response:", { 
            responseData: response.data,
            responseDataType: typeof response.data,
            responseDataKeys: typeof response.data === 'object' && response.data !== null 
              ? Object.keys(response.data) 
              : [],
            responseDataStringified: JSON.stringify(response.data).substring(0, 200)
          });
          return null;
        }
        
        return token;
      } catch (error: any) {
        console.error("Failed to generate agent token:", error);
        
        // Extract detailed error message from response
        let errorMessage = "Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.";
        
        if (error.response?.data) {
          const errorData = error.response.data;
          
          // Check for different error formats
          if (errorData.message) {
            errorMessage = errorData.message;
          } else if (errorData.error) {
            // Handle error code format: "agent_has_no_service_account"
            if (errorData.error === "agent_has_no_service_account") {
              errorMessage = "Agent must have a ServiceAccount configured to generate tokens. Please configure a ServiceAccount for this agent.";
            } else if (errorData.error === "validation_error") {
              errorMessage = errorData.message || "Validation error: " + JSON.stringify(errorData);
            } else {
              errorMessage = errorData.error;
            }
          } else if (typeof errorData === 'string') {
            errorMessage = errorData;
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          } else {
            // Try to extract from nested structure
            const errorStr = JSON.stringify(errorData);
            if (errorStr !== '{}') {
              errorMessage = `Error: ${errorStr}`;
            }
          }
        } else if (error.message) {
          errorMessage = error.message;
        }
        
        throw new Error(errorMessage);
      }
    },
    enabled: !!currentOrgId && !!currentEnvId && !!defaultAgent?.id,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes (reduced from 30 for better security)
    retry: 1, // Retry once on failure
  });

  // Synchronize tokenData with agentToken state
  useEffect(() => {
    // Ensure tokenData is a valid string before setting it
    if (tokenData && typeof tokenData === 'string' && tokenData.trim().length > 0) {
      setAgentToken(tokenData);
    } else if (tokenData === null) {
      // Explicitly reset token if tokenData is null
      setAgentToken(null);
    } else if (tokenData !== undefined) {
      // tokenData is not null/undefined but also not a valid string (could be an object)
      console.error("Invalid tokenData format:", { 
        tokenData, 
        type: typeof tokenData,
        isObject: typeof tokenData === 'object',
        keys: typeof tokenData === 'object' ? Object.keys(tokenData) : []
      });
      setAgentToken(null);
    }
    // If tokenData is undefined, don't change agentToken (still loading)
  }, [tokenData]);

  // Show error if token generation fails
  useEffect(() => {
    if (tokenError) {
      const errorMessage = tokenError instanceof Error 
        ? tokenError.message 
        : "Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.";
      setError(errorMessage);
      setLoading(false); // Stop loading state
      setTools([]); // Clear tools on token error
    } else if (tokenData === null && defaultAgent) {
      // Token generation was attempted but returned null (shouldn't happen, but handle it)
      setError("Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.");
      setLoading(false);
      setTools([]);
    }
  }, [tokenError, tokenData, defaultAgent]);

  // Reset token when environment changes
  useEffect(() => {
    setAgentToken(null);
    setError(null); // Clear errors when environment changes
  }, [currentEnvId]);

  const loadTools = useCallback(async () => {
    if (!currentOrgId || !currentEnvId) {
      setLoading(false);
      return;
    }

    // Get the current token value at call time (not closure value)
    // This prevents race conditions where token might be cleared while function is executing
    const currentToken = agentToken;
    
    // Don't try to load tools without a token - this should never happen due to useEffect guard
    // Check for null, undefined, or empty string
    if (!currentToken || typeof currentToken !== 'string' || currentToken.trim().length === 0) {
      console.warn("loadTools called without valid agentToken:", { 
        agentToken: currentToken, 
        type: typeof currentToken,
        length: currentToken?.length,
        currentOrgId,
        currentEnvId,
        timestamp: new Date().toISOString()
      });
      setError("Agent token is required to load tools. Please wait for token generation or ensure the agent has a ServiceAccount configured.");
      setLoading(false);
      setTools([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await mcpFabric.getTools(currentOrgId, currentEnvId, currentToken);
      // Handle both formats: {tools: [...]} or direct array
      const toolsArray = Array.isArray(response) 
        ? response 
        : (Array.isArray(response?.tools) ? response.tools : []);
      setTools(toolsArray);
    } catch (err: any) {
      setTools([]); // Reset tools on error
      
      // Provide user-friendly error messages
      if (err instanceof MCPFabricError) {
        // Check if it's the "token required" error - this should not happen if guard works
        if (err.message.includes("Agent token") || err.message.includes("token") || err.message.includes("missing")) {
          setError("Agent token is missing. Please ensure the agent has a ServiceAccount configured and token generation succeeded. If this error persists, try refreshing the page.");
        } else if (err.statusCode === 503 || err.statusCode === 504) {
          // Service unavailable or timeout - likely offline environment
          setError(err.message || "MCP Fabric server is not available. The environment may be offline or not started.");
        } else {
          setError(err.message);
        }
      } else if (err.response?.data) {
        // Extract error from response
        const errorData = err.response.data;
        const status = err.response.status;
        
        // Handle specific status codes
        if (status === 503 || status === 504) {
          setError("MCP Fabric server is not available. The environment may be offline or not started.");
        } else {
          const errorMsg = errorData.detail || errorData.message || errorData.error || "Failed to load tools";
          setError(errorMsg);
        }
      } else if (err.code === "ECONNREFUSED" || err.code === "ERR_NETWORK" || err.code === "ERR_CONNECTION_REFUSED") {
        setError("Cannot connect to MCP Fabric server. The server may be offline or the environment may not be started.");
      } else if (err.code === "ETIMEDOUT" || err.code === "ECONNABORTED" || err.code === "TIMEOUT") {
        setError("Request timeout: The MCP Fabric server did not respond. The environment may be offline or not started.");
      } else {
        setError(err.message || "Failed to load tools. Please check your connection and ensure the MCP Fabric server is running.");
      }
    } finally {
      setLoading(false);
    }
  }, [currentOrgId, currentEnvId, agentToken]);

  // Retry function that refetches token and then loads tools
  const handleRetry = useCallback(async () => {
    setError(null);
    setLoading(true);
    
    // If we have an agent but no token, refetch the token first
    if (defaultAgent && !agentToken) {
      try {
        const result = await refetchToken();
        const fetchedToken = result.data;
        
        if (fetchedToken && typeof fetchedToken === 'string' && fetchedToken.trim().length > 0) {
          // Token was successfully fetched, use it directly to load tools
          // Don't wait for state update - use the token directly
          try {
            const response = await mcpFabric.getTools(currentOrgId!, currentEnvId!, fetchedToken);
            const toolsArray = Array.isArray(response) 
              ? response 
              : (Array.isArray(response?.tools) ? response.tools : []);
            setTools(toolsArray);
            setLoading(false);
            setError(null);
          } catch (err: any) {
            setTools([]);
            if (err instanceof MCPFabricError) {
              setError(err.message);
            } else {
              setError("Failed to load tools. Please check your connection and ensure the MCP Fabric server is running.");
            }
            setLoading(false);
          }
        } else {
          setLoading(false);
          setError("Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.");
        }
      } catch (err) {
        setLoading(false);
        setError("Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.");
      }
    } else if (agentToken) {
      // We have a token, just retry loading tools
      loadTools();
    } else {
      // No agent available
      setLoading(false);
      setError("No agent available for this environment. Please create an agent with a ServiceAccount configured.");
    }
  }, [defaultAgent, agentToken, refetchToken, loadTools, currentOrgId, currentEnvId]);

  useEffect(() => {
    if (currentOrgId && currentEnvId) {
      // Check if we have an agent available
      if (!defaultAgent) {
        // No agent available for this environment
        setTools([]);
        setError("No agent available for this environment. Please create an agent with a ServiceAccount configured.");
        setLoading(false);
        return;
      }
      
      // If token generation failed, don't try to load tools
      if (tokenError) {
        // Error is already set by tokenError useEffect
        setLoading(false);
        return;
      }
      
      // Wait for token to be generated if agent exists but token is not ready yet
      if (!agentToken) {
        // Check if tokenData is still loading (undefined) vs failed (null)
        if (tokenData === undefined) {
          // Token is still being generated, show loading state
          setLoading(true);
          setError(null);
        } else if (tokenData === null) {
          // Token generation completed but returned null
          // This shouldn't happen, but handle it
          setLoading(false);
          // Error will be set by tokenError useEffect if there's an error
        }
        return;
      }
      
      // Token is available, load tools
      // Only call if we have a valid token string (not null, undefined, or empty)
      if (agentToken && typeof agentToken === 'string' && agentToken.trim().length > 0) {
        loadTools();
      } else {
        // Token is invalid (empty string, null, or undefined)
        console.warn("Cannot load tools: invalid agentToken", { 
          agentToken, 
          type: typeof agentToken,
          length: agentToken?.length 
        });
        setError("Agent token is invalid. Please wait for token generation to complete.");
        setLoading(false);
      }
    } else {
      setTools([]);
      setError(null);
      setLoading(false);
    }
  }, [currentOrgId, currentEnvId, agentToken, defaultAgent, tokenError, tokenData, loadTools]);

  if (organizations.length === 0) {
    return (
      <div className="p-4 text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
        No organizations available. Please create an organization first.
      </div>
    );
  }

  if (!currentOrgId || !currentEnvId) {
    if (environments.length === 0 && currentOrgId) {
      return (
        <div className="p-4 text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
          No environments available for this organization. Please create an environment first.
        </div>
      );
    }
    // Still loading or selecting
    return (
      <div className="p-4 text-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading...
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 text-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading tools...
      </div>
    );
  }

  // Only show environment selector if multiple options available
  const showEnvSelector = environments.length > 1;

  // Show error with environment selector so user can change environment
  if (error) {
    return (
      <div className="space-y-6">
        {/* Environment Selector - always show if available, even on error */}
        {(showEnvSelector || environments.length > 0) && (
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Environment
            </label>
            <select
              value={currentEnvId || ""}
              onChange={(e) => setCurrentEnv(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {!currentEnvId && (
                <option value="">Select an environment...</option>
              )}
              {environments.map((env: any) => (
                <option key={env.id} value={env.id}>
                  {env.name} ({env.type})
                </option>
              ))}
            </select>
          </div>
        )}
        
        {/* Error message */}
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <span className="font-semibold text-red-400">Error</span>
          </div>
          <p className="text-red-300 mb-3">{error}</p>
          <div className="flex gap-2">
            <button
              onClick={handleRetry}
              disabled={loading}
              className="px-4 py-2 bg-red-500/20 text-red-300 rounded hover:bg-red-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Retrying...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  Retry
                </>
              )}
            </button>
            {environments.length > 0 && (
              <button
                onClick={() => {
                  setError(null);
                  setCurrentEnv(null);
                }}
                className="px-4 py-2 bg-slate-700 text-slate-300 rounded hover:bg-slate-600 transition-colors flex items-center gap-2"
              >
                Change Environment
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Separate system tools from regular tools
  const systemTools = tools.filter((tool) => tool.name.startsWith("agentxsuite_"));
  const regularTools = tools.filter((tool) => !tool.name.startsWith("agentxsuite_"));

  return (
    <div className="space-y-6">
      {/* Environment Selector - show if multiple options OR if we want to allow changing */}
      {(showEnvSelector || environments.length > 0) && (
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Environment
          </label>
          <select
            value={currentEnvId || ""}
            onChange={(e) => setCurrentEnv(e.target.value)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {environments.map((env: any) => (
              <option key={env.id} value={env.id}>
                {env.name} ({env.type})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* System Tools Section */}
      {systemTools.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white">System Tools (AxCore)</h2>
              <p className="text-slate-400 text-sm mt-1">
                Tools für AxCore-Agents zur Verwaltung von AgentxSuite
              </p>
            </div>
            <button
              onClick={loadTools}
              className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
          <div className="grid gap-4">
            {systemTools.map((tool) => (
              <MCPToolCard
                key={tool.name}
                tool={tool}
                onEdit={(tool) => setEditingTool(tool)}
                isSystemTool={true}
                agentToken={agentToken}
                defaultAgent={defaultAgent}
                currentOrgId={currentOrgId}
              />
            ))}
          </div>
        </div>
      )}

      {/* Regular Tools Section */}
      <div className="space-y-4">
      <div className="flex items-center justify-between">
          <div>
        <h2 className="text-2xl font-bold text-white">MCP Tools</h2>
            <p className="text-slate-400 text-sm mt-1">
              Reguläre Tools aus MCP-Verbindungen
            </p>
          </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Tool
          </button>
          <button
            onClick={loadTools}
            className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>
      <div className="grid gap-4">
          {regularTools && regularTools.length > 0 ? (
            regularTools.map((tool) => (
            <MCPToolCard
              key={tool.name}
              tool={tool}
              onEdit={(tool) => setEditingTool(tool)}
                isSystemTool={false}
                agentToken={agentToken}
                defaultAgent={defaultAgent}
                currentOrgId={currentOrgId}
            />
          ))
        ) : (
          <div className="p-8 text-center text-slate-400 bg-slate-900 border border-slate-800 rounded-lg">
              No regular tools available for this environment
          </div>
        )}
        </div>
      </div>

      <MCPToolCreateDialog
        isOpen={showCreateDialog || !!editingTool}
        onClose={() => {
          setShowCreateDialog(false);
          setEditingTool(null);
        }}
        orgId={currentOrgId}
        envId={currentEnvId}
        tool={editingTool || undefined}
        onSuccess={() => {
          loadTools();
          setEditingTool(null);
        }}
      />
    </div>
  );
}

function MCPToolCard({
  tool,
  onEdit,
  isSystemTool = false,
  agentToken,
  defaultAgent,
  currentOrgId,
}: {
  tool: MCPTool;
  onEdit: (tool: MCPTool) => void;
  isSystemTool?: boolean;
  agentToken?: string | null;
  defaultAgent?: any;
  currentOrgId?: string | null;
}) {
  const { currentOrgId: storeOrgId, currentEnvId } = useAppStore();
  const orgId = currentOrgId || storeOrgId;
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showDialog, setShowDialog] = useState(false);

  const handleRun = async (args: Record<string, any>) => {
    if (!orgId || !currentEnvId) return;

    setRunning(true);
    setError(null);
    setResult(null);

    try {
      // Get agent token if not already available
      let token = agentToken;
      if (!token && defaultAgent && orgId) {
        try {
          const tokenResponse = await api.post(`/orgs/${orgId}/agents/${defaultAgent.id}/tokens/`, {
            ttl_minutes: 60,
            scopes: ["mcp:run", "mcp:tools", "mcp:manifest"],
          });
          token = tokenResponse.data?.token || null;
        } catch (error) {
          console.error("Failed to generate token for tool execution:", error);
        }
      }

      const response = await mcpFabric.runTool(
        orgId,
        currentEnvId,
        tool.name,
        args,
        token
      );

      // runTool now always returns MCPRunResponse (never throws)
      if (response.isError) {
        // Combine all error content items
        const errorText = response.content
          ?.map((item) => item.text || "")
          .filter(Boolean)
          .join("\n") || "Unknown error";
        setError(errorText);
      } else {
        // Combine all result content items
        const resultText = response.content
          ?.map((item) => item.text || "")
          .filter(Boolean)
          .join("\n") || "Success";
        setResult(resultText);
      }
    } catch (err: any) {
      // Fallback error handling (should not happen, but just in case)
      if (err instanceof MCPFabricError) {
        setError(err.message);
      } else {
        // Handle nested error objects
        let errorMsg = "Failed to execute tool";
        
        if (err.response?.data) {
          const data = err.response.data;
          
          // Check if detail is an object with error_description
          if (typeof data.detail === 'object' && data.detail !== null) {
            errorMsg = data.detail.error_description || data.detail.error || JSON.stringify(data.detail);
          } else if (typeof data.detail === 'string') {
            errorMsg = data.detail;
          } else if (data.message) {
            errorMsg = data.message;
          } else if (data.error) {
            errorMsg = data.error;
          }
        } else if (err.message) {
          errorMsg = err.message;
        }
        
        setError(errorMsg);
      }
    } finally {
      setRunning(false);
    }
  };

  return (
    <>
      <div className={`bg-slate-900 border rounded-lg p-4 ${
        isSystemTool 
          ? "border-purple-500/30 bg-gradient-to-r from-purple-500/5 to-pink-500/5" 
          : "border-slate-800"
      }`}>
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <div className="flex items-center gap-2">
            <h3 className="font-semibold text-lg text-white">{tool.name}</h3>
              {isSystemTool && (
                <span className="px-2 py-1 text-xs font-semibold bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-300 border border-purple-500/30 rounded">
                  System Tool
                </span>
              )}
            </div>
            {(tool.description || tool.inputSchema?.description) && (
              <p className="text-slate-400 text-sm mt-1">
                {tool.description || tool.inputSchema?.description || ""}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onEdit(tool)}
              className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-all flex items-center gap-2"
              title="Edit Tool"
            >
              <Edit className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowDialog(true)}
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={running}
            >
              {running ? "Running..." : "Run"}
            </button>
          </div>
        </div>
      </div>

      {showDialog && (
        <MCPToolRunDialog
          tool={tool}
          onRun={handleRun}
          onClose={() => {
            setShowDialog(false);
            setResult(null);
            setError(null);
          }}
          running={running}
          result={result}
          error={error}
        />
      )}
    </>
  );
}

