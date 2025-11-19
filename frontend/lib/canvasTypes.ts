/**
 * TypeScript types for Canvas visualization system.
 */

import type { Node, Edge } from "@xyflow/react";
import type { Agent, Tool, Resource, Policy, Connection, Environment, Organization, Prompt } from "./types";

// Node types in the canvas
export type CanvasNodeType = 
  | "agent" 
  | "tool" 
  | "resource" 
  | "policy" 
  | "server" 
  | "environment"
  | "organization"
  | "prompt";

// Node data structure
export interface CanvasNodeData extends Record<string, unknown> {
  type: CanvasNodeType;
  // Entity IDs
  agentId?: string;
  toolId?: string;
  resourceId?: string;
  policyId?: string;
  connectionId?: string;
  environmentId?: string;
  organizationId?: string;
  promptId?: string;
  // Entity data (full objects)
  agent?: Agent;
  tool?: Tool;
  resource?: Resource;
  policy?: Policy;
  connection?: Connection;
  environment?: Environment;
  organization?: Organization;
  prompt?: Prompt;
  // Visual properties
  label: string;
  status?: "connected" | "error" | "unauthorized" | "disabled" | "unknown";
  // Grouping
  groupId?: string;
  // Metadata
  metadata?: Record<string, any>;
  // Position tracking (internal)
  dirty?: boolean; // true if user has moved this node
  // Callback for creating new nodes
  onCreateNode?: (type: CanvasNodeType, position: { x: number; y: number }, side: "left" | "right", sourceNodeId?: string) => void;
  // Callback for node actions (test, sync, run, etc.)
  onAction?: (action: string, entityId?: string) => void;
  // Edge information for showing buttons
  hasConnections?: boolean;
}

// Edge types
export type CanvasEdgeType = 
  | "agent-tool"        // Agent uses Tool (only allowed)
  | "agent-resource"    // Agent accesses Resource
  | "agent-server"      // Agent hosted on Server
  | "agent-environment" // Agent in Environment (deprecated - not shown by default)
  | "tool-server"       // Tool from Server (deprecated - use server-tool)
  | "tool-environment"  // Tool belongs to Environment (deprecated - not shown by default)
  | "resource-environment" // Resource belongs to Environment (deprecated - not shown by default)
  | "environment-resource" // Environment contains Resource (reversed from Resource.environment FK)
  | "policy-agent"      // Policy applies to Agent
  | "policy-tool"        // Policy applies to Tool
  | "policy-server"     // Policy applies to Server
  | "policy-resource"    // Policy applies to Resource
  | "policy-environment" // Policy belongs to Environment (deprecated - not shown by default)
  | "environment-policy" // Environment contains Policy (reversed from Policy.environment FK)
  | "agent-environment" // Agent in Environment (deprecated - not shown by default)
  | "environment-agent" // Environment contains Agent (reversed from Agent.environment FK)
  | "environment-prompt" // Environment contains Prompt (reversed from Prompt.environment FK)
  | "prompt-resource"    // Prompt uses Resource (from Prompt.uses_resources)
  | "server-environment" // Server belongs to Environment (deprecated - use environment-server)
  | "environment-server" // Environment contains Server/Connection
  | "server-tool"        // Server/Connection provides Tool
  | "organization-environment"; // Organization contains Environment

// Edge data structure
export interface CanvasEdgeData extends Record<string, unknown> {
  type: CanvasEdgeType;
  // Configuration based on edge type
  config?: {
    // For agent-tool: tool is in allowlist
    allowed?: boolean;
    // For agent-resource: access permissions
    permissions?: string[];
    // For policy edges: rule details
    ruleId?: string;
    effect?: "allow" | "deny";
    conditions?: Record<string, any>;
  };
  metadata?: Record<string, any>;
}

// Canvas state
export interface CanvasState {
  nodes: Node<CanvasNodeData>[];
  edges: Edge<CanvasEdgeData>[];
  viewport: {
    x: number;
    y: number;
    zoom: number;
  };
  groups: {
    [groupId: string]: {
      name: string;
      type: "organization" | "environment" | "server";
      nodes: string[]; // Node IDs
      position: { x: number; y: number };
      size: { width: number; height: number };
    };
  };
}

// Export format for AgentxSuite config
export interface CanvasExportConfig {
  version: string;
  exportedAt: string;
  organizationId: string;
  canvas: CanvasState;
  // Mapped to actual entities
  agents: Agent[];
  tools: Tool[];
  resources: Resource[];
  policies: Policy[];
  connections: Connection[];
  environments: Environment[];
  // Relationships
  relationships: {
    agentTools: Array<{ agentId: string; toolId: string; allowed: boolean }>;
    agentResources: Array<{ agentId: string; resourceId: string; permissions: string[] }>;
    agentServers: Array<{ agentId: string; connectionId: string }>;
    agentEnvironments: Array<{ agentId: string; environmentId: string }>;
    toolServers: Array<{ toolId: string; connectionId: string }>;
    resourceServers: Array<{ resourceId: string; connectionId: string }>;
    policyBindings: Array<{
      policyId: string;
      targetType: "agent" | "tool" | "server" | "resource";
      targetId: string;
      ruleId?: string;
      effect: "allow" | "deny";
      conditions?: Record<string, any>;
    }>;
  };
}

// Node creation payload
export interface CreateNodePayload {
  type: CanvasNodeType;
  position: { x: number; y: number };
  data: Partial<CanvasNodeData>;
}

// Connection creation payload
export interface CreateConnectionPayload {
  source: string; // Node ID
  target: string; // Node ID
  type: CanvasEdgeType;
  config?: CanvasEdgeData["config"];
}

