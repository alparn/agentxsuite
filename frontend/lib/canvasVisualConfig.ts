/**
 * Canvas Visual Configuration
 * 
 * Defines visual hierarchy, colors, sizes, and layout rules for canvas nodes
 */

import type { CanvasNodeType } from "./canvasTypes";

// ============================================================================
// NODE SIZES (based on visual importance)
// ============================================================================

export type NodeSize = "small" | "medium" | "large" | "xlarge";

export const nodeSizeConfig: Record<CanvasNodeType, NodeSize> = {
  // Small: Context elements (very compact)
  environment: "small",
  
  // Medium: Secondary elements
  prompt: "medium",
  resource: "medium",
  policy: "medium",
  tool: "medium",
  
  // Large: Agents (intelligent actors)
  agent: "large",
  organization: "large",
  
  // XLarge: Servers (most prominent - the stars of the show)
  server: "xlarge",
};

export const nodeSizeClasses: Record<NodeSize, string> = {
  small: "w-36 min-h-[60px]", // Very compact (Environments) - extra small
  medium: "w-52 min-h-[85px]", // Standard (Tools, Policies, Resources)
  large: "w-60 min-h-[110px]", // Prominent (Agents)
  xlarge: "w-80 min-h-[150px]", // Extra large (Servers - the stars) - even bigger
};

// ============================================================================
// NODE COLORS (distinct, meaningful)
// ============================================================================

export interface NodeColorScheme {
  bg: string; // Background color (subtle)
  border: string; // Border color
  icon: string; // Icon color (bright)
  iconBg: string; // Icon background
  text: string; // Primary text
  accent: string; // Accent color for mini-map
}

export const nodeColors: Record<CanvasNodeType, NodeColorScheme> = {
  // Environment: Gray/Blue (neutral, structural) - very subtle
  environment: {
    bg: "bg-slate-800/20",
    border: "border-slate-600/30",
    icon: "text-slate-400",
    iconBg: "bg-slate-700/20",
    text: "text-slate-300",
    accent: "#64748b",
  },
  
  // Server/MCP: Teal (services, connections) - PROMINENT
  server: {
    bg: "bg-teal-900/40",
    border: "border-teal-500/60",
    icon: "text-teal-300",
    iconBg: "bg-teal-500/20",
    text: "text-teal-50",
    accent: "#14b8a6",
  },
  
  // Agent: Purple (intelligent actors) - PROMINENT
  agent: {
    bg: "bg-purple-900/40",
    border: "border-purple-500/60",
    icon: "text-purple-300",
    iconBg: "bg-purple-500/20",
    text: "text-purple-50",
    accent: "#a855f7",
  },
  
  // Tool: Blue (actions, functions)
  tool: {
    bg: "bg-blue-900/25",
    border: "border-blue-500/40",
    icon: "text-blue-300",
    iconBg: "bg-blue-500/15",
    text: "text-blue-50",
    accent: "#3b82f6",
  },
  
  // Policy: Yellow/Amber (security, rules)
  policy: {
    bg: "bg-yellow-900/25",
    border: "border-yellow-500/40",
    icon: "text-yellow-300",
    iconBg: "bg-yellow-500/15",
    text: "text-yellow-50",
    accent: "#eab308",
  },
  
  // Resource: Orange (data, content)
  resource: {
    bg: "bg-orange-900/25",
    border: "border-orange-500/40",
    icon: "text-orange-300",
    iconBg: "bg-orange-500/15",
    text: "text-orange-50",
    accent: "#f97316",
  },
  
  // Organization: Indigo (top-level structure)
  organization: {
    bg: "bg-indigo-900/30",
    border: "border-indigo-600/50",
    icon: "text-indigo-400",
    iconBg: "bg-indigo-500/10",
    text: "text-indigo-100",
    accent: "#6366f1",
  },
  
  // Prompt: Pink (templates, conversations)
  prompt: {
    bg: "bg-pink-900/30",
    border: "border-pink-600/50",
    icon: "text-pink-400",
    iconBg: "bg-pink-500/10",
    text: "text-pink-100",
    accent: "#ec4899",
  },
};

// ============================================================================
// LAYOUT LANES (horizontal grouping)
// ============================================================================

export interface Lane {
  id: string;
  label: string;
  color: string;
  x: number; // X position (column)
  nodeTypes: CanvasNodeType[];
}

export const lanes: Lane[] = [
  {
    id: "context",
    label: "Context",
    color: "slate",
    x: 0,
    nodeTypes: ["organization", "environment"],
  },
  {
    id: "core",
    label: "Core Services",
    color: "teal",
    x: 400,
    nodeTypes: ["server", "agent"],
  },
  {
    id: "capabilities",
    label: "Capabilities",
    color: "blue",
    x: 900,
    nodeTypes: ["tool", "policy", "resource", "prompt"],
  },
];

// ============================================================================
// AUTO-LAYOUT CONFIGURATION
// ============================================================================

export const layoutConfig = {
  // Spacing between nodes (MUCH larger to prevent overlap completely)
  nodeSpacing: {
    horizontal: 250, // Space between columns (lanes) - very wide
    vertical: 250, // Space between rows (nodes in same lane) - EXTRA LARGE to prevent any overlap
  },
  
  // Lane configuration
  laneWidth: 500, // Width of each lane (must fit XL servers + padding)
  laneGap: 200, // Very large gap between lanes for maximum clarity
  
  // Starting position
  startX: 100,
  startY: 100,
  
  // Alignment within lanes
  alignVertical: true, // Stack nodes vertically in lanes
  centerInLane: false, // Left-align nodes in lanes for consistency
  
  // Node height estimates (for overlap prevention) - realistic sizes including ALL content
  // These must match actual rendered heights: Header (40px) + Body (40px) + Buttons (35px) + Padding
  nodeHeights: {
    small: 100,   // Environment nodes: Header + Body only (no buttons)
    medium: 150,  // Tools, policies, resources: Header + Body + 1 Button
    large: 160,   // Agents: Header + Body + 1 Button (similar to medium)
    xlarge: 230,  // Servers: Header + Body + 2 Buttons (tallest)
  },
};

// ============================================================================
// EDGE STYLES (connection types)
// ============================================================================

export const edgeStyles = {
  default: {
    stroke: "#64748b",
    strokeWidth: 2,
    animated: false,
  },
  agentTool: {
    stroke: "#a855f7",
    strokeWidth: 2.5,
    animated: true,
  },
  agentResource: {
    stroke: "#f97316",
    strokeWidth: 2,
    animated: false,
  },
  toolPolicy: {
    stroke: "#eab308",
    strokeWidth: 2,
    animated: false,
  },
  serverTool: {
    stroke: "#3b82f6",
    strokeWidth: 2,
    animated: false,
  },
  environmentServer: {
    stroke: "#06b6d4",
    strokeWidth: 2,
    animated: false,
  },
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get lane for a specific node type
 */
export function getLaneForNodeType(type: CanvasNodeType): Lane | undefined {
  return lanes.find((lane) => lane.nodeTypes.includes(type));
}

/**
 * Get auto-layout position for a node type
 * Ensures nodes don't overlap by calculating proper spacing
 */
export function getAutoLayoutPosition(
  type: CanvasNodeType,
  indexInLane: number
): { x: number; y: number } {
  const lane = getLaneForNodeType(type);
  if (!lane) {
    return { x: 0, y: 0 };
  }
  
  // Calculate X position (lane position + start offset)
  const x = lane.x + layoutConfig.startX;
  
  // Calculate Y position with proper spacing to prevent overlap
  // Get node size to calculate appropriate spacing
  const size = nodeSizeConfig[type] || "medium";
  const nodeHeight = layoutConfig.nodeHeights[size];
  
  // Y position = start + (index * (node height + vertical spacing))
  // This ensures each node has its own vertical space
  const totalSpacingPerNode = nodeHeight + layoutConfig.nodeSpacing.vertical;
  const y = layoutConfig.startY + indexInLane * totalSpacingPerNode;
  
  return { x, y };
}

/**
 * Get color scheme for node type
 */
export function getNodeColors(type: CanvasNodeType): NodeColorScheme {
  return nodeColors[type] || nodeColors.tool;
}

/**
 * Get size class for node type
 */
export function getNodeSizeClass(type: CanvasNodeType): string {
  const size = nodeSizeConfig[type] || "medium";
  return nodeSizeClasses[size];
}

