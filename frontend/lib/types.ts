/**
 * TypeScript type definitions for AgentxSuite frontend.
 */

// Organization and Environment types (from existing codebase)
export interface Organization {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

// Cost Analytics types
export interface CostSummary {
  organization_id: string;
  environment_id?: string;
  period_days: number;
  start_date: string;
  end_date: string;
  total_cost: number;
  total_cost_input: number;
  total_cost_output: number;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  currency: string;
}

export interface AgentCostSummary {
  agent_id: string;
  agent_name: string;
  total_cost: number;
  total_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface EnvironmentCostSummary {
  environment_id: string;
  environment_name: string;
  total_cost: number;
  total_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface ModelCostSummary {
  model_name: string;
  total_cost: number;
  total_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface ToolCostSummary {
  tool_id: string;
  tool_name: string;
  total_cost: number;
  total_runs: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
}

export interface Environment {
  id: string;
  name: string;
  type: string;
  organization: Organization;
  created_at: string;
  updated_at: string;
}

// Resource types
export interface Resource {
  id: string;
  organization: Organization;
  environment: Environment;
  environment_id: string;
  name: string;
  type: "static" | "http" | "sql" | "s3" | "file";
  config_json: Record<string, any>;
  mime_type: string;
  schema_json?: Record<string, any> | null;
  secret_ref?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

// Prompt types
export interface Prompt {
  id: string;
  organization: Organization;
  environment: Environment;
  environment_id: string;
  name: string;
  description: string;
  input_schema: Record<string, any>;
  template_system: string;
  template_user: string;
  uses_resources: string[];
  output_hints?: Record<string, any> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

// MCP Server Registration types
export interface MCPServerRegistration {
  id: string;
  organization: Organization;
  environment: Environment;
  environment_id: string;
  name: string;
  slug: string;
  description: string;
  server_type: "stdio" | "http" | "ws";
  endpoint: string;
  command: string;
  args: string[];
  env_vars: Record<string, string>;
  auth_method: "none" | "bearer" | "basic" | "api_key" | "oauth2";
  secret_ref: string;
  enabled: boolean;
  last_health_check: string | null;
  health_status: string;
  health_message: string;
  tags: string[];
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ClaudeDesktopConfig {
  mcpServers: Record<string, {
    command: string;
    args: string[];
    env?: Record<string, string>;
  }>;
}

// MCP Fabric Resource types
export interface MCPResource {
  name: string;
  type?: string;
  mimeType: string; // MCP standard: CamelCase
  schema_json?: Record<string, any> | null;
  uri?: string; // Optional: URI if provided by backend
  description?: string;
}

export interface MCPResourceContent {
  name: string;
  mimeType: string; // MCP standard: CamelCase
  content: string | Record<string, any>;
  uri?: string; // Optional: URI if provided by backend
  text?: string; // Legacy/alternative format
  blob?: string; // Legacy/alternative format
}

// MCP Fabric Prompt types
export interface MCPPrompt {
  name: string;
  description?: string;
  inputSchema?: Record<string, any>; // MCP standard: JSON Schema for prompt inputs
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>; // Legacy/alternative format
}

export interface MCPPromptResponse {
  messages: Array<{
    role: "user" | "assistant" | "system";
    content: string | Array<{ type: string; text: string }>;
  }>;
}

// Policy types
export interface Policy {
  id: string;
  organization: Organization;
  environment_id?: string | null;
  name: string;
  version: number;
  is_active: boolean;
  enabled: boolean; // Legacy, synced with is_active
  rules?: PolicyRule[];
  rules_json?: Record<string, any>; // Legacy
  description?: string; // Legacy, from rules_json
  created_at: string;
  updated_at: string;
}

export interface PolicyRule {
  id: number;
  policy_id: string;
  policy_name?: string;
  action: 'tool.invoke' | 'agent.invoke' | 'resource.read' | 'resource.write' | string;
  target: string; // e.g., "tool:pdf/*", "agent:ocr"
  effect: 'allow' | 'deny';
  conditions: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PolicyBinding {
  id: number;
  policy_id: string;
  policy_name?: string;
  scope_type: 'org' | 'env' | 'agent' | 'tool' | 'role' | 'user' | 'resource_ns';
  scope_id: string;
  priority: number;
  created_at: string;
  updated_at: string;
}

export interface PolicyEvaluateRequest {
  action: string;
  target: string;
  subject?: string;
  organization_id?: string;
  environment_id?: string;
  agent_id?: string;
  tool_id?: string;
  resource_ns?: string;
  context?: Record<string, any>;
  explain?: boolean;
}

export interface PolicyEvaluateResponse {
  decision: 'allow' | 'deny';
  rule_id?: number;
  matched_rules?: Array<{
    rule_id: number;
    policy_id: string;
    policy_name: string;
    effect: 'allow' | 'deny';
    target: string;
    scope_type: string;
    priority: number;
  }>;
  bindings_order?: Array<{
    policy_id: string;
    policy_name: string;
    scope_type: string;
    scope_id: string;
    priority: number;
  }>;
}

export interface AuditEvent {
  id: string;
  ts: string;
  created_at: string;
  updated_at: string;
  subject?: string;
  action?: string;
  action_field?: string;
  target?: string;
  decision?: 'allow' | 'deny';
  rule_id?: number;
  context?: Record<string, any>;
  actor?: string;
  object_type?: string;
  details?: string;
  event_type: string;
  event_data: Record<string, any>;
  organization: Organization;
}

// Agent types
export interface Agent {
  id: string;
  name: string;
  slug?: string;
  version: string;
  enabled: boolean;
  mode: "runner" | "caller";
  capabilities: string[];
  tags: string[];
  organization: Organization;
  environment: Environment;
  connection?: any;
  service_account?: string;
  default_max_depth: number;
  default_budget_cents: number;
  default_ttl_seconds: number;
  inbound_auth_method: "bearer" | "mtls" | "none";
  created_at: string;
  updated_at: string;
}

// Tool types
export interface Tool {
  id: string;
  organization: Organization;
  environment: Environment;
  connection: Connection;
  name: string;
  version: string;
  schema_json: Record<string, any>;
  enabled: boolean;
  sync_status: "synced" | "failed" | "stale";
  synced_at?: string | null;
  created_at: string;
  updated_at: string;
}

// Token types
export interface IssuedToken {
  id: string;
  jti: string;
  agent: string;
  agent_name: string;
  expires_at: string;
  revoked_at?: string | null;
  revoked_by?: string | null;
  scopes: string[];
  metadata: Record<string, any>;
  created_at: string;
  is_expired: boolean;
  is_revoked: boolean;
}

export interface TokenGenerateRequest {
  ttl_minutes?: number;
  scopes?: string[];
  metadata?: Record<string, any>;
}

export interface TokenGenerateResponse {
  token: string;
  token_info: IssuedToken;
}

// ServiceAccount types
export interface ServiceAccount {
  id: string;
  name: string;
  organization: Organization;
  organization_name: string;
  environment?: Environment | null;
  environment_name?: string | null;
  subject: string;
  issuer: string;
  audience: string;
  scope_allowlist: string[];
  credential_ref?: string | null;
  expires_at?: string | null;
  rotated_at?: string | null;
  enabled: boolean;
  agent_id?: string | null;
  agent_name?: string | null;
  created_at: string;
  updated_at: string;
}

// Run types (for list view - optimized)
export interface RunList {
  id: string;
  organization_id: string;
  organization_name: string;
  environment_id: string;
  environment_name: string;
  agent_id: string;
  agent_name: string;
  tool_id: string;
  tool_name: string;
  status: "pending" | "running" | "succeeded" | "failed";
  started_at?: string | null;
  ended_at?: string | null;
  created_at: string;
  updated_at: string;
}

// Run types (for detail view - full nested objects)
export interface RunDetail {
  id: string;
  organization: Organization;
  environment: Environment;
  agent: Agent;
  tool: {
    id: string;
    organization: Organization;
    environment: Environment;
    connection?: Connection;
    name: string;
    version: string;
    schema_json: Record<string, any>;
    enabled: boolean;
    sync_status: string;
    synced_at?: string | null;
    created_at: string;
    updated_at: string;
  };
  status: "pending" | "running" | "succeeded" | "failed";
  started_at?: string | null;
  ended_at?: string | null;
  input_json: Record<string, any>;
  output_json?: Record<string, any> | null;
  error_text?: string;
  created_at: string;
  updated_at: string;
}

// Connection types
export interface Connection {
  id: string;
  organization: Organization;
  environment: Environment;
  name: string;
  endpoint: string;
  auth_method: "none" | "bearer" | "basic";
  secret_ref?: string | null;
  status: "unknown" | "ok" | "fail";
  last_seen_at?: string | null;
  created_at: string;
  updated_at: string;
}

