import axios from "axios";
import type { Resource, Prompt, Policy, PolicyRule, PolicyBinding, PolicyEvaluateRequest, Agent, IssuedToken, TokenGenerateRequest, TokenGenerateResponse, ServiceAccount, RunList, RunDetail, MCPServerRegistration, ClaudeDesktopConfig, CostSummary, AgentCostSummary, EnvironmentCostSummary, ModelCostSummary, ToolCostSummary } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("auth_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Resources API
export const resourcesApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/resources/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/resources/${id}/`),
  create: (orgId: string, data: Partial<Resource>) =>
    api.post(`/orgs/${orgId}/resources/`, data),
  update: (orgId: string, id: string, data: Partial<Resource>) =>
    api.put(`/orgs/${orgId}/resources/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/resources/${id}/`),
};

// Prompts API
export const promptsApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/prompts/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/prompts/${id}/`),
  create: (orgId: string, data: Partial<Prompt>) =>
    api.post(`/orgs/${orgId}/prompts/`, data),
  update: (orgId: string, id: string, data: Partial<Prompt>) =>
    api.put(`/orgs/${orgId}/prompts/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/prompts/${id}/`),
};

// Policies API
export const policiesApi = {
  list: (orgId: string, params?: { name?: string; is_active?: boolean }) =>
    api.get(`/orgs/${orgId}/policies/`, { params }),
  get: (orgId: string, id: string) =>
    api.get(`/orgs/${orgId}/policies/${id}/`),
  create: (orgId: string, data: Partial<Policy>) =>
    api.post(`/orgs/${orgId}/policies/`, data),
  update: (orgId: string, id: string, data: Partial<Policy>) =>
    api.put(`/orgs/${orgId}/policies/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/policies/${id}/`),
};

// Policy Rules API
export const policyRulesApi = {
  list: (params?: { policy_id?: string }) =>
    api.get(`/policy-rules/`, { params }),
  get: (id: string) => api.get(`/policy-rules/${id}/`),
  create: (data: Partial<PolicyRule>) =>
    api.post(`/policy-rules/`, data),
  update: (id: string, data: Partial<PolicyRule>) =>
    api.put(`/policy-rules/${id}/`, data),
  delete: (id: string) =>
    api.delete(`/policy-rules/${id}/`),
};

// Policy Bindings API
export const policyBindingsApi = {
  list: (params?: { scope_type?: string; scope_id?: string; policy_id?: string }) =>
    api.get(`/policy-bindings/`, { params }),
  get: (id: string) => api.get(`/policy-bindings/${id}/`),
  create: (data: Partial<PolicyBinding>) =>
    api.post(`/policy-bindings/`, data),
  update: (id: string, data: Partial<PolicyBinding>) =>
    api.put(`/policy-bindings/${id}/`, data),
  delete: (id: string) =>
    api.delete(`/policy-bindings/${id}/`),
};

// Policy Evaluate API
export const policyEvaluateApi = {
  evaluate: (data: PolicyEvaluateRequest, explain?: boolean) =>
    api.post(`/policies/evaluate/`, data, { params: explain ? { explain: 'true' } : {} }),
};

// Audit API (erweitert)
export const auditApi = {
  list: (orgId: string, params?: {
    subject?: string;
    action?: string;
    target?: string;
    decision?: 'allow' | 'deny';
    ts_from?: string;
    ts_to?: string;
  }) =>
    api.get(`/orgs/${orgId}/audit/`, { params }),
};

// Agents API
export const agentsApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/agents/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/agents/${id}/`),
  create: (orgId: string, data: Partial<Agent>) =>
    api.post(`/orgs/${orgId}/agents/`, data),
  update: (orgId: string, id: string, data: Partial<Agent>) =>
    api.put(`/orgs/${orgId}/agents/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/agents/${id}/`),
};

// Token API
export const tokensApi = {
  // Generate token for agent
  generate: (orgId: string, agentId: string, data?: TokenGenerateRequest) =>
    api.post<TokenGenerateResponse>(`/orgs/${orgId}/agents/${agentId}/tokens/`, data || {}),
  // List tokens for agent
  list: (orgId: string, agentId: string) =>
    api.get<IssuedToken[]>(`/orgs/${orgId}/agents/${agentId}/tokens/`),
  // Revoke token
  revoke: (orgId: string, agentId: string, jti: string) =>
    api.post<IssuedToken>(`/orgs/${orgId}/agents/${agentId}/tokens/${jti}/revoke/`),
  // Delete token
  delete: (orgId: string, agentId: string, jti: string) =>
    api.delete(`/orgs/${orgId}/agents/${agentId}/tokens/${jti}/`),
};

// ServiceAccount API
export const serviceAccountsApi = {
  list: (orgId: string) => api.get<ServiceAccount[]>(`/orgs/${orgId}/service-accounts/`),
  get: (orgId: string, id: string) => api.get<ServiceAccount>(`/orgs/${orgId}/service-accounts/${id}/`),
  create: (orgId: string, data: Partial<ServiceAccount>) =>
    api.post<ServiceAccount>(`/orgs/${orgId}/service-accounts/`, data),
  update: (orgId: string, id: string, data: Partial<ServiceAccount>) =>
    api.put<ServiceAccount>(`/orgs/${orgId}/service-accounts/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/service-accounts/${id}/`),
};

// Runs API
export const runsApi = {
  list: (orgId: string, params?: { status?: string; agent?: string; tool?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append("status", params.status);
    if (params?.agent) queryParams.append("agent", params.agent);
    if (params?.tool) queryParams.append("tool", params.tool);
    const queryString = queryParams.toString();
    return api.get<{ count: number; next: string | null; previous: string | null; results: RunList[] }>(
      `/orgs/${orgId}/runs/${queryString ? `?${queryString}` : ""}`
    );
  },
  get: (orgId: string, id: string) => api.get<RunDetail>(`/orgs/${orgId}/runs/${id}/`),
  steps: (orgId: string, id: string) => api.get(`/orgs/${orgId}/runs/${id}/steps/`),
  execute: (
    orgId: string,
    data: {
      tool: string; // Tool UUID or name
      agent?: string; // Optional agent UUID
      input: Record<string, any>; // Input data
      environment?: string; // Optional environment UUID
      timeout_seconds?: number; // Optional timeout
    }
  ) => api.post(`/orgs/${orgId}/runs/execute/`, data),
};

// Canvas API
export const canvasApi = {
  getDefault: (orgId: string) =>
    api.get(`/orgs/${orgId}/canvas/default/`),
  saveDefault: (orgId: string, state: any) =>
    api.post(`/orgs/${orgId}/canvas/default/`, { state_json: state }),
  list: (orgId: string) =>
    api.get(`/orgs/${orgId}/canvas/`),
  get: (orgId: string, id: string) =>
    api.get(`/orgs/${orgId}/canvas/${id}/`),
  create: (orgId: string, data: any) =>
    api.post(`/orgs/${orgId}/canvas/`, data),
  update: (orgId: string, id: string, data: any) =>
    api.put(`/orgs/${orgId}/canvas/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/canvas/${id}/`),
};

// MCP Server Registration API
export const mcpServersApi = {
  list: (orgId: string) => api.get<MCPServerRegistration[]>(`/orgs/${orgId}/mcp-servers/`),
  get: (orgId: string, id: string) => api.get<MCPServerRegistration>(`/orgs/${orgId}/mcp-servers/${id}/`),
  create: (orgId: string, data: Partial<MCPServerRegistration>) =>
    api.post<MCPServerRegistration>(`/orgs/${orgId}/mcp-servers/`, data),
  update: (orgId: string, id: string, data: Partial<MCPServerRegistration>) =>
    api.put<MCPServerRegistration>(`/orgs/${orgId}/mcp-servers/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/mcp-servers/${id}/`),
  // Health check for a specific server
  healthCheck: (orgId: string, id: string) =>
    api.post<{
      id: string;
      slug: string;
      health_status: string;
      health_message: string;
      last_health_check: string | null;
    }>(`/orgs/${orgId}/mcp-servers/${id}/health_check/`),
  // Get Claude Desktop configuration
  getClaudeConfig: (orgId: string, params?: { env_id?: string; token?: string }) =>
    api.get<ClaudeDesktopConfig>(`/orgs/${orgId}/mcp-servers/claude_config/`, { params }),
  // Download Claude Desktop configuration as JSON file
  downloadConfig: async (orgId: string, params?: { env_id?: string; token?: string }) => {
    const response = await api.get(
      `/orgs/${orgId}/mcp-servers/download_config/`,
      {
        params,
        responseType: 'blob'
      }
    );
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'claude_desktop_config.json');
    document.body.appendChild(link);
    link.click();
    link.remove();
  },
};

// MCP Hub API (GitHub-discovered servers)
export interface MCPHubServer {
  id: string;
  github_id: number;
  full_name: string;
  name: string;
  description: string;
  html_url: string;
  stargazers_count: number;
  forks_count: number;
  language: string;
  topics: string[];
  owner_login: string;
  owner_avatar_url: string;
  updated_at_github: string;
  last_synced_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const mcpHubApi = {
  list: (params?: {
    language?: string;
    min_stars?: number;
    max_stars?: number;
    topic?: string[];
    search?: string;
    sort?: "stargazers_count" | "forks_count" | "updated_at_github" | "name";
  }) => {
    const queryParams = new URLSearchParams();
    if (params?.language) queryParams.append("language", params.language);
    if (params?.min_stars) queryParams.append("min_stars", params.min_stars.toString());
    if (params?.max_stars) queryParams.append("max_stars", params.max_stars.toString());
    if (params?.topic) {
      params.topic.forEach((t) => queryParams.append("topic", t));
    }
    if (params?.search) queryParams.append("search", params.search);
    if (params?.sort) queryParams.append("sort", params.sort);
    
    const queryString = queryParams.toString();
    // DRF returns paginated response: { count, next, previous, results: [...] }
    return api.get<{ count: number; next: string | null; previous: string | null; results: MCPHubServer[] } | MCPHubServer[]>(
      `/mcp-hub/hub-servers/${queryString ? `?${queryString}` : ""}`
    );
  },
};

// Auth API
export const authApi = {
  me: () => api.get("/auth/me/"),
  updateMe: (data: { first_name?: string; last_name?: string; email?: string }) =>
    api.put("/auth/me/", data),
  patchMe: (data: { first_name?: string; last_name?: string; email?: string }) =>
    api.patch("/auth/me/", data),
  myOrganizations: () => api.get("/auth/me/orgs/"),
  addOrganization: (data: { organization_id?: string; organization_name?: string }) =>
    api.post("/auth/me/orgs/", data),
};

// Cost Analytics API
export const costsApi = {
  // Get organization total cost summary
  summary: (orgId: string, params?: { environment?: string; days?: number }) =>
    api.get<CostSummary>(`/orgs/${orgId}/costs/`, { params }),
  
  // Get cost breakdown by agent
  byAgent: (orgId: string, params?: { environment?: string; days?: number }) =>
    api.get<AgentCostSummary[]>(`/orgs/${orgId}/costs/by_agent/`, { params }),
  
  // Get cost breakdown by environment
  byEnvironment: (orgId: string, params?: { days?: number }) =>
    api.get<EnvironmentCostSummary[]>(`/orgs/${orgId}/costs/by_environment/`, { params }),
  
  // Get cost breakdown by model
  byModel: (orgId: string, params?: { environment?: string; days?: number }) =>
    api.get<ModelCostSummary[]>(`/orgs/${orgId}/costs/by_model/`, { params }),
  
  // Get cost breakdown by tool
  byTool: (orgId: string, params?: { environment?: string; days?: number }) =>
    api.get<ToolCostSummary[]>(`/orgs/${orgId}/costs/by_tool/`, { params }),
};

export default api;
