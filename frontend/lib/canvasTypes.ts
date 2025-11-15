/**
 * TypeScript types for Canvas visualization system.
 */

import type { Node, Edge } from "@xyflow/react";
import type { Agent, Tool, Resource, Policy, Connection, Environment, Organization } from "./types";

// Node types in the canvas
export type CanvasNodeType = 
  | "agent" 
  | "tool" 
  | "resource" 
  | "policy" 
  | "server" 
  | "environment"
  | "organization";

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
  // Entity data (full objects)
  agent?: Agent;
  tool?: Tool;
  resource?: Resource;
  policy?: Policy;
  connection?: Connection;
  environment?: Environment;
  organization?: Organization;
  // Visual properties
  label: string;
  status?: "connected" | "error" | "unauthorized" | "disabled" | "unknown";
  // Grouping
  groupId?: string;
  // Metadata
  metadata?: Record<string, any>;
  // Callback for creating new nodes
  onCreateNode?: (type: CanvasNodeType, position: { x: number; y: number }, side: "left" | "right", sourceNodeId?: string) => void;
  // Edge information for showing buttons
  hasConnections?: boolean;
}

// Edge types
export type CanvasEdgeType = 
  | "agent-tool"        // Agent uses Tool
  | "agent-resource"    // Agent accesses Resource
  | "agent-server"      // Agent hosted on Server
  | "agent-environment" // Agent in Environment
  | "tool-server"       // Tool from Server
  | "resource-server"   // Resource from Server
  | "policy-agent"      // Policy applies to Agent
  | "policy-tool"        // Policy applies to Tool
  | "policy-server"     // Policy applies to Server
  | "policy-resource"    // Policy applies to Resource
  | "environment-server" // Environment on Server
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

