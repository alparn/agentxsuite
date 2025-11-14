/**
 * MCP Fabric API Client
 * 
 * Client für die Kommunikation mit dem MCP Fabric FastAPI-Service.
 */
import axios from "axios";

const MCP_FABRIC_URL =
  process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090";

// MCP Types
export interface MCPManifest {
  protocol_version: string;
  name: string;
  version: string;
  capabilities: Record<string, any>;
}

export interface MCPTool {
  name: string;
  description?: string;
  inputSchema: Record<string, any>;
}

export interface MCPToolsResponse {
  tools: MCPTool[];
}

export interface MCPRunRequest {
  name: string;
  arguments: Record<string, any>;
}

export interface MCPRunContent {
  type: string;
  text: string;
}

export interface MCPRunResponse {
  content: MCPRunContent[];
  isError: boolean;
}

// Resource types
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

// Prompt types
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

// Error Handling
export class MCPFabricError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code?: string
  ) {
    super(message);
    this.name = "MCPFabricError";
  }
}

export function handleMCPError(error: any): string {
  if (error.response) {
    const status = error.response.status;
    const detail = error.response.data?.detail || "Unknown error";

    switch (status) {
      case 401:
        return "Authentication required. Please login again.";
      case 403:
        return `Access denied: ${detail}`;
      case 404:
        return `Not found: ${detail}`;
      case 408:
        return `Timeout: ${detail}`;
      case 429:
        return "Rate limit exceeded. Please try again later.";
      default:
        return `Error ${status}: ${detail}`;
    }
  }
  return "Network error. Please check your connection.";
}

// API Client
class MCPFabricClient {
  private getAuthToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("auth_token");
  }

  private getHeaders(): Record<string, string> {
    const token = this.getAuthToken();
    return {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    };
  }

  async getManifest(orgId: string, envId: string): Promise<MCPManifest> {
    try {
      const response = await axios.get<MCPManifest>(
        `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/manifest.json`,
        { headers: this.getHeaders() }
      );
      return response.data;
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }

  async getTools(orgId: string, envId: string): Promise<MCPToolsResponse> {
    try {
      const response = await axios.get<any>(
        `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/tools`,
        { headers: this.getHeaders() }
      );
      // Backend returns direct array, but we normalize to MCPToolsResponse format
      const data = response.data;
      if (Array.isArray(data)) {
        return { tools: data };
      }
      // If it's already in the expected format
      return Array.isArray(data?.tools) ? data : { tools: [] };
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }

  async runTool(
    orgId: string,
    envId: string,
    toolName: string,
    args: Record<string, any>
  ): Promise<MCPRunResponse> {
    try {
      const response = await axios.post<any>(
        `${MCP_FABRIC_URL}/mcp/${orgId}/${envId}/.well-known/mcp/run`,
        { name: toolName, arguments: args },
        { headers: this.getHeaders() }
      );
      
      // Backend returns: {status: "success"|"error", output: {...}, run_id: "..."}
      // Frontend expects: {content: [{type: string, text: string}], isError: boolean}
      const data = response.data;
      
      // Check if it's already in MCP format
      if (data.content && Array.isArray(data.content)) {
        return data as MCPRunResponse;
      }
      
      // Convert backend format to MCP format
      if (data.status === "success") {
        const output = data.output || {};
        const outputText = typeof output === "string" 
          ? output 
          : JSON.stringify(output, null, 2);
        
        return {
          content: [
            {
              type: "text",
              text: outputText,
            },
          ],
          isError: false,
        };
      } else {
        // Error case
        const errorText = data.error || data.message || "Execution failed";
        return {
          content: [
            {
              type: "text",
              text: errorText,
            },
          ],
          isError: true,
        };
      }
    } catch (error: any) {
      // Handle HTTP errors
      const errorMessage = error.response?.data?.detail || handleMCPError(error);
      return {
        content: [
          {
            type: "text",
            text: errorMessage,
          },
        ],
        isError: true,
      };
    }
  }

  async getResources(orgId: string, envId: string): Promise<MCPResource[]> {
    try {
      const response = await axios.get<MCPResource[]>(
        `${MCP_FABRIC_URL}/api/v1/mcp/${orgId}/${envId}/.well-known/mcp/resources`,
        { headers: this.getHeaders() }
      );
      return Array.isArray(response.data) ? response.data : [];
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }

  async getResource(
    orgId: string,
    envId: string,
    resourceName: string
  ): Promise<MCPResourceContent> {
    try {
      const response = await axios.get<MCPResourceContent>(
        `${MCP_FABRIC_URL}/api/v1/mcp/${orgId}/${envId}/.well-known/mcp/resources/${resourceName}`,
        { headers: this.getHeaders() }
      );
      return response.data;
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }

  async getPrompts(orgId: string, envId: string): Promise<MCPPrompt[]> {
    try {
      const response = await axios.get<MCPPrompt[]>(
        `${MCP_FABRIC_URL}/api/v1/mcp/${orgId}/${envId}/.well-known/mcp/prompts`,
        { headers: this.getHeaders() }
      );
      return Array.isArray(response.data) ? response.data : [];
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }

  async invokePrompt(
    orgId: string,
    envId: string,
    promptName: string,
    input: Record<string, any>
  ): Promise<MCPPromptResponse> {
    try {
      const response = await axios.post<MCPPromptResponse>(
        `${MCP_FABRIC_URL}/api/v1/mcp/${orgId}/${envId}/.well-known/mcp/prompts/${promptName}/invoke`,
        { arguments: input },
        { headers: this.getHeaders() }
      );
      return response.data;
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        error.response?.status || 500
      );
    }
  }
}

export const mcpFabric = new MCPFabricClient();

