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
  // Handle null/undefined errors
  if (!error) {
    return "Unknown error occurred";
  }
  
  // Handle string errors
  if (typeof error === 'string') {
    return error;
  }
  
  // Handle error objects
  if (error.response) {
    const status = error.response.status;
    const detail = error.response.data?.detail || 
                   error.response.data?.error_description || 
                   error.response.data?.error ||
                   error.response.data?.message ||
                   "Unknown error";

    switch (status) {
      case 401:
        return `Authentication required: ${detail}`;
      case 403:
        return `Access denied: ${detail}`;
      case 404:
        return `Not found: ${detail}`;
      case 408:
        return `Timeout: ${detail}`;
      case 429:
        return "Rate limit exceeded. Please try again later.";
      case 503:
        return "MCP Fabric server is not available. Please ensure the server is running on port 8090.";
      default:
        return `Error ${status}: ${detail}`;
    }
  }
  
  // Network errors (no response received)
  if (error.request) {
    // Request was made but no response received
    if (error.code === "ECONNREFUSED") {
      return "MCP Fabric server is not reachable. The server may be offline or not running on port 8090. Please check if the MCP Fabric service is started.";
    }
    if (error.code === "ERR_NETWORK" || error.message?.includes("Network Error")) {
      return "Network error: Cannot connect to MCP Fabric server. Please check your connection and ensure the server is running.";
    }
    if (error.code === "ETIMEDOUT" || error.code === "ECONNABORTED" || error.code === "TIMEOUT") {
      return "Request timeout: The MCP Fabric server did not respond in time. The server may be offline, overloaded, or the environment may not be started.";
    }
    if (error.code === "ERR_CONNECTION_REFUSED") {
      return "Connection refused: MCP Fabric server is not accepting connections. Please ensure the server is running and the environment is started.";
    }
    if (error.code === "ERR_CONNECTION_RESET") {
      return "Connection reset: The connection to MCP Fabric server was closed. Please try again or check if the server is running.";
    }
    return `Network error: ${error.message || "No response from server. The MCP Fabric server may be offline."}`;
  }
  
  // Request setup errors
  if (error.message) {
    return `Request error: ${error.message}`;
  }
  
  // Fallback for unknown error types
  if (typeof error === 'object') {
    try {
      const errorStr = JSON.stringify(error);
      return `Unknown error: ${errorStr}`;
    } catch {
      return "Unknown error occurred";
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

  private getHeaders(agentToken?: string | null): Record<string, string> {
    // MCP Fabric API requires agent JWT token (not user token)
    // User tokens are Django tokens without JWT claims (sub/iss) needed for agent resolution
    if (!agentToken || typeof agentToken !== 'string' || agentToken.trim().length === 0) {
      // This should not happen if the calling code properly checks for token before calling
      // Log detailed info for debugging
      console.error("getHeaders called without valid token:", {
        agentToken,
        type: typeof agentToken,
        length: agentToken?.length,
        isNull: agentToken === null,
        isUndefined: agentToken === undefined,
        isEmpty: agentToken === '',
      });
      throw new MCPFabricError(
        "Agent token is required but not available. Please ensure an agent with a ServiceAccount is selected and wait for token generation to complete.",
        400
      );
    }
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${agentToken}`,
    };
  }

  async getManifest(orgId: string, envId: string, agentToken?: string | null): Promise<MCPManifest> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.get<MCPManifest>(
        `${MCP_FABRIC_URL}/.well-known/mcp/manifest.json`,
        { 
          headers: this.getHeaders(agentToken),
          timeout: 10000, // 10 second timeout
        }
      );
      return response.data;
    } catch (error: any) {
      const statusCode = this._getStatusCodeFromError(error);
      throw new MCPFabricError(
        handleMCPError(error),
        statusCode
      );
    }
  }
  
  private _getStatusCodeFromError(error: any): number {
    if (error?.response?.status) {
      return error.response.status;
    } else if (error?.code === "ECONNREFUSED" || error?.code === "ERR_CONNECTION_REFUSED") {
      return 503; // Service Unavailable
    } else if (error?.code === "ETIMEDOUT" || error?.code === "ECONNABORTED" || error?.code === "TIMEOUT") {
      return 504; // Gateway Timeout
    } else if (error?.code === "ERR_NETWORK" || error?.code === "ERR_CONNECTION_RESET") {
      return 503; // Service Unavailable
    }
    return 500; // Internal Server Error
  }

  async getTools(orgId: string, envId: string, agentToken?: string | null): Promise<MCPToolsResponse> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.get<any>(
        `${MCP_FABRIC_URL}/.well-known/mcp/tools`,
        { 
          headers: this.getHeaders(agentToken),
          timeout: 10000, // 10 second timeout
        }
      );
      // Backend returns direct array, but we normalize to MCPToolsResponse format
      const data = response.data;
      if (Array.isArray(data)) {
        return { tools: data };
      }
      // If it's already in the expected format
      return Array.isArray(data?.tools) ? data : { tools: [] };
    } catch (error: any) {
      // Log detailed error for debugging - safely extract properties
      const errorDetails: Record<string, any> = {
        url: `${MCP_FABRIC_URL}/.well-known/mcp/tools`,
      };
      
      if (error) {
        if (error.message !== undefined) errorDetails.message = error.message;
        if (error.code !== undefined) errorDetails.code = error.code;
        if (error.name !== undefined) errorDetails.name = error.name;
        
        if (error.response) {
          errorDetails.status = error.response.status;
          errorDetails.statusText = error.response.statusText;
          if (error.response.data !== undefined) {
            errorDetails.responseData = error.response.data;
          }
        }
        
        if (error.request !== undefined) {
          errorDetails.hasRequest = true;
        }
      }
      
      // Only log if we have meaningful data, otherwise log the raw error
      if (Object.keys(errorDetails).length > 1) {
        console.error("MCP Fabric getTools error:", errorDetails);
      } else {
        console.error("MCP Fabric getTools error (unexpected format):", error);
      }
      
      throw new MCPFabricError(
        handleMCPError(error),
        this._getStatusCodeFromError(error)
      );
    }
  }

  async runTool(
    orgId: string,
    envId: string,
    toolName: string,
    args: Record<string, any>,
    agentToken?: string | null
  ): Promise<MCPRunResponse> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.post<any>(
        `${MCP_FABRIC_URL}/.well-known/mcp/run`,
        { name: toolName, arguments: args },
        { headers: this.getHeaders(agentToken) }
      );
      
      // Backend returns different formats:
      // 1. MCP format: {content: [...], isError: boolean}
      // 2. Tool Registry format: {status: "success", output: {...}, run_id: "..."}
      // 3. System Tools format: {status: "success", agents: [...], ...} (data directly in root)
      // Frontend expects: {content: [{type: string, text: string}], isError: boolean}
      const data = response.data;
      
      // Check if it's already in MCP format
      if (data.content && Array.isArray(data.content)) {
        return data as MCPRunResponse;
      }
      
      // Convert backend format to MCP format
      if (data.status === "success") {
        // Check if there's an output field (Tool Registry format)
        if (data.output !== undefined) {
          const output = data.output;
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
          // System Tools format: data is directly in root (e.g., {status: "success", agents: [...]})
          // Extract all fields except status, run_id, and other metadata
          const resultData: Record<string, any> = {};
          for (const [key, value] of Object.entries(data)) {
            if (key !== "status" && key !== "run_id" && key !== "error" && key !== "error_description") {
              resultData[key] = value;
            }
          }
          
          // If resultData is empty, use the whole data object (minus status)
          const outputText = Object.keys(resultData).length > 0
            ? JSON.stringify(resultData, null, 2)
            : JSON.stringify(data, null, 2);
          
          return {
            content: [
              {
                type: "text",
                text: outputText,
              },
            ],
            isError: false,
          };
        }
      } else {
        // Error case
        const errorText = data.error || data.error_description || data.message || "Execution failed";
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

  async getResources(orgId: string, envId: string, agentToken?: string | null): Promise<MCPResource[]> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.get<MCPResource[]>(
        `${MCP_FABRIC_URL}/.well-known/mcp/resources`,
        { 
          headers: this.getHeaders(agentToken),
          timeout: 10000, // 10 second timeout
        }
      );
      return Array.isArray(response.data) ? response.data : [];
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        this._getStatusCodeFromError(error)
      );
    }
  }

  async getResource(
    orgId: string,
    envId: string,
    resourceName: string,
    agentToken?: string | null
  ): Promise<MCPResourceContent> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.get<MCPResourceContent>(
        `${MCP_FABRIC_URL}/.well-known/mcp/resources/${resourceName}`,
        { 
          headers: this.getHeaders(agentToken),
          timeout: 10000, // 10 second timeout
        }
      );
      return response.data;
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        this._getStatusCodeFromError(error)
      );
    }
  }

  async getPrompts(orgId: string, envId: string, agentToken?: string | null): Promise<MCPPrompt[]> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.get<MCPPrompt[]>(
        `${MCP_FABRIC_URL}/.well-known/mcp/prompts`,
        { 
          headers: this.getHeaders(agentToken),
          timeout: 10000, // 10 second timeout
        }
      );
      return Array.isArray(response.data) ? response.data : [];
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        this._getStatusCodeFromError(error)
      );
    }
  }

  async invokePrompt(
    orgId: string,
    envId: string,
    promptName: string,
    input: Record<string, any>,
    agentToken?: string | null
  ): Promise<MCPPromptResponse> {
    // Note: orgId/envId are kept for backward compatibility but not used in URL
    // org_id/env_id are extracted from token claims (secure multi-tenant)
    try {
      const response = await axios.post<MCPPromptResponse>(
        `${MCP_FABRIC_URL}/.well-known/mcp/prompts/${promptName}/invoke`,
        { arguments: input },
        { 
          headers: this.getHeaders(agentToken),
          timeout: 30000, // 30 second timeout for prompt invocation
        }
      );
      return response.data;
    } catch (error: any) {
      throw new MCPFabricError(
        handleMCPError(error),
        this._getStatusCodeFromError(error)
      );
    }
  }
}

export const mcpFabric = new MCPFabricClient();

