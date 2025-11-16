/**
 * Validation logic for canvas edge connections.
 * Defines which node types can be logically connected.
 */

import type { CanvasNodeType, CanvasEdgeType } from "./canvasTypes";

/**
 * Valid edge connections based on logical model relationships.
 * 
 * Format: { sourceType: { targetType: edgeType } }
 */
export const validEdgeConnections: Record<
  CanvasNodeType,
  Partial<Record<CanvasNodeType, CanvasEdgeType[]>>
> = {
  // Agent connections
  agent: {
    tool: ["agent-tool"], // Agent uses Tool (only allowed via PolicyRules)
    resource: ["agent-resource"], // Agent accesses Resource (is_allowed_resource)
    server: ["agent-server"], // Agent hosted on Server/Connection (Agent.connection FK)
    // Note: agent-environment removed - not shown by default
  },
  
  // Tool connections
  tool: {
    // Note: tool-server and tool-environment removed - not shown by default
  },
  
  // Resource connections
  resource: {
    // Note: resource-environment removed - not shown by default
  },
  
  // Policy connections (PolicyBinding with scope_type)
  policy: {
    agent: ["policy-agent"], // Policy applies to Agent (PolicyBinding scope_type="agent")
    tool: ["policy-tool"], // Policy applies to Tool (PolicyBinding scope_type="tool")
    server: ["policy-server"], // Policy applies to Server/Connection
    resource: ["policy-resource"], // Policy applies to Resource (PolicyBinding scope_type="resource_ns")
    // Note: policy-environment removed - not shown by default
  },
  
  // Environment connections
  environment: {
    server: ["environment-server"], // Environment contains Server/Connection (reversed from Connection.environment FK)
    policy: ["environment-policy"], // Environment contains Policy (reversed from Policy.environment FK)
    resource: ["environment-resource"], // Environment contains Resource (reversed from Resource.environment FK)
    prompt: ["environment-prompt"], // Environment contains Prompt (reversed from Prompt.environment FK)
    // Note: environment-agent is not shown - Agent relationships are shown via Agent → Connection/Tool
  },
  
  // Prompt connections
  prompt: {
    resource: ["prompt-resource"], // Prompt uses Resource (from Prompt.uses_resources)
  },
  
  // Organization connections
  organization: {
    environment: ["organization-environment"], // Organization contains Environment (Environment.organization FK)
  },
  
  // Server connections (Connection model)
  server: {
    tool: ["server-tool"], // Server/Connection provides Tool (reversed from Tool.connection FK)
  },
};

/**
 * Check if an edge connection is valid.
 */
export function isValidEdgeConnection(
  sourceType: CanvasNodeType,
  targetType: CanvasNodeType,
  edgeType?: CanvasEdgeType
): boolean {
  const validTargets = validEdgeConnections[sourceType];
  if (!validTargets) {
    return false;
  }

  const validEdgeTypes = validTargets[targetType];
  if (!validEdgeTypes || validEdgeTypes.length === 0) {
    return false;
  }

  // If edgeType is specified, check if it's in the valid list
  if (edgeType) {
    return validEdgeTypes.includes(edgeType);
  }

  // If no edgeType specified, any valid edge type is acceptable
  return true;
}

/**
 * Get valid edge types for a source-target combination.
 */
export function getValidEdgeTypes(
  sourceType: CanvasNodeType,
  targetType: CanvasNodeType
): CanvasEdgeType[] {
  return validEdgeConnections[sourceType]?.[targetType] || [];
}

/**
 * Get the default edge type for a source-target combination.
 */
export function getDefaultEdgeType(
  sourceType: CanvasNodeType,
  targetType: CanvasNodeType
): CanvasEdgeType | null {
  const validTypes = getValidEdgeTypes(sourceType, targetType);
  return validTypes.length > 0 ? validTypes[0] : null;
}

/**
 * Get all valid target types for a source type.
 */
export function getValidTargetTypes(sourceType: CanvasNodeType): CanvasNodeType[] {
  const validTargets = validEdgeConnections[sourceType];
  if (!validTargets) {
    return [];
  }
  return Object.keys(validTargets) as CanvasNodeType[];
}

/**
 * Get all valid source types for a target type.
 */
export function getValidSourceTypes(targetType: CanvasNodeType): CanvasNodeType[] {
  const validSources: CanvasNodeType[] = [];
  for (const [sourceType, targets] of Object.entries(validEdgeConnections)) {
    if (targets && targetType in targets) {
      validSources.push(sourceType as CanvasNodeType);
    }
  }
  return validSources;
}

/**
 * Defines which child nodes each node type can CREATE (not just connect to).
 * This is different from edge validation - it's about creation permissions.
 * 
 * Based on the logical model:
 * - Environment contains Connections and Policies
 * - Connection (Server) provides Tools and Resources
 * - Agent uses Tools/Resources but doesn't create them
 * - Tool/Resource/Policy are endpoints, not containers
 */
export const allowedChildNodes: Record<CanvasNodeType, CanvasNodeType[]> = {
  environment: ["server", "policy", "agent", "resource", "prompt"], // Environment kann Server, Policy, Agent, Resource & Prompt erstellen
  server: ["tool"], // Connection kann nur Tools erstellen (Tools haben connection FK)
  tool: [], // Tool kann nichts erstellen (optional: "run" wenn implementiert)
  resource: [], // Resource kann nichts erstellen
  agent: [], // Agent kann nichts erstellen (optional: "run" wenn implementiert)
  policy: [], // Policy kann nichts erstellen (Rules werden intern verwaltet)
  prompt: [], // Prompt kann nichts ERSTELLEN - nur existierende Resources verknüpfen (über Node-Sidebar)
  organization: ["environment"], // Organization kann Environments erstellen
};

/**
 * Get allowed child node types that a parent node can CREATE.
 * This is for the plus button menu - what can this node create?
 */
export function getAllowedChildNodes(parentType: CanvasNodeType): CanvasNodeType[] {
  return allowedChildNodes[parentType] || [];
}

/**
 * Check if a parent node can create a specific child node type.
 */
export function canCreateChildNode(parentType: CanvasNodeType, childType: CanvasNodeType): boolean {
  return getAllowedChildNodes(parentType).includes(childType);
}

/**
 * Get all parent node types that can create a specific child node type.
 * Used for the "left" plus button - which nodes can create this node?
 */
export function getValidParentTypes(childType: CanvasNodeType): CanvasNodeType[] {
  const validParents: CanvasNodeType[] = [];
  for (const [parentType, children] of Object.entries(allowedChildNodes)) {
    if (children.includes(childType)) {
      validParents.push(parentType as CanvasNodeType);
    }
  }
  return validParents;
}

