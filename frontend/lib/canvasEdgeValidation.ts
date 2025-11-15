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
    tool: ["agent-tool"], // Agent uses Tool (Run model)
    resource: ["agent-resource"], // Agent accesses Resource (is_allowed_resource)
    server: ["agent-server"], // Agent hosted on Server/Connection (Agent.connection FK)
    environment: ["agent-environment"], // Agent belongs to Environment (Agent.environment FK)
  },
  
  // Tool connections
  tool: {
    server: ["tool-server"], // Tool from Server/Connection (Tool.connection FK)
  },
  
  // Resource connections
  resource: {
    server: ["resource-server"], // Resource from Server (via MCP)
  },
  
  // Policy connections (PolicyBinding with scope_type)
  policy: {
    agent: ["policy-agent"], // Policy applies to Agent (PolicyBinding scope_type="agent")
    tool: ["policy-tool"], // Policy applies to Tool (PolicyBinding scope_type="tool")
    server: ["policy-server"], // Policy applies to Server/Connection
    resource: ["policy-resource"], // Policy applies to Resource (PolicyBinding scope_type="resource_ns")
  },
  
  // Environment connections
  environment: {
    server: ["environment-server"], // Environment on Server
    organization: ["organization-environment"], // Environment belongs to Organization (Environment.organization FK)
  },
  
  // Organization connections
  organization: {
    environment: ["organization-environment"], // Organization contains Environment (Environment.organization FK)
  },
  
  // Server connections (Connection model)
  server: {
    // Servers can be targets but typically not sources for logical relationships
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

