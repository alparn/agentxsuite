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

// MCP Fabric Resource types
export interface MCPResource {
  uri: string;
  name: string;
  description?: string;
  mimeType: string;
}

export interface MCPResourceContent {
  uri: string;
  mimeType: string;
  text?: string;
  blob?: string;
}

// MCP Fabric Prompt types
export interface MCPPrompt {
  name: string;
  description?: string;
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>;
}

export interface MCPPromptResponse {
  messages: Array<{
    role: "user" | "assistant" | "system";
    content: string | Array<{ type: string; text: string }>;
  }>;
}

