"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  NodeChange,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CanvasNode } from "./CanvasNode";
import { CanvasSidebar } from "./CanvasSidebar";
import { CanvasEdgeSidebar } from "./CanvasEdgeSidebar";
import { CanvasToolbar } from "./CanvasToolbar";
import { TestConnectionModal } from "./TestConnectionModal";
import { SyncToolsModal } from "./SyncToolsModal";
import { RunToolModal } from "./RunToolModal";
import { PingAgentModal } from "./PingAgentModal";
import { AgentDialog } from "../AgentDialog";
import { ToolDialog } from "../ToolDialog";
import { ResourceDialog } from "../ResourceDialog";
import { ConnectionDialog } from "../ConnectionDialog";
import { EnvironmentDialog } from "../EnvironmentDialog";
import { PolicyDialog } from "../PolicyDialog";
import { PromptDialog } from "../PromptDialog";
import { api, agentsApi, canvasApi, policyRulesApi, policyBindingsApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CanvasNodeData, CanvasEdgeData, CanvasState, CanvasNodeType } from "@/lib/canvasTypes";
import { isValidEdgeConnection, getDefaultEdgeType, getValidEdgeTypes } from "@/lib/canvasEdgeValidation";
import { Plus, Download, Upload, Save, RefreshCw, Layers, Filter, X, ArrowDownUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { getAutoLayoutPosition, getLaneForNodeType } from "@/lib/canvasVisualConfig";

const nodeTypes = {
  canvasNode: CanvasNode,
};

// Inner component for node navigation
function NodeNavigator({ nodes }: { nodes: Node<CanvasNodeData>[] }) {
  const { setCenter, getNode } = useReactFlow();
  const [isOpen, setIsOpen] = useState(false);
  
  // Function to zoom to a specific node
  const zoomToNode = useCallback((nodeId: string) => {
    const node = getNode(nodeId);
    if (!node) return;
    
    // Center on node with zoom
    const nodeWidth = node.data.type === "server" ? 320 : node.data.type === "agent" ? 240 : 208;
    const nodeHeight = node.data.type === "server" ? 200 : node.data.type === "agent" ? 150 : 120;
    
    setCenter(node.position.x + nodeWidth / 2, node.position.y + nodeHeight / 2, {
      zoom: 1.5,
      duration: 600,
    });
  }, [setCenter, getNode]);
  
  // Group nodes by type
  const nodesByType = useMemo(() => {
    const grouped = new Map<CanvasNodeType, Node<CanvasNodeData>[]>();
    nodes.forEach((node) => {
      const type = node.data.type;
      if (!grouped.has(type)) {
        grouped.set(type, []);
      }
      grouped.get(type)!.push(node);
    });
    return grouped;
  }, [nodes]);
  
  if (!isOpen) {
    return (
      <Panel position="bottom-left" className="m-2">
        <button
          onClick={() => setIsOpen(true)}
          className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2 shadow-lg"
          title="Open node navigator"
        >
          <Layers className="w-4 h-4" />
          Navigator
        </button>
      </Panel>
    );
  }
  
  return (
    <Panel position="bottom-left" className="m-2">
      <div className="bg-slate-900/95 rounded-lg shadow-xl border border-slate-700 max-w-xs max-h-96 overflow-hidden flex flex-col">
        <div className="px-3 py-2 border-b border-slate-700 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">Node Navigator</h3>
          <button
            onClick={() => setIsOpen(false)}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-2">
          {Array.from(nodesByType.entries()).map(([type, nodesOfType]) => (
            <div key={type} className="mb-3">
              <div className="text-xs font-semibold text-slate-400 uppercase px-2 py-1">
                {type}s ({nodesOfType.length})
              </div>
              {nodesOfType.map((node) => (
                <button
                  key={node.id}
                  onClick={() => zoomToNode(node.id)}
                  className="w-full text-left px-2 py-1.5 text-sm text-slate-300 hover:bg-slate-700/50 rounded transition-colors flex items-center gap-2"
                >
                  <div className={cn(
                    "w-5 h-5 rounded flex items-center justify-center text-xs font-bold",
                    type === "server" && "bg-teal-500/20 text-teal-400",
                    type === "agent" && "bg-purple-500/20 text-purple-400",
                    type === "tool" && "bg-blue-500/20 text-blue-400",
                    type === "policy" && "bg-yellow-500/20 text-yellow-400",
                    type === "resource" && "bg-orange-500/20 text-orange-400",
                    type === "environment" && "bg-slate-500/20 text-slate-400",
                    type === "prompt" && "bg-pink-500/20 text-pink-400",
                  )}>
                    {type === "server" ? "S" : type === "agent" ? "A" : type === "tool" ? "T" : 
                     type === "policy" ? "P" : type === "resource" ? "R" : type === "environment" ? "E" : "►"}
                  </div>
                  <span className="truncate">{node.data.label}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

export function CanvasView() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();
  const [selectedNode, setSelectedNode] = useState<Node<CanvasNodeData> | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<Edge<CanvasEdgeData> | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [edgeSidebarOpen, setEdgeSidebarOpen] = useState(false);
  const [groupBy, setGroupBy] = useState<"none" | "organization" | "environment" | "server">("none");
  const [showAgentDialog, setShowAgentDialog] = useState(false);
  const [showToolDialog, setShowToolDialog] = useState(false);
  const [showResourceDialog, setShowResourceDialog] = useState(false);
  const [showConnectionDialog, setShowConnectionDialog] = useState(false);
  const [showEnvironmentDialog, setShowEnvironmentDialog] = useState(false);
  const [showPolicyDialog, setShowPolicyDialog] = useState(false);
  const [showPromptDialog, setShowPromptDialog] = useState(false);
  const [pendingNodeType, setPendingNodeType] = useState<CanvasNodeType | null>(null);
  const [pendingPosition, setPendingPosition] = useState<{ x: number; y: number } | null>(null);
  const [pendingSourceNodeId, setPendingSourceNodeId] = useState<string | undefined>(undefined);
  const [pendingSide, setPendingSide] = useState<"left" | "right" | undefined>(undefined);
  const [preselectedEnvironmentId, setPreselectedEnvironmentId] = useState<string | undefined>(undefined);
  const [preselectedConnectionId, setPreselectedConnectionId] = useState<string | undefined>(undefined);
  
  // Action modal states
  const [showTestModal, setShowTestModal] = useState(false);
  const [showSyncModal, setShowSyncModal] = useState(false);
  const [showRunModal, setShowRunModal] = useState(false);
  const [showPingModal, setShowPingModal] = useState(false);
  const [selectedActionEntityId, setSelectedActionEntityId] = useState<string>("");
  const [selectedActionEntityName, setSelectedActionEntityName] = useState<string>("");
  
  // Filter state
  const [showFilter, setShowFilter] = useState(false);
  const [filteredNodeTypes, setFilteredNodeTypes] = useState<Set<CanvasNodeType>>(new Set());
  const [filteredEdgeTypes, setFilteredEdgeTypes] = useState<Set<string>>(new Set());
  const [filteredStatuses, setFilteredStatuses] = useState<Set<string>>(new Set());
  const filterMenuRef = useRef<HTMLDivElement>(null);
  
  // Track viewport for saving
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  
  // Ref for managing edge creation timeouts to prevent memory leaks
  const edgeTimeoutsRef = useRef<Set<NodeJS.Timeout>>(new Set());

  // Fetch current organization from backend
  const { data: currentOrgData } = useQuery({
    queryKey: ["current-organization"],
    queryFn: async () => {
      const response = await api.get("/auth/me/");
      // Backend should return current organization info
      return response.data;
    },
  });

  // Extract orgId from backend response
  const backendOrgId = currentOrgData?.organization_id || currentOrgData?.organization?.id || null;
  
  // Use backend orgId if available, otherwise fall back to store
  const effectiveOrgId = backendOrgId || orgId;
  
  // Update store if backend provides different orgId
  useEffect(() => {
    if (backendOrgId && backendOrgId !== orgId) {
      setCurrentOrg(backendOrgId);
    }
  }, [backendOrgId, orgId, setCurrentOrg]);
  
  // Cleanup all edge timeouts on unmount
  useEffect(() => {
    return () => {
      edgeTimeoutsRef.current.forEach(clearTimeout);
      edgeTimeoutsRef.current.clear();
    };
  }, []);

  // Fetch all entities (only when effectiveOrgId is available)
  const { data: agentsData } = useQuery({
    queryKey: ["agents", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      const response = await api.get(`/orgs/${effectiveOrgId}/agents/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!effectiveOrgId, // Only fetch when orgId is available
  });

  const { data: toolsData } = useQuery({
    queryKey: ["tools", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      const response = await api.get(`/orgs/${effectiveOrgId}/tools/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!effectiveOrgId,
  });

  const { data: resourcesData } = useQuery({
    queryKey: ["resources", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      const response = await api.get(`/orgs/${effectiveOrgId}/resources/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!effectiveOrgId,
  });

  const { data: policiesData } = useQuery({
    queryKey: ["policies", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      const response = await api.get(`/orgs/${effectiveOrgId}/policies/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!effectiveOrgId,
  });

  const { data: connectionsData } = useQuery({
    queryKey: ["connections", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      const response = await api.get(`/orgs/${effectiveOrgId}/connections/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!effectiveOrgId,
  });

  const { data: environmentsData, isLoading: environmentsLoading } = useQuery({
    queryKey: ["environments", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) {
        throw new Error("Organization ID is required");
      }
      try {
        // Try organization-specific endpoint first
        const response = await api.get(`/orgs/${effectiveOrgId}/environments/`);
        return Array.isArray(response.data) ? response.data : response.data?.results || [];
      } catch (error: any) {
        // Fallback: try direct environments endpoint with org filter
        if (error.response?.status === 404) {
          try {
            const response = await api.get(`/environments/`, { params: { organization: effectiveOrgId } });
            return Array.isArray(response.data) ? response.data : response.data?.results || [];
          } catch (e) {
            console.error("Failed to fetch environments:", e);
            return [];
          }
        }
        console.error("Failed to fetch environments:", error);
        return [];
      }
    },
    enabled: !!effectiveOrgId,
  });

  // Fetch Prompts
  const { data: promptsData } = useQuery({
    queryKey: ["prompts", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) return [];
      try {
        const response = await api.get(`/orgs/${effectiveOrgId}/prompts/`);
        if (Array.isArray(response.data)) {
          return response.data;
        }
        return response.data?.results || [];
      } catch (error) {
        console.error("Failed to fetch prompts:", error);
        return [];
      }
    },
    enabled: !!effectiveOrgId,
  });

  // Fetch PolicyRules for checking allowed Agent → Tool connections
  const { data: policyRulesData } = useQuery({
    queryKey: ["policy-rules", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) return [];
      try {
        const response = await policyRulesApi.list();
        if (Array.isArray(response.data)) {
          return response.data;
        }
        return response.data?.results || [];
      } catch (error) {
        console.error("Failed to fetch policy rules:", error);
        return [];
      }
    },
    enabled: !!effectiveOrgId,
  });

  // Fetch PolicyBindings for checking which policies apply to agents
  const { data: policyBindingsData } = useQuery({
    queryKey: ["policy-bindings", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) return [];
      try {
        const response = await policyBindingsApi.list();
        if (Array.isArray(response.data)) {
          return response.data;
        }
        return response.data?.results || [];
      } catch (error) {
        console.error("Failed to fetch policy bindings:", error);
        return [];
      }
    },
    enabled: !!effectiveOrgId,
  });

  // Layout helper: Calculate positions to avoid overlaps
  const calculateLayout = useCallback((
    items: any[],
    startX: number,
    startY: number,
    nodeWidth: number = 200,
    nodeHeight: number = 100,
    spacing: number = 50
  ) => {
    const positions: Array<{ x: number; y: number }> = [];
    const cols = Math.ceil(Math.sqrt(items.length)) || 1;
    const rows = Math.ceil(items.length / cols) || 1;
    
    items.forEach((_, idx) => {
      const col = idx % cols;
      const row = Math.floor(idx / cols);
      const x = startX + col * (nodeWidth + spacing);
      const y = startY + row * (nodeHeight + spacing);
      positions.push({
        x: isNaN(x) ? 0 : x,
        y: isNaN(y) ? 0 : y,
      });
    });
    
    return positions;
  }, []);

  // Helper to validate and ensure position is valid
  const ensureValidPosition = useCallback((pos: { x: number; y: number } | undefined, fallback: { x: number; y: number }): { x: number; y: number } => {
    if (!pos || typeof pos.x !== 'number' || typeof pos.y !== 'number' || isNaN(pos.x) || isNaN(pos.y)) {
      return fallback;
    }
    return pos;
  }, []);


  // Convert entities to canvas nodes with better layout
  const initialNodes = useMemo(() => {
    const nodes: Node<CanvasNodeData>[] = [];
    const nodeWidth = 200;
    const nodeHeight = 100;
    const spacing = 50;
    const sectionSpacing = 300;
    
    let currentY = 100;
    let currentX = 100;

    // Group by environment for better organization
    const nodesByEnv = new Map<string, any[]>();
    
    // Add environments first (as containers)
    (environmentsData || []).forEach((env: any, idx: number) => {
      const envPositions = calculateLayout([env], currentX, currentY, nodeWidth, nodeHeight, spacing);
      const fallbackPos = { x: currentX, y: currentY + idx * (nodeHeight + sectionSpacing) };
      const pos = ensureValidPosition(envPositions[0], fallbackPos);
      nodes.push({
        id: `env-${env.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "environment",
          environmentId: env.id,
          environment: env,
          label: env.name,
          status: "connected",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
      nodesByEnv.set(env.id, []);
      currentY += nodeHeight + sectionSpacing;
    });

    // Reset Y for main layout
    currentY = 100;
    const maxX = 1200; // Max width before wrapping

    // Add agents with better spacing
    const agentPositions = calculateLayout(agentsData || [], currentX, currentY, nodeWidth, nodeHeight, spacing);
    (agentsData || []).forEach((agent: any, idx: number) => {
      const fallbackPos = { x: currentX + (idx % 3) * (nodeWidth + spacing), y: currentY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const pos = ensureValidPosition(agentPositions[idx], fallbackPos);
      nodes.push({
        id: `agent-${agent.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "agent",
          agentId: agent.id,
          agent,
          label: agent.name,
          status: agent.enabled ? "connected" : "disabled",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    // Add resources (positioned early for visibility)
    const resourceStartY = currentY;
    const resourcePositions = calculateLayout(resourcesData || [], currentX, resourceStartY, nodeWidth, nodeHeight, spacing);
    (resourcesData || []).forEach((resource: any, idx: number) => {
      const fallbackPos = { x: currentX + (idx % 3) * (nodeWidth + spacing), y: resourceStartY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const pos = ensureValidPosition(resourcePositions[idx], fallbackPos);
      nodes.push({
        id: `resource-${resource.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "resource",
          resourceId: resource.id,
          resource,
          label: resource.name,
          status: resource.enabled ? "connected" : "disabled",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    // Add tools - position near their connections
    const maxResourceY = resourcePositions.length > 0 ? Math.max(...resourcePositions.map(p => p.y)) : resourceStartY;
    const toolStartY = maxResourceY + sectionSpacing;
    const toolsWithPositions = (toolsData || []).map((tool: any, idx: number) => {
      // Try to position tools near their connection/server
      const connectionId = tool.connection?.id || tool.connection_id;
      const connectionNode = nodes.find((n) => n.data.connectionId === connectionId);
      
      if (connectionNode) {
        // Position tool near its connection
        return {
          ...tool,
          preferredX: connectionNode.position.x + 250,
          preferredY: connectionNode.position.y + (idx % 3) * (nodeHeight + spacing),
        };
      }
      return tool;
    });

    const toolPositions = calculateLayout(toolsWithPositions, currentX, toolStartY, nodeWidth, nodeHeight, spacing);
    toolsWithPositions.forEach((tool: any, idx: number) => {
      const fallbackPos = toolPositions[idx] || { x: currentX + (idx % 3) * (nodeWidth + spacing), y: toolStartY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const preferredPos = (tool.preferredX !== undefined && tool.preferredY !== undefined && 
                           !isNaN(tool.preferredX) && !isNaN(tool.preferredY))
        ? { x: tool.preferredX, y: tool.preferredY }
        : null;
      const pos = ensureValidPosition(preferredPos || toolPositions[idx], fallbackPos);
      nodes.push({
        id: `tool-${tool.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "tool",
          toolId: tool.id,
          tool,
          label: tool.name,
          status: tool.enabled ? "connected" : "disabled",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    // Add policies
    const maxToolY = toolPositions.length > 0 ? Math.max(...toolPositions.map(p => p.y)) : toolStartY;
    const policyStartY = maxToolY + sectionSpacing;
    const policyPositions = calculateLayout(policiesData || [], currentX, policyStartY, nodeWidth, nodeHeight, spacing);
    (policiesData || []).forEach((policy: any, idx: number) => {
      const fallbackPos = { x: currentX + (idx % 3) * (nodeWidth + spacing), y: policyStartY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const pos = ensureValidPosition(policyPositions[idx], fallbackPos);
      nodes.push({
        id: `policy-${policy.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "policy",
          policyId: policy.id,
          policy,
          label: policy.name,
          status: policy.is_active ? "connected" : "disabled",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    // Add prompts
    const maxPolicyY = policyPositions.length > 0 ? Math.max(...policyPositions.map(p => p.y)) : policyStartY;
    const promptStartY = maxPolicyY + sectionSpacing;
    const promptPositions = calculateLayout(promptsData || [], currentX, promptStartY, nodeWidth, nodeHeight, spacing);
    (promptsData || []).forEach((prompt: any, idx: number) => {
      const fallbackPos = { x: currentX + (idx % 3) * (nodeWidth + spacing), y: promptStartY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const pos = ensureValidPosition(promptPositions[idx], fallbackPos);
      nodes.push({
        id: `prompt-${prompt.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "prompt",
          promptId: prompt.id,
          prompt,
          label: prompt.name,
          status: prompt.enabled ? "connected" : "disabled",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    // Add servers/connections
    const maxPromptY = promptPositions.length > 0 ? Math.max(...promptPositions.map(p => p.y)) : promptStartY;
    const connectionStartY = maxPromptY + sectionSpacing;
    const connectionPositions = calculateLayout(connectionsData || [], currentX, connectionStartY, nodeWidth, nodeHeight, spacing);
    (connectionsData || []).forEach((connection: any, idx: number) => {
      const fallbackPos = { x: currentX + (idx % 3) * (nodeWidth + spacing), y: connectionStartY + Math.floor(idx / 3) * (nodeHeight + spacing) };
      const pos = ensureValidPosition(connectionPositions[idx], fallbackPos);
      nodes.push({
        id: `server-${connection.id}`,
        type: "canvasNode",
        position: pos,
        data: {
          type: "server",
          connectionId: connection.id,
          connection,
          label: connection.name,
          status: connection.status === "ok" ? "connected" : connection.status === "fail" ? "error" : "unknown",
          hasConnections: false, // Will be updated by useEffect based on edges
        },
      });
    });

    return nodes;
  }, [agentsData, toolsData, resourcesData, policiesData, connectionsData, environmentsData, promptsData, calculateLayout, ensureValidPosition]);

  // Helper function to check if a resource is allowed for an agent via PolicyRules
  const getAllowedResourcesForAgent = useCallback((agentId: string, agentEnvId: string | null): Map<string, { policyId: string; policyName: string; action: string }> => {
    const allowedResources = new Map<string, { policyId: string; policyName: string; action: string }>();
    
    if (!policyRulesData || !policyBindingsData || !policiesData) {
      return allowedResources;
    }

    // Find all policy bindings for this agent
    const agentBindings = (policyBindingsData || []).filter(
      (binding: any) => binding.scope_type === "agent" && binding.scope_id === agentId
    );

    // Get all policies that are bound to this agent
    const boundPolicyIds = new Set(agentBindings.map((b: any) => b.policy_id));
    
    // Also include policies that match the agent's environment
    (policiesData || []).forEach((policy: any) => {
      if (
        boundPolicyIds.has(policy.id) ||
        !policy.environment_id ||
        policy.environment_id === agentEnvId
      ) {
        boundPolicyIds.add(policy.id);
      }
    });

    // Find all "resource.read" and "resource.write" rules with effect="allow" from bound policies
    (policyRulesData || []).forEach((rule: any) => {
      if (
        (rule.action === "resource.read" || rule.action === "resource.write") &&
        rule.effect === "allow" &&
        boundPolicyIds.has(rule.policy_id)
      ) {
        // Get policy info
        const policy = (policiesData || []).find((p: any) => p.id === rule.policy_id);
        const policyName = policy?.name || "Unknown Policy";
        
        // Parse target pattern (e.g., "resource:name" or "resource:*")
        const targetPattern = rule.target.replace(/^resource:/, "");
        
        // Match resources against pattern
        (resourcesData || []).forEach((resource: any) => {
          const resourceName = resource.name || "";
          
          // Pattern matching with wildcard support
          let isMatch = false;
          if (targetPattern === "*") {
            isMatch = true;
          } else if (targetPattern.endsWith("/*")) {
            // Pattern like "DB/*" - matches "DB" or "DB/anything"
            const prefix = targetPattern.slice(0, -2);
            isMatch = resourceName === prefix || resourceName.startsWith(prefix + "/");
          } else if (targetPattern.includes("*")) {
            // Pattern with * in middle or start - convert to regex
            const regexPattern = targetPattern
              .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
              .replace(/\*/g, '.*');
            const regex = new RegExp(`^${regexPattern}$`);
            isMatch = regex.test(resourceName);
          } else {
            // Exact match
            isMatch = resourceName === targetPattern;
          }
          
          if (isMatch) {
            // Store action type (read/write)
            const action = rule.action.replace("resource.", "");
            const existing = allowedResources.get(resource.id);
            if (existing) {
              // Combine actions if multiple rules allow different actions
              allowedResources.set(resource.id, { 
                ...existing, 
                action: existing.action === action ? action : `${existing.action},${action}`,
              });
            } else {
              allowedResources.set(resource.id, { policyId: rule.policy_id, policyName, action });
            }
          }
        });
      }
    });

    return allowedResources;
  }, [policyRulesData, policyBindingsData, policiesData, resourcesData]);

  // Helper function to check if a tool is allowed for an agent via PolicyRules
  const getAllowedToolsForAgent = useCallback((agentId: string, agentEnvId: string | null): Map<string, { policyId: string; policyName: string }> => {
    const allowedTools = new Map<string, { policyId: string; policyName: string }>();
    
    if (!policyRulesData || !policyBindingsData || !policiesData) {
      return allowedTools;
    }

    // Find all policy bindings for this agent
    const agentBindings = (policyBindingsData || []).filter(
      (binding: any) => binding.scope_type === "agent" && binding.scope_id === agentId
    );

    // Get all policies that are bound to this agent
    const boundPolicyIds = new Set(agentBindings.map((b: any) => b.policy_id));
    
    // Also include policies that match the agent's environment (if policy has environment)
    (policiesData || []).forEach((policy: any) => {
      // Policy applies if:
      // 1. It's bound to this agent, OR
      // 2. It has no environment (applies to all), OR
      // 3. It matches the agent's environment
      if (
        boundPolicyIds.has(policy.id) ||
        !policy.environment_id ||
        policy.environment_id === agentEnvId
      ) {
        boundPolicyIds.add(policy.id);
      }
    });

    // Find all "tool.invoke" rules with effect="allow" from bound policies
    (policyRulesData || []).forEach((rule: any) => {
      if (
        rule.action === "tool.invoke" &&
        rule.effect === "allow" &&
        boundPolicyIds.has(rule.policy_id)
      ) {
        // Get policy info
        const policy = (policiesData || []).find((p: any) => p.id === rule.policy_id);
        const policyName = policy?.name || "Unknown Policy";
        
        // Parse target pattern (e.g., "tool:namespace/name" or "tool:*")
        const targetPattern = rule.target.replace(/^tool:/, "");
        
        // Match tools against pattern
        (toolsData || []).forEach((tool: any) => {
          // Get tool identifier (namespace/name format)
          const toolNamespace = tool.connection?.name || "default";
          const toolName = tool.name || "";
          const toolIdentifier = `${toolNamespace}/${toolName}`;
          
          // Pattern matching with wildcard support
          let isMatch = false;
          if (targetPattern === "*") {
            isMatch = true;
          } else if (targetPattern.endsWith("/*")) {
            // Pattern like "namespace/*" - matches "namespace/anything"
            const prefix = targetPattern.slice(0, -2);
            isMatch = toolIdentifier.startsWith(prefix + "/") || toolIdentifier === prefix;
          } else if (targetPattern.includes("*")) {
            // Pattern with * in middle or start - convert to regex
            const regexPattern = targetPattern
              .replace(/[.+?^${}()|[\]\\]/g, '\\$&')
              .replace(/\*/g, '.*');
            const regex = new RegExp(`^${regexPattern}$`);
            isMatch = regex.test(toolIdentifier);
          } else {
            // Exact match
            isMatch = toolIdentifier === targetPattern;
          }
          
          if (isMatch) {
            allowedTools.set(tool.id, { policyId: rule.policy_id, policyName });
          }
        });
      }
    });

    return allowedTools;
  }, [policyRulesData, policyBindingsData, policiesData, toolsData]);

  // Generate initial edges from backend relationships
  // Only show necessary connections: Environment → Connection, Connection → Tool, Agent → Connection, Agent → Tool (only allowed)
  const initialEdges = useMemo(() => {
    const edges: Edge<CanvasEdgeData>[] = [];

    // 1. Environment → Connection (reversed from Connection.environment FK)
    (connectionsData || []).forEach((connection: any) => {
      const envId = connection.environment?.id || connection.environment_id;
      if (envId) {
        edges.push({
          id: `env-${envId}-server-${connection.id}`,
          source: `env-${envId}`,
          target: `server-${connection.id}`,
          type: "smoothstep",
          data: {
            type: "environment-server",
            config: { allowed: true },
          },
        });
      }
    });

    // 2. Connection → Tool (reversed from Tool.connection FK)
    (toolsData || []).forEach((tool: any) => {
      const connectionId = tool.connection?.id || tool.connection_id;
      if (connectionId) {
        edges.push({
          id: `server-${connectionId}-tool-${tool.id}`,
          source: `server-${connectionId}`,
          target: `tool-${tool.id}`,
          type: "smoothstep",
          data: {
            type: "server-tool",
            config: { allowed: true },
          },
        });
      }
    });

    // 3. Agent → Connection (server) - unchanged
    (agentsData || []).forEach((agent: any) => {
      const connectionId = agent.connection?.id || agent.connection_id;
      if (connectionId) {
        edges.push({
          id: `agent-${agent.id}-server-${connectionId}`,
          source: `agent-${agent.id}`,
          target: `server-${connectionId}`,
          type: "smoothstep",
          data: {
            type: "agent-server",
            config: { allowed: true },
          },
        });
      }
    });

    // 4. Agent → Tool (only allowed via PolicyRules)
    (agentsData || []).forEach((agent: any) => {
      const agentEnvId = agent.environment?.id || agent.environment_id;
      const allowedTools = getAllowedToolsForAgent(agent.id, agentEnvId);
      
      allowedTools.forEach((policyInfo, toolId) => {
        edges.push({
          id: `agent-${agent.id}-tool-${toolId}`,
          source: `agent-${agent.id}`,
          target: `tool-${toolId}`,
          type: "smoothstep",
          animated: true, // Animate policy-governed edges
          style: { 
            stroke: "#eab308", // Yellow for policy-governed
            strokeWidth: 2,
            strokeDasharray: "5,5", // Dashed line
          },
          label: policyInfo.policyName, // Show policy name as label
          labelStyle: { 
            fill: "#eab308", 
            fontSize: 10,
            fontWeight: 600,
          },
          labelBgStyle: {
            fill: "#1e293b",
            fillOpacity: 0.8,
          },
          data: {
            type: "agent-tool",
            config: { 
              allowed: true,
            },
            metadata: {
              policyId: policyInfo.policyId,
              policyName: policyInfo.policyName,
              policyGoverned: true,
            },
          },
        });
      });
    });

    // 5. Environment → Policy (reversed from Policy.environment FK)
    (policiesData || []).forEach((policy: any) => {
      const envId = policy.environment?.id || policy.environment_id;
      if (envId) {
        edges.push({
          id: `env-${envId}-policy-${policy.id}`,
          source: `env-${envId}`,
          target: `policy-${policy.id}`,
          type: "smoothstep",
          data: {
            type: "environment-policy",
            config: { allowed: true },
          },
        });
      }
    });

    // Note: Environment → Agent edge is NOT created
    // Agent can be created from Environment (via plus button), but the hierarchical edge is not shown
    // Agent relationships are shown via:
    // - Agent → Connection (server)
    // - Agent → Tool (if allowed by policy)

    // 6. Agent → Resource (only allowed via PolicyRules)
    (agentsData || []).forEach((agent: any) => {
      const agentEnvId = agent.environment?.id || agent.environment_id;
      const allowedResources = getAllowedResourcesForAgent(agent.id, agentEnvId);
      
      allowedResources.forEach((policyInfo, resourceId) => {
        edges.push({
          id: `agent-${agent.id}-resource-${resourceId}`,
          source: `agent-${agent.id}`,
          target: `resource-${resourceId}`,
          type: "smoothstep",
          animated: true, // Animate policy-governed edges
          style: { 
            stroke: "#f59e0b", // Amber for resource access
            strokeWidth: 2,
            strokeDasharray: "5,5", // Dashed line
          },
          label: `${policyInfo.policyName} (${policyInfo.action})`, // Show policy name and action
          labelStyle: { 
            fill: "#f59e0b", 
            fontSize: 10,
            fontWeight: 600,
          },
          labelBgStyle: {
            fill: "#1e293b",
            fillOpacity: 0.8,
          },
          data: {
            type: "agent-resource",
            config: { 
              allowed: true,
              permissions: policyInfo.action.split(','), // e.g., ["read", "write"]
            },
            metadata: {
              policyId: policyInfo.policyId,
              policyName: policyInfo.policyName,
              policyGoverned: true,
            },
          },
        });
      });
    });

    // 7. Environment → Resource (reversed from Resource.environment FK)
    (resourcesData || []).forEach((resource: any) => {
      const envId = resource.environment?.id || resource.environment_id;
      if (envId) {
        edges.push({
          id: `env-${envId}-resource-${resource.id}`,
          source: `env-${envId}`,
          target: `resource-${resource.id}`,
          type: "smoothstep",
          data: {
            type: "environment-resource",
            config: { allowed: true },
          },
        });
      }
    });

    // 8. Environment → Prompt (reversed from Prompt.environment FK)
    (promptsData || []).forEach((prompt: any) => {
      const envId = prompt.environment?.id || prompt.environment_id;
      if (envId) {
        edges.push({
          id: `env-${envId}-prompt-${prompt.id}`,
          source: `env-${envId}`,
          target: `prompt-${prompt.id}`,
          type: "smoothstep",
          data: {
            type: "environment-prompt",
            config: { allowed: true },
          },
        });
      }
    });

    // 9. Prompt → Resource (from Prompt.uses_resources, dashed line)
    (promptsData || []).forEach((prompt: any) => {
      const usesResources = prompt.uses_resources || [];
      // uses_resources is an array of resource names, need to find matching resources
      usesResources.forEach((resourceName: string) => {
        const matchingResource = (resourcesData || []).find((r: any) => r.name === resourceName);
        if (matchingResource) {
          edges.push({
            id: `prompt-${prompt.id}-resource-${matchingResource.id}`,
            source: `prompt-${prompt.id}`,
            target: `resource-${matchingResource.id}`,
            type: "smoothstep",
            animated: true,
            style: {
              stroke: "#f59e0b", // Amber for resource usage
              strokeWidth: 2,
              strokeDasharray: "5,5", // Dashed line
            },
            label: "uses",
            labelStyle: {
              fill: "#f59e0b",
              fontSize: 10,
              fontWeight: 600,
            },
            labelBgStyle: {
              fill: "#1e293b",
              fillOpacity: 0.8,
            },
            data: {
              type: "prompt-resource",
              config: { allowed: true },
              metadata: {
                resourceName,
              },
            },
          });
        }
      });
    });

    return edges;
  }, [agentsData, toolsData, connectionsData, environmentsData, policiesData, resourcesData, promptsData, getAllowedToolsForAgent, getAllowedResourcesForAgent]);

  // Load saved canvas state from backend
  const { data: savedCanvasState } = useQuery({
    queryKey: ["canvas-state", effectiveOrgId],
    queryFn: async () => {
      if (!effectiveOrgId) return null;
      try {
        const response = await canvasApi.getDefault(effectiveOrgId);
        return response.data?.state_json || null;
      } catch (error: any) {
        // 404 is ok - no saved state yet
        if (error.response?.status === 404) {
          return null;
        }
        console.error("Failed to load canvas state from backend:", error);
        // Fallback to localStorage
        try {
          const saved = localStorage.getItem(`canvas-state-${effectiveOrgId}`);
          if (saved) {
            return JSON.parse(saved);
          }
        } catch (e) {
          console.error("Failed to load canvas state from localStorage:", e);
        }
        return null;
      }
    },
    enabled: !!effectiveOrgId,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Load saved canvas state from localStorage (fallback)
  const loadCanvasState = useCallback(() => {
    // Prefer backend state
    if (savedCanvasState) {
      // Debug logging (development only)
      if (process.env.NODE_ENV === 'development') {
        console.log("Loading positions from backend:", 
          savedCanvasState.nodes?.map((n: any) => ({ id: n.id, pos: n.position }))
        );
      }
      return savedCanvasState;
    }
    
    // Fallback to localStorage
    if (!effectiveOrgId) return null;
    try {
      const saved = localStorage.getItem(`canvas-state-${effectiveOrgId}`);
      if (saved) {
        const state = JSON.parse(saved);
        
        // Debug logging (development only)
        if (process.env.NODE_ENV === 'development') {
          console.log("Loading positions from localStorage:", 
            state.nodes?.map((n: any) => ({ id: n.id, pos: n.position }))
          );
        }
        
        return state;
      }
    } catch (error) {
      console.error("Failed to load canvas state:", error);
    }
    return null;
  }, [effectiveOrgId, savedCanvasState]);
  
  // Restore viewport when canvas state loads
  useEffect(() => {
    const savedState = loadCanvasState();
    if (savedState?.viewport) {
      setViewport(savedState.viewport);
    }
  }, [loadCanvasState]);

  // Save canvas state mutation
  const saveCanvasStateMutation = useMutation({
    mutationFn: async (state: any) => {
      if (!effectiveOrgId) throw new Error("Organization ID is required");
      return canvasApi.saveDefault(effectiveOrgId, state);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["canvas-state", effectiveOrgId] });
    },
    onError: (error: any, state: any) => {
      console.error("Failed to save canvas state to backend:", error);
      // Fallback to localStorage
      if (effectiveOrgId && state) {
        try {
          localStorage.setItem(`canvas-state-${effectiveOrgId}`, JSON.stringify(state));
        } catch (e) {
          console.error("Failed to save canvas state to localStorage:", e);
        }
      }
    },
  });

  // Save canvas state to backend (with localStorage fallback)
  const saveCanvasState = useCallback((nodesToSave: Node<CanvasNodeData>[], edgesToSave: Edge<CanvasEdgeData>[]) => {
    if (!effectiveOrgId) return;
    
    // Debug logging (development only)
    if (process.env.NODE_ENV === 'development') {
      console.log("Saving positions:", 
        nodesToSave.map(n => ({ 
          id: n.id, 
          pos: n.position, 
          dirty: n.data.dirty 
        }))
      );
    }
    
    const state = {
      nodes: nodesToSave.map((n) => ({
        id: n.id,
        position: n.position || { x: 0, y: 0 }, // Ensure position exists
        data: {
          type: n.data.type,
          agentId: n.data.agentId,
          toolId: n.data.toolId,
          resourceId: n.data.resourceId,
          policyId: n.data.policyId,
          promptId: n.data.promptId,
          connectionId: n.data.connectionId,
          environmentId: n.data.environmentId,
          organizationId: n.data.organizationId,
          // Note: dirty flag is NOT saved to backend (it's local state only)
        },
      })),
      edges: edgesToSave.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type || "smoothstep", // Save edge type for ReactFlow rendering
        data: e.data,
      })),
      viewport: viewport, // Save current viewport instead of hardcoded
      groups: {},
      savedAt: new Date().toISOString(),
    };
    
    // Save to backend
    saveCanvasStateMutation.mutate(state);
    
    // Also save to localStorage as backup
    try {
      localStorage.setItem(`canvas-state-${effectiveOrgId}`, JSON.stringify(state));
    } catch (error) {
      console.error("Failed to save canvas state to localStorage:", error);
    }
  }, [effectiveOrgId, viewport, saveCanvasStateMutation]);

  // Merge saved positions with current data
  const mergedNodes = useMemo(() => {
    const savedState = loadCanvasState();
    if (!savedState || !savedState.nodes) return initialNodes;

    // Create a map of saved positions by entity ID
    const savedPositions = new Map<string, { x: number; y: number }>();
    savedState.nodes.forEach((savedNode: any) => {
      const entityId = savedNode.data.agentId || savedNode.data.toolId || 
                       savedNode.data.resourceId || savedNode.data.policyId ||
                       savedNode.data.promptId || savedNode.data.connectionId || 
                       savedNode.data.environmentId;
      if (entityId && savedNode.position) {
        const pos = savedNode.position;
        // Validate saved position
        if (typeof pos.x === 'number' && typeof pos.y === 'number' && 
            !isNaN(pos.x) && !isNaN(pos.y)) {
          savedPositions.set(savedNode.id, pos);
        }
      }
    });

    // Merge saved positions with initial nodes
    return initialNodes.map((node) => {
      const savedPosition = savedPositions.get(node.id);
      if (savedPosition) {
        // Double-check position is valid before using it
        if (typeof savedPosition.x === 'number' && typeof savedPosition.y === 'number' &&
            !isNaN(savedPosition.x) && !isNaN(savedPosition.y)) {
          return { ...node, position: savedPosition };
        }
      }
      // Ensure node position is valid
      const nodePos = node.position || { x: 0, y: 0 };
      if (typeof nodePos.x !== 'number' || typeof nodePos.y !== 'number' ||
          isNaN(nodePos.x) || isNaN(nodePos.y)) {
        return { ...node, position: { x: 0, y: 0 } };
      }
      return node;
    });
  }, [initialNodes, loadCanvasState]);

  // Calculate initial edges once
  const initialEdgesComputed = useMemo(() => {
    const nodeIds = new Set(mergedNodes.map((n) => n.id));
    const savedState = loadCanvasState();
    
    // Start with initial edges from backend relationships
    let edgesToUse = initialEdges.filter((e) => 
      nodeIds.has(e.source) && nodeIds.has(e.target)
    );
    
    // Merge with saved edges (user-created connections)
    if (savedState && savedState.edges) {
      const savedEdges = savedState.edges.filter((e: any) => 
        nodeIds.has(e.source) && nodeIds.has(e.target)
      );
      
      // Combine: use saved edges, but don't duplicate initial edges
      // Use a Set to track edge IDs by source-target combination to avoid duplicates
      const edgeIdMap = new Map<string, Edge<CanvasEdgeData>>();
      
      // Add initial edges first
      edgesToUse.forEach((e) => {
        const key = `${e.source}-${e.target}`;
        edgeIdMap.set(key, e);
      });
      
      // Add saved edges (they take precedence if they have the same source-target)
      savedEdges.forEach((e: any) => {
        const key = `${e.source}-${e.target}`;
        // Only add if not already present or if it's a different edge ID
        if (!edgeIdMap.has(key) || edgeIdMap.get(key)?.id !== e.id) {
          // Ensure saved edge has type attribute (required for ReactFlow rendering)
          const edgeWithType = {
            ...e,
            type: e.type || "smoothstep", // Add default type if missing
          } as Edge<CanvasEdgeData>;
          edgeIdMap.set(key, edgeWithType);
        }
      });
      
      edgesToUse = Array.from(edgeIdMap.values());
    }
    
    return edgesToUse;
  }, [mergedNodes, initialEdges, loadCanvasState]);

  const [nodes, setNodes, onNodesChangeInternal] = useNodesState(mergedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<CanvasEdgeData>>(initialEdgesComputed);

  // Enhanced onNodesChange with dirty flag tracking
  const onNodesChange = useCallback((changes: NodeChange<Node<CanvasNodeData>>[]) => {
    // Track position changes and mark nodes as dirty
    const positionChangeIds = new Set<string>();
    
    changes.forEach((change) => {
      if (change.type === 'position' && change.id) {
        positionChangeIds.add(change.id);
      }
    });
    
    // Mark nodes as dirty if their position changed
    if (positionChangeIds.size > 0) {
      setNodes((currentNodes) =>
        currentNodes.map((node) =>
          positionChangeIds.has(node.id)
            ? { ...node, data: { ...node.data, dirty: true } }
            : node
        )
      );
    }
    
    // Call React Flow's internal handler
    onNodesChangeInternal(changes);
  }, [onNodesChangeInternal, setNodes]);

  // Filter nodes and edges based on filter settings
  const filteredNodes = useMemo(() => {
    if (filteredNodeTypes.size === 0 && filteredStatuses.size === 0) {
      return nodes;
    }
    return nodes.filter((node) => {
      const nodeType = node.data?.type;
      const nodeStatus = node.data?.status || "unknown";
      
      // Filter by node type
      if (filteredNodeTypes.size > 0 && nodeType && !filteredNodeTypes.has(nodeType)) {
        return false;
      }
      
      // Filter by status
      if (filteredStatuses.size > 0 && !filteredStatuses.has(nodeStatus)) {
        return false;
      }
      
      return true;
    });
  }, [nodes, filteredNodeTypes, filteredStatuses]);

  const filteredEdges = useMemo(() => {
    // Always filter edges based on visible nodes
    const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
    
    return edges.filter((edge) => {
      // Only show edges where both source and target nodes are visible
      if (filteredNodeIds.size > 0 && filteredNodes.length < nodes.length) {
        if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) {
          return false;
        }
      }
      
      // Filter by edge type if any edge types are selected
      if (filteredEdgeTypes.size > 0 && edge.data?.type && !filteredEdgeTypes.has(edge.data.type)) {
        return false;
      }
      
      return true;
    });
  }, [edges, filteredEdgeTypes, filteredNodes, nodes]);

  // Use ref to access nodes without causing re-renders
  const nodesRef = useRef(nodes);
  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  // Handle creating new nodes (defined after setNodes is available)
  const handleCreateNode = useCallback((type: CanvasNodeType, position?: { x: number; y: number }, side?: "left" | "right", sourceNodeId?: string) => {
    // Use provided position or center of viewport
    const nodePosition = position || { x: 400, y: 300 };
    
    // If creating from a source node, try to get the environment and connection from it
    let environmentIdToPreselect: string | undefined = undefined;
    let connectionIdToPreselect: string | undefined = undefined;
    if (sourceNodeId) {
      const sourceNode = nodesRef.current.find((n) => n.id === sourceNodeId);
      if (sourceNode) {
        // Get environment from source node based on its type
        if (sourceNode.data.type === "environment") {
          // If source is an environment node, use its ID as preselected environment
          environmentIdToPreselect = sourceNode.data.environmentId || sourceNode.data.environment?.id;
        } else if (sourceNode.data.type === "server" && sourceNode.data.connection?.environment?.id) {
          environmentIdToPreselect = sourceNode.data.connection.environment.id;
          connectionIdToPreselect = sourceNode.data.connectionId; // Get the server's connection ID
        } else if (sourceNode.data.environmentId) {
          // For agents, tools, resources that have environmentId
          environmentIdToPreselect = sourceNode.data.environmentId;
        } else if (sourceNode.data.environment?.id) {
          environmentIdToPreselect = sourceNode.data.environment.id;
        }
        
        // Also get connection from tool/agent if creating from them
        if (sourceNode.data.type === "tool" && sourceNode.data.tool?.connection?.id) {
          connectionIdToPreselect = sourceNode.data.tool.connection.id;
        } else if (sourceNode.data.type === "agent" && sourceNode.data.agent?.connection?.id) {
          connectionIdToPreselect = sourceNode.data.agent.connection.id;
        }
      }
    }
    
    if (type === "agent") {
      // Open agent dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setPreselectedConnectionId(connectionIdToPreselect);
      setShowAgentDialog(true);
    } else if (type === "tool") {
      // Open tool dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setPreselectedConnectionId(connectionIdToPreselect);
      setShowToolDialog(true);
    } else if (type === "resource") {
      // Open resource dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setShowResourceDialog(true);
    } else if (type === "server") {
      // Open connection/server dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setShowConnectionDialog(true);
    } else if (type === "policy") {
      // Open policy dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setShowPolicyDialog(true);
    } else if (type === "prompt") {
      // Open prompt dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setPreselectedEnvironmentId(environmentIdToPreselect);
      setShowPromptDialog(true);
    } else if (type === "environment") {
      // Open environment dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setShowEnvironmentDialog(true);
    } else {
      // For other types, create a placeholder node
      // TODO: Implement dialogs for other types
      const newNodeId = `new-${type}-${Date.now()}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: nodePosition,
        data: {
          type,
          label: `New ${type}`,
          status: "unknown",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Automatically create connection if source node is provided
        if (sourceNodeId) {
          const sourceNode = nds.find((n) => n.id === sourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = side === "left" ? newNodeId : sourceNodeId;
            const targetId = side === "left" ? sourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = side === "left" ? type : sourceNode.data.type;
            const targetType = side === "left" ? sourceNode.data.type : type;
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              // Skip creating edge for invalid connections
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated - use a small delay to ensure nodes exist
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handleCreateNode:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
    }
  }, [setNodes, setEdges]);

  // Add onCreateNode callback and connection info to all nodes after they're initialized
  // Use useMemo to avoid infinite loops - only recalculate when edges or handleCreateNode changes
  const nodesWithConnectionsSet = useMemo(() => {
    const set = new Set<string>();
    edges.forEach((edge) => {
      set.add(edge.source);
      set.add(edge.target);
    });
    return set;
  }, [edges]);

  // Node action handler (test, sync, run, ping) - MUST be defined before useEffect
  const handleNodeAction = useCallback(async (action: string, entityId?: string) => {
    if (!effectiveOrgId || !entityId) return;

    // Find the entity name from nodes using ref
    const node = nodesRef.current.find((n) => 
      n.data.connectionId === entityId || 
      n.data.toolId === entityId ||
      n.data.agentId === entityId
    );
    const entityName = node?.data.label || "Unknown";

    if (action === "test") {
      // Open test connection modal
      setSelectedActionEntityId(entityId);
      setSelectedActionEntityName(entityName);
      setShowTestModal(true);
    } else if (action === "sync") {
      // Open sync tools modal
      setSelectedActionEntityId(entityId);
      setSelectedActionEntityName(entityName);
      setShowSyncModal(true);
    } else if (action === "run") {
      // Open run tool modal
      setSelectedActionEntityId(entityId);
      setSelectedActionEntityName(entityName);
      setShowRunModal(true);
    } else if (action === "ping") {
      // Open ping agent modal
      setSelectedActionEntityId(entityId);
      setSelectedActionEntityName(entityName);
      setShowPingModal(true);
    }
  }, [effectiveOrgId, queryClient]);

  // Serialize edges to detect actual changes (not reference changes)
  const edgesSerialized = useMemo(() => {
    const connectionsSet = new Set<string>();
    edges.forEach((edge) => {
      connectionsSet.add(edge.source);
      connectionsSet.add(edge.target);
    });
    return {
      length: edges.length,
      connectionsStr: Array.from(connectionsSet).sort().join(","),
    };
  }, [edges]);

  // Use refs to track changes and prevent infinite loops
  const lastHandleCreateNodeRef = useRef(handleCreateNode);
  const lastHandleNodeActionRef = useRef(handleNodeAction);
  const lastEdgesSerializedRef = useRef<{ length: number; connectionsStr: string }>({ length: 0, connectionsStr: "" });
  
  useEffect(() => {
    // Check if anything actually changed
    const handleCreateNodeChanged = lastHandleCreateNodeRef.current !== handleCreateNode;
    const handleNodeActionChanged = lastHandleNodeActionRef.current !== handleNodeAction;
    const edgesChanged = 
      lastEdgesSerializedRef.current.length !== edgesSerialized.length ||
      lastEdgesSerializedRef.current.connectionsStr !== edgesSerialized.connectionsStr;
    
    // Only update if something actually changed
    if (!handleCreateNodeChanged && !handleNodeActionChanged && !edgesChanged) {
      return; // Nothing changed, skip update
    }
    
    // Update refs
    lastHandleCreateNodeRef.current = handleCreateNode;
    lastHandleNodeActionRef.current = handleNodeAction;
    lastEdgesSerializedRef.current = edgesSerialized;
    
    // Recalculate nodesWithConnectionsSet from edgesSerialized
    // We can reconstruct the set from the serialized string
    const currentConnectionsSet = new Set<string>();
    if (edgesSerialized.connectionsStr) {
      edgesSerialized.connectionsStr.split(",").forEach((nodeId) => {
        if (nodeId) currentConnectionsSet.add(nodeId);
      });
    }
    
    setNodes((currentNodes) => {
      // Check if any node needs updating
      const needsUpdate = currentNodes.some((node) => {
        const hasConnections = currentConnectionsSet.has(node.id);
        const onCreateNodeChanged = node.data.onCreateNode !== handleCreateNode;
        const onActionChanged = node.data.onAction !== handleNodeAction;
        const hasConnectionsChanged = node.data.hasConnections !== hasConnections;
        return onCreateNodeChanged || onActionChanged || hasConnectionsChanged;
      });

      if (!needsUpdate) {
        return currentNodes; // Return same reference to prevent re-render
      }

      return currentNodes.map((node) => {
        const hasConnections = currentConnectionsSet.has(node.id);
        return {
          ...node,
          data: {
            ...node.data,
            onCreateNode: handleCreateNode,
            onAction: handleNodeAction,
            hasConnections,
          },
        };
      });
    });
  }, [setNodes, handleCreateNode, handleNodeAction, edgesSerialized]);


  // Save state when nodes or edges change (debounced)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveCanvasState(nodes, edges);
    }, 1000); // Debounce: save 1 second after last change

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, saveCanvasState]);

  // Track initial load state
  const initialLoadDoneRef = useRef(false);
  
  // Robust merge function
  const mergeFromBackend = useCallback((
    currentNodes: Node<CanvasNodeData>[],
    backendNodes: Node<CanvasNodeData>[],
    options: { overwritePosition: boolean }
  ): Node<CanvasNodeData>[] => {
    return backendNodes.map((backendNode) => {
      const localNode = currentNodes.find((n) => n.id === backendNode.id);
      
      if (!localNode) {
        // Node is new → use position from backend, mark as clean
        return { 
          ...backendNode, 
          data: { ...backendNode.data, dirty: false }
        };
      }
      
      if (options.overwritePosition && !localNode.data.dirty) {
        // Initial load: overwrite position only if user never moved it
        return { 
          ...backendNode, 
          position: backendNode.position || localNode.position,
          data: { ...backendNode.data, dirty: false }
        };
      }
      
      // Ongoing operation: NEVER overwrite position
      // Keep local position and dirty flag
      return { 
        ...backendNode, 
        position: localNode.position,
        data: { ...backendNode.data, dirty: localNode.data.dirty ?? false }
      };
    });
  }, []);

  // Initialize nodes on mount and when mergedNodes change
  useEffect(() => {
    setNodes((currentNodes) => {
      if (!initialLoadDoneRef.current || currentNodes.length === 0) {
        // Initial load: merge with position overwrite
        initialLoadDoneRef.current = true;
        const merged = mergeFromBackend(currentNodes, mergedNodes, { overwritePosition: true });
        
        // Debug logging (development only)
        if (process.env.NODE_ENV === 'development') {
          console.log("Initial load - Merging positions from backend:", 
            merged.map(n => ({ id: n.id, pos: n.position, dirty: n.data.dirty }))
          );
        }
        
        return merged.length > 0 ? merged : currentNodes;
      } else {
        // Subsequent updates: merge WITHOUT position overwrite
        const merged = mergeFromBackend(currentNodes, mergedNodes, { overwritePosition: false });
        
        // Add any new nodes that don't exist yet (user-created nodes)
        const existingIds = new Set(merged.map((n) => n.id));
        const newNodes = currentNodes.filter((n) => !existingIds.has(n.id));
        
        // Debug logging (development only)
        if (process.env.NODE_ENV === 'development') {
          const dirtyNodes = merged.filter(n => n.data.dirty);
          if (dirtyNodes.length > 0) {
            console.log("Preserving dirty node positions:", 
              dirtyNodes.map(n => ({ id: n.id, pos: n.position }))
            );
          }
        }
        
        return [...merged, ...newNodes];
      }
    });
  }, [mergedNodes, setNodes, mergeFromBackend]);

  // Update edges when initial edges change (merge with saved edges)
  useEffect(() => {
    const nodeIds = new Set(nodes.map((n) => n.id));
    const validInitialEdges = initialEdges.filter((e) => 
      nodeIds.has(e.source) && nodeIds.has(e.target)
    );
    
    // Merge initial edges with current edges (avoid duplicates)
    // Use both ID and source-target combination to detect duplicates
    const currentEdgeIds = new Set(edges.map((e) => e.id));
    const currentEdgeKeys = new Set(edges.map((e) => `${e.source}-${e.target}`));
    
    const newInitialEdges = validInitialEdges.filter((e) => {
      const edgeKey = `${e.source}-${e.target}`;
      return !currentEdgeIds.has(e.id) && !currentEdgeKeys.has(edgeKey);
    });
    
    if (newInitialEdges.length > 0) {
      setEdges((eds) => {
        // Double-check to avoid duplicates
        const existingIds = new Set(eds.map((e) => e.id));
        const existingKeys = new Set(eds.map((e) => `${e.source}-${e.target}`));
        const trulyNew = newInitialEdges.filter((e) => {
          const edgeKey = `${e.source}-${e.target}`;
          return !existingIds.has(e.id) && !existingKeys.has(edgeKey);
        });
        return [...eds, ...trulyNew];
      });
    }
  }, [initialEdges, nodes, edges, setEdges]);

  const saveEdgeToBackend = useCallback(async (edge: Edge<CanvasEdgeData>) => {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    const targetNode = nodes.find((n) => n.id === edge.target);

    if (!sourceNode || !targetNode || !effectiveOrgId) return;

    try {
      // Handle different edge types
      if (edge.data?.type === "agent-tool" && sourceNode.data.type === "agent" && targetNode.data.type === "tool") {
        // Add tool to agent's capabilities (or create a separate allowlist mechanism)
        // For now, we'll update the agent's connection if it's a tool-server connection
        const agentId = sourceNode.data.agentId;
        const toolId = targetNode.data.toolId;
        
        if (agentId && toolId) {
          // TODO: Implement tool allowlist in backend
          // For now, we can store this in agent metadata or create a separate model
          console.log(`Would add tool ${toolId} to agent ${agentId} allowlist`);
        }
      } else if (edge.data?.type === "agent-server" && sourceNode.data.type === "agent" && targetNode.data.type === "server") {
        // Update agent's connection
        const agentId = sourceNode.data.agentId;
        const connectionId = targetNode.data.connectionId;
        
        if (agentId && connectionId) {
          await api.patch(`/orgs/${effectiveOrgId}/agents/${agentId}/`, {
            connection_id: connectionId,
          });
          queryClient.invalidateQueries({ queryKey: ["agents", effectiveOrgId] });
        }
      } else if (edge.data?.type === "environment-server" && sourceNode.data.type === "environment" && targetNode.data.type === "server") {
        // Update connection's environment (reversed: Environment → Connection)
        const connectionId = targetNode.data.connectionId;
        const environmentId = sourceNode.data.environmentId;
        
        if (connectionId && environmentId) {
          await api.patch(`/orgs/${effectiveOrgId}/connections/${connectionId}/`, {
            environment_id: environmentId,
          });
          queryClient.invalidateQueries({ queryKey: ["connections", effectiveOrgId] });
        }
      } else if (edge.data?.type === "server-tool" && sourceNode.data.type === "server" && targetNode.data.type === "tool") {
        // Update tool's connection (reversed: Connection → Tool)
        const toolId = targetNode.data.toolId;
        const connectionId = sourceNode.data.connectionId;
        
        if (toolId && connectionId) {
          await api.patch(`/orgs/${effectiveOrgId}/tools/${toolId}/`, {
            connection_id: connectionId,
          });
          queryClient.invalidateQueries({ queryKey: ["tools", effectiveOrgId] });
        }
      } else if (edge.data?.type === "environment-policy" && sourceNode.data.type === "environment" && targetNode.data.type === "policy") {
        // Update policy's environment (reversed: Environment → Policy)
        const policyId = targetNode.data.policyId;
        const environmentId = sourceNode.data.environmentId;
        
        if (policyId && environmentId) {
          await api.patch(`/orgs/${effectiveOrgId}/policies/${policyId}/`, {
            environment_id: environmentId,
          });
          queryClient.invalidateQueries({ queryKey: ["policies", effectiveOrgId] });
        }
      } else if (edge.data?.type === "environment-resource" && sourceNode.data.type === "environment" && targetNode.data.type === "resource") {
        // Update resource's environment (reversed: Environment → Resource)
        const resourceId = targetNode.data.resourceId;
        const environmentId = sourceNode.data.environmentId;
        
        if (resourceId && environmentId) {
          await api.patch(`/orgs/${effectiveOrgId}/resources/${resourceId}/`, {
            environment_id: environmentId,
          });
          queryClient.invalidateQueries({ queryKey: ["resources", effectiveOrgId] });
        }
      } else if (edge.data?.type === "environment-prompt" && sourceNode.data.type === "environment" && targetNode.data.type === "prompt") {
        // Update prompt's environment (reversed: Environment → Prompt)
        const promptId = targetNode.data.promptId;
        const environmentId = sourceNode.data.environmentId;
        
        if (promptId && environmentId) {
          await api.patch(`/orgs/${effectiveOrgId}/prompts/${promptId}/`, {
            environment_id: environmentId,
          });
          queryClient.invalidateQueries({ queryKey: ["prompts", effectiveOrgId] });
        }
      } else if (edge.data?.type === "prompt-resource" && sourceNode.data.type === "prompt" && targetNode.data.type === "resource") {
        // Update prompt's uses_resources (add resource name to array)
        const promptId = sourceNode.data.promptId;
        const resourceName = targetNode.data.resource?.name || targetNode.data.label;
        
        if (promptId && resourceName) {
          // Get current prompt data to update uses_resources
          const promptData = sourceNode.data.prompt;
          const currentUsesResources = promptData?.uses_resources || [];
          
          // Add resource name if not already in list
          if (!currentUsesResources.includes(resourceName)) {
            await api.patch(`/orgs/${effectiveOrgId}/prompts/${promptId}/`, {
              uses_resources: [...currentUsesResources, resourceName],
            });
            queryClient.invalidateQueries({ queryKey: ["prompts", effectiveOrgId] });
          }
        }
      } else if (edge.data?.type === "policy-agent" && sourceNode.data.type === "policy" && targetNode.data.type === "agent") {
        // Create policy binding
        const policyId = sourceNode.data.policyId;
        const agentId = targetNode.data.agentId;
        
        if (policyId && agentId) {
          // TODO: Implement policy binding creation
          console.log(`Would bind policy ${policyId} to agent ${agentId}`);
        }
      }
    } catch (error) {
      console.error("Failed to save edge to backend:", error);
    }
  }, [nodes, effectiveOrgId, queryClient]);

  const onConnect = useCallback(
    async (params: Connection) => {
      const sourceNode = nodes.find((n) => n.id === params.source);
      const targetNode = nodes.find((n) => n.id === params.target);

      if (!sourceNode || !targetNode) {
        console.warn("Source or target node not found");
        return;
      }

      // Validate connection is logically valid
      const sourceType = sourceNode.data.type;
      const targetType = targetNode.data.type;
      
      if (!isValidEdgeConnection(sourceType, targetType)) {
        console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
        // Show error to user (could use a toast notification)
        alert(`Cannot connect ${sourceType} to ${targetType}. This connection is not logically valid.`);
        return;
      }

      // Get default edge type for this connection
      const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
      if (!defaultEdgeType) {
        console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
        alert(`Cannot determine edge type for ${sourceType} -> ${targetType}`);
        return;
      }

      const edgeType: CanvasEdgeData["type"] = defaultEdgeType;

      // Generate consistent edge ID based on source and target node IDs
      const edgeId = `${params.source}-${params.target}`;

      const newEdge: Edge<CanvasEdgeData> = {
        ...params,
        id: edgeId,
        type: "smoothstep",
        animated: false,
        style: { stroke: "#a855f7", strokeWidth: 2 },
        data: {
          type: edgeType,
          config: {
            allowed: true,
          },
        },
      };

      setEdges((eds) => {
        // Check if edge already exists
        const edgeExists = eds.some((e) => e.id === newEdge.id);
        if (edgeExists) {
          console.warn("Edge already exists:", newEdge.id);
          return eds;
        }
        console.log("Creating new edge via drag & drop:", newEdge);
        return addEdge(newEdge, eds);
      });
      
      // Save to backend
      await saveEdgeToBackend(newEdge);
    },
    [nodes, setEdges, saveEdgeToBackend]
  );

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node<CanvasNodeData>) => {
    setSelectedNode(node);
    setSelectedEdge(null); // Close edge sidebar when selecting node
    setSidebarOpen(true);
    setEdgeSidebarOpen(false);
  }, []);

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["agents", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["tools", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["resources", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["policies", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["prompts", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["connections", effectiveOrgId] });
    queryClient.invalidateQueries({ queryKey: ["environments", effectiveOrgId] });
  }, [queryClient, effectiveOrgId]);

  const handleAutoArrange = useCallback(() => {
    // Group nodes by LANE (not by type!) to prevent overlaps
    const nodesByLane = new Map<string, Node<CanvasNodeData>[]>();
    
    nodes.forEach((node) => {
      const lane = getLaneForNodeType(node.data.type);
      if (lane) {
        const laneId = lane.id;
        if (!nodesByLane.has(laneId)) {
          nodesByLane.set(laneId, []);
        }
        nodesByLane.get(laneId)!.push(node);
      }
    });

    // Sort nodes within each lane by type (so similar nodes stay together)
    nodesByLane.forEach((nodesInLane, laneId) => {
      nodesInLane.sort((a, b) => {
        // Sort by type first, then by label
        if (a.data.type !== b.data.type) {
          return a.data.type.localeCompare(b.data.type);
        }
        return a.data.label.localeCompare(b.data.label);
      });
    });

    // Apply auto-layout positions to each node
    const updatedNodes = nodes.map((node) => {
      const lane = getLaneForNodeType(node.data.type);
      if (!lane) {
        return node; // Keep original position if no lane found
      }
      
      // Get all nodes in the same lane (already sorted)
      const nodesInSameLane = nodesByLane.get(lane.id) || [];
      
      // Find index of this node within its lane
      const indexInLane = nodesInSameLane.findIndex((n) => n.id === node.id);
      
      if (indexInLane === -1) {
        return node; // Keep original if not found
      }
      
      // Calculate position based on lane and index
      const newPosition = getAutoLayoutPosition(node.data.type, indexInLane);
      
      return {
        ...node,
        position: newPosition,
      };
    });

    setNodes(updatedNodes);
    
    // Save state after auto-arranging
    setTimeout(() => {
      saveCanvasState(updatedNodes, edges);
    }, 100);
  }, [nodes, edges, setNodes, saveCanvasState]);

  const handleExport = useCallback(() => {
    const canvasState: CanvasState = {
      nodes: nodes.map((n) => ({
        ...n,
        data: n.data,
      })),
      edges: edges.map((e) => ({
        ...e,
        data: e.data,
      })),
      viewport: { x: 0, y: 0, zoom: 1 },
      groups: {},
    };

    const exportData = {
      version: "1.0.0",
      exportedAt: new Date().toISOString(),
      organizationId: effectiveOrgId || "",
      canvas: canvasState,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agentxsuite-canvas-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [nodes, edges, orgId]);


  const handleResourceCreated = useCallback((resource: any) => {
    if (pendingPosition && pendingNodeType === "resource") {
      const newNodeId = `resource-${resource.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "resource",
          resourceId: resource.id,
          resource,
          label: resource.name,
          status: resource.enabled ? "connected" : "disabled",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Create connection if source node is provided - use callback to get current nodes
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = pendingSide === "left" ? "resource" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "resource";
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              // Skip creating edge for invalid connections
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handleResourceCreated:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

  const handlePromptCreated = useCallback((prompt: any) => {
    if (pendingPosition && pendingNodeType === "prompt") {
      const newNodeId = `prompt-${prompt.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "prompt",
          promptId: prompt.id,
          prompt,
          label: prompt.name,
          status: prompt.enabled ? "connected" : "disabled",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
          
        // Create connection if source node is provided
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = pendingSide === "left" ? "prompt" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "prompt";
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handlePromptCreated:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

  const handlePolicyCreated = useCallback((policy: any) => {
    if (pendingPosition && pendingNodeType === "policy") {
      const newNodeId = `policy-${policy.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "policy",
          policyId: policy.id,
          policy,
          label: policy.name,
          status: policy.is_active ? "connected" : "disabled",
          onCreateNode: handleCreateNode,
          hasConnections: false,
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Create connection if source node is provided
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            const sourceType = pendingSide === "left" ? "policy" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "policy";
            
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: { type: edgeType, config: { allowed: true } },
            };
            
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

  const handleConnectionCreated = useCallback((connection: any) => {
    if (pendingPosition && pendingNodeType === "server") {
      const newNodeId = `server-${connection.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "server",
          connectionId: connection.id,
          connection,
          label: connection.name,
          status: connection.status === "ok" ? "connected" : connection.status === "fail" ? "error" : "unknown",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Create connection if source node is provided - use callback to get current nodes
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = pendingSide === "left" ? "server" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "server";
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              // Skip creating edge for invalid connections
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handleConnectionCreated:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

  const handleEnvironmentCreated = useCallback(async (createdEnv: any) => {
    if (!pendingPosition || pendingNodeType !== "environment" || !createdEnv) {
      // Clear pending state if conditions not met
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
      return;
    }

    // Use the created environment directly
    const newNodeId = `env-${createdEnv.id}`;
    
    // Check if node already exists
    const nodeExists = nodes.some((n) => n.id === newNodeId);
    if (nodeExists) {
      console.warn("Environment node already exists:", newNodeId);
      // Invalidate queries to refresh data
      await queryClient.invalidateQueries({ queryKey: ["environments", effectiveOrgId] });
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
      return;
    }
    
    const newNode: Node<CanvasNodeData> = {
      id: newNodeId,
      type: "canvasNode",
      position: pendingPosition,
      data: {
        type: "environment",
        environmentId: createdEnv.id,
        environment: createdEnv,
        label: createdEnv.name,
        status: "connected",
        onCreateNode: handleCreateNode,
        hasConnections: false, // Newly created node has no connections yet
      },
    };
    
    setNodes((nds) => {
      const updatedNodes = [...nds, newNode];
        
      // Create connection if source node is provided - use callback to get current nodes
      if (pendingSourceNodeId && pendingSide) {
        const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
        if (sourceNode) {
          // Determine edge direction based on side
          const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
          const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
          
          // Determine edge type based on node types
          const sourceType = pendingSide === "left" ? "environment" : sourceNode.data.type;
          const targetType = pendingSide === "left" ? sourceNode.data.type : "environment";
          
          // Validate connection is logically valid
          if (!isValidEdgeConnection(sourceType, targetType)) {
            console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
            // Skip creating edge for invalid connections
            return updatedNodes;
          }

          // Get default edge type for this connection
          const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
          if (!defaultEdgeType) {
            console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
            return updatedNodes;
          }

          const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
          
          // Generate consistent edge ID based on source and target node IDs
          const edgeId = `${sourceId}-${targetId}`;
          
          const newEdge: Edge<CanvasEdgeData> = {
            id: edgeId,
            source: sourceId,
            target: targetId,
            type: "smoothstep",
            animated: false,
            style: { stroke: "#a855f7", strokeWidth: 2 },
            data: {
              type: edgeType,
              config: {
                allowed: true,
              },
            },
          };
          
          // Create edge after nodes are updated
          const timeoutId = setTimeout(() => {
            edgeTimeoutsRef.current.delete(timeoutId);
            setEdges((eds) => {
              // Check if edge already exists
              const edgeExists = eds.some((e) => e.id === newEdge.id);
              if (edgeExists) {
                console.warn("Edge already exists:", newEdge.id);
                return eds;
              }
              console.log("Creating new edge from handleEnvironmentCreated:", {
                id: newEdge.id,
                source: newEdge.source,
                target: newEdge.target,
                type: newEdge.data?.type,
                sourceType,
                targetType,
              });
              return addEdge(newEdge, eds);
            });
          }, 50);
          edgeTimeoutsRef.current.add(timeoutId);
        }
      }
      
      return updatedNodes;
    });
    
    // Invalidate queries in the background to refresh data (don't await)
    queryClient.invalidateQueries({ queryKey: ["environments", effectiveOrgId] });
    
    // Clear pending state
    setPendingNodeType(null);
    setPendingPosition(null);
    setPendingSourceNodeId(undefined);
    setPendingSide(undefined);
    setPreselectedEnvironmentId(undefined);
    setPreselectedConnectionId(undefined);
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode, effectiveOrgId, queryClient]);

  const handleToolCreated = useCallback((tool: any) => {
    if (pendingPosition && pendingNodeType === "tool") {
      const newNodeId = `tool-${tool.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "tool",
          toolId: tool.id,
          tool,
          label: tool.name,
          status: tool.enabled ? "connected" : "disabled",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Create connection if source node is provided - use callback to get current nodes
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = pendingSide === "left" ? "tool" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "tool";
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              // Skip creating edge for invalid connections
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handleToolCreated:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

  const handleAgentCreated = useCallback((agent: any) => {
    if (pendingPosition && pendingNodeType === "agent") {
      const newNodeId = `agent-${agent.id}`;
      const newNode: Node<CanvasNodeData> = {
        id: newNodeId,
        type: "canvasNode",
        position: pendingPosition,
        data: {
          type: "agent",
          agentId: agent.id,
          agent,
          label: agent.name,
          status: agent.enabled ? "connected" : "disabled",
          onCreateNode: handleCreateNode,
          hasConnections: false, // Newly created node has no connections yet
        },
      };
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        
        // Create connection if source node is provided - use callback to get current nodes
        if (pendingSourceNodeId && pendingSide) {
          const sourceNode = nds.find((n) => n.id === pendingSourceNodeId);
          if (sourceNode) {
            // Determine edge direction based on side
            const sourceId = pendingSide === "left" ? newNodeId : pendingSourceNodeId;
            const targetId = pendingSide === "left" ? pendingSourceNodeId : newNodeId;
            
            // Determine edge type based on node types
            const sourceType = pendingSide === "left" ? "agent" : sourceNode.data.type;
            const targetType = pendingSide === "left" ? sourceNode.data.type : "agent";
            
            // Validate connection is logically valid
            if (!isValidEdgeConnection(sourceType, targetType)) {
              console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
              // Skip creating edge for invalid connections
              return updatedNodes;
            }

            // Get default edge type for this connection
            const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
            if (!defaultEdgeType) {
              console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
              return updatedNodes;
            }

            const edgeType: CanvasEdgeData["type"] = defaultEdgeType;
            
            // Generate consistent edge ID based on source and target node IDs
            const edgeId = `${sourceId}-${targetId}`;
            
            const newEdge: Edge<CanvasEdgeData> = {
              id: edgeId,
              source: sourceId,
              target: targetId,
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
              data: {
                type: edgeType,
                config: {
                  allowed: true,
                },
              },
            };
            
            // Create edge after nodes are updated
            const timeoutId = setTimeout(() => {
              edgeTimeoutsRef.current.delete(timeoutId);
              setEdges((eds) => {
                // Check if edge already exists
                const edgeExists = eds.some((e) => e.id === newEdge.id);
                if (edgeExists) {
                  console.warn("Edge already exists:", newEdge.id);
                  return eds;
                }
                console.log("Creating new edge from handleAgentCreated:", {
                  id: newEdge.id,
                  source: newEdge.source,
                  target: newEdge.target,
                  type: newEdge.data?.type,
                  sourceType,
                  targetType,
                });
                return addEdge(newEdge, eds);
              });
            }, 50);
            edgeTimeoutsRef.current.add(timeoutId);
          }
        }
        
        return updatedNodes;
      });
      
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
      setPreselectedEnvironmentId(undefined);
      setPreselectedConnectionId(undefined);
    }
    queryClient.invalidateQueries({ queryKey: ["agents", effectiveOrgId] });
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode, queryClient, effectiveOrgId]);

  const onEdgeClick = useCallback((event: React.MouseEvent, edge: Edge<CanvasEdgeData>) => {
    setSelectedEdge(edge);
    setSelectedNode(null); // Close node sidebar when selecting edge
    setEdgeSidebarOpen(true);
    setSidebarOpen(false);
  }, []);

  const onPaneClick = useCallback((event: React.MouseEvent) => {
    // Check if right-click or Ctrl/Cmd+click for context menu
    if (event.button === 2 || (event.ctrlKey || event.metaKey)) {
      return;
    }
    // Close sidebars on canvas click
    setSidebarOpen(false);
    setEdgeSidebarOpen(false);
    setSelectedNode(null);
    setSelectedEdge(null);
  }, []);

  const handleEdgeUpdate = useCallback((edgeId: string, data: Partial<CanvasEdgeData>) => {
    setEdges((eds) =>
      eds.map((e) =>
        e.id === edgeId
          ? {
              ...e,
              data: {
                ...(e.data || {}),
                ...data,
              } as CanvasEdgeData,
            }
          : e
      )
    );
  }, [setEdges]);

  const handleEdgeDelete = useCallback((edgeId: string) => {
    setEdges((eds) => eds.filter((e) => e.id !== edgeId));
    setEdgeSidebarOpen(false);
    setSelectedEdge(null);
  }, [setEdges]);

  const handleEdgeUpdateSourceTarget = useCallback(async (edgeId: string, newSource: string, newTarget: string) => {
    const edge = edges.find((e) => e.id === edgeId);
    if (!edge) return;

    const sourceNode = nodes.find((n) => n.id === newSource);
    const targetNode = nodes.find((n) => n.id === newTarget);
    
    if (!sourceNode || !targetNode) {
      console.warn("Source or target node not found");
      return;
    }

    // Validate edge type is still valid for new source/target
    const sourceType = sourceNode.data.type;
    const targetType = targetNode.data.type;
    const currentEdgeType = edge.data?.type;
    
    let finalEdgeType = currentEdgeType;
    if (currentEdgeType) {
      const validTypes = getValidEdgeTypes(sourceType, targetType);
      if (!validTypes.includes(currentEdgeType)) {
        // If current type is invalid, use default type or first valid type
        finalEdgeType = validTypes.length > 0 ? validTypes[0] : currentEdgeType;
        console.warn(`Edge type ${currentEdgeType} invalid for ${sourceType} → ${targetType}, changing to ${finalEdgeType}`);
      }
    }

    // Update edge with new source and target
    const newEdgeId = `${newSource}-${newTarget}`;
    setEdges((eds) => {
      return eds.map((e) =>
        e.id === edgeId
          ? {
              ...e,
              id: newEdgeId,
              source: newSource,
              target: newTarget,
              data: {
                ...(e.data || {}),
                type: finalEdgeType,
              } as CanvasEdgeData,
            }
          : e
      );
    });
    
    // Update selected edge if it's the one being modified
    if (selectedEdge?.id === edgeId) {
      const updatedEdge: Edge<CanvasEdgeData> = {
        ...selectedEdge,
        id: newEdgeId,
        source: newSource,
        target: newTarget,
        data: {
          ...(selectedEdge.data || {}),
          type: finalEdgeType,
        } as CanvasEdgeData,
      };
      setSelectedEdge(updatedEdge);
      
      // Sync to backend if needed
      if (effectiveOrgId) {
        try {
          // Delete old edge from backend if it exists
          try {
            await api.delete(`/orgs/${effectiveOrgId}/canvas/edges/${edgeId}/`);
          } catch (error: any) {
            // Ignore 404 errors (edge might not exist in backend)
            if (error.response?.status !== 404) {
              console.warn("Failed to delete old edge from backend:", error);
            }
          }
          
          // Create new edge in backend
          await api.post(`/orgs/${effectiveOrgId}/canvas/edges/`, {
            id: newEdgeId,
            source: newSource,
            target: newTarget,
            type: finalEdgeType,
            config: updatedEdge.data?.config,
            metadata: updatedEdge.data?.metadata,
          });
          
          // Also sync to backend models if needed
          await saveEdgeToBackend(updatedEdge);
        } catch (error) {
          console.error("Failed to sync edge source/target change to backend:", error);
        }
      }
    }
  }, [setEdges, nodes, selectedEdge, edges, effectiveOrgId, saveEdgeToBackend]);

  // Close filter menu when clicking outside
  useEffect(() => {
    if (!showFilter) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (!filterMenuRef.current || !event.target) return;

      const target = event.target as HTMLElement;
      
      // Check if click is inside the filter menu
      if (filterMenuRef.current.contains(target)) {
        return; // Click is inside menu, don't close
      }

      // Check if click is on the filter button (should toggle menu, not close)
      const isFilterButton = target.closest('button')?.textContent?.includes('Filter') || 
                             target.closest('button')?.querySelector('svg');
      if (isFilterButton && target.closest('.relative')) {
        return; // Click is on filter button, let button handler manage it
      }

      // Click is outside menu and not on filter button, close menu
      setShowFilter(false);
    };

    // Use a small timeout to avoid immediate closing when opening the menu
    const timeoutId = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside, true);
    }, 10);
    
    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener("mousedown", handleClickOutside, true);
    };
  }, [showFilter]);

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-slate-950 w-full">
      <ReactFlowProvider>
        <div className="flex-1 relative">
          <ReactFlow
            nodes={filteredNodes}
            edges={filteredEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            connectionLineStyle={{ stroke: "#a855f7", strokeWidth: 2 }}
            snapToGrid={true}
            snapGrid={[15, 15]}
            defaultEdgeOptions={{
              type: "smoothstep",
              animated: false,
              style: { stroke: "#a855f7", strokeWidth: 2 },
            }}
            onNodeClick={onNodeClick}
            onEdgeClick={onEdgeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            defaultViewport={viewport}
            onViewportChange={(newViewport) => setViewport(newViewport)}
            fitView={false}
            className="bg-slate-950"
            deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background />
            <Controls 
              className="[&_button]:bg-slate-800 [&_button]:border-slate-700 [&_button]:text-slate-200 hover:[&_button]:bg-slate-700 [&_button]:shadow-lg"
            />
            <MiniMap
              nodeColor={(node) => {
                try {
                  if (!node?.data) return "#64748b";
                  const nodeData = node.data as CanvasNodeData;
                  const nodeType = nodeData.type;
                  // Use accent colors from visual config for consistency
                  const colorMap: Record<string, string> = {
                    environment: "#64748b", // Slate (subtle)
                    server: "#14b8a6", // Teal (PROMINENT)
                    agent: "#a855f7", // Purple (PROMINENT)
                    tool: "#3b82f6", // Blue
                    policy: "#eab308", // Yellow
                    resource: "#f97316", // Orange
                    organization: "#6366f1", // Indigo
                    prompt: "#ec4899", // Pink
                  };
                  return colorMap[nodeType] || "#64748b";
                } catch {
                  return "#64748b";
                }
              }}
              nodeStrokeWidth={2}
              nodeBorderRadius={2}
              maskColor="rgba(0, 0, 0, 0.6)"
              maskStrokeColor="rgba(255, 255, 255, 0.4)"
              position="bottom-right"
              pannable={true}
              zoomable={true}
              style={{
                backgroundColor: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            />

            <Panel position="top-left" className="bg-slate-900/90 rounded-lg p-2 m-2">
              <div className="flex items-center gap-2">
                <CanvasToolbar onCreateNode={handleCreateNode} />
                <button
                  onClick={handleRefresh}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={!effectiveOrgId}
                  title="Refresh data from backend"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  onClick={handleAutoArrange}
                  className="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors flex items-center gap-2"
                  title="Auto-arrange nodes into lanes"
                >
                  <ArrowDownUp className="w-4 h-4" />
                  Auto-Arrange
                </button>
                <button
                  onClick={handleExport}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2"
                  title="Export canvas configuration"
                >
                  <Download className="w-4 h-4" />
                  Export
                </button>
                <select
                  value={groupBy}
                  onChange={(e) => setGroupBy(e.target.value as any)}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
                >
                  <option value="none">No Grouping</option>
                  <option value="organization">By Organization</option>
                  <option value="environment">By Environment</option>
                  <option value="server">By Server</option>
                </select>
                <div className="relative">
                  <button
                    onClick={() => setShowFilter(!showFilter)}
                    className={cn(
                      "px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2",
                      showFilter && "bg-slate-700"
                    )}
                  >
                    <Filter className="w-4 h-4" />
                    Filter
                  </button>
                  {showFilter && (
                    <div ref={filterMenuRef} className="absolute top-full left-0 mt-2 bg-slate-800 border border-slate-700 rounded-lg shadow-xl p-3 min-w-[280px] max-w-xs z-50">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-slate-200">Filter</h3>
                        <button
                          onClick={() => setShowFilter(false)}
                          className="text-slate-400 hover:text-slate-200 transition-colors"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                      
                      <div className="space-y-4">
                        {/* Node Type Filter */}
                        <div>
                          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 block">
                            Node Types
                          </label>
                          <div className="space-y-1">
                            {(["agent", "tool", "resource", "policy", "prompt", "server", "environment", "organization"] as CanvasNodeType[]).map((type) => {
                              const isSelected = filteredNodeTypes.has(type);
                              return (
                                <label
                                  key={type}
                                  className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer hover:text-slate-100 transition-colors"
                                >
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      const newSet = new Set(filteredNodeTypes);
                                      if (e.target.checked) {
                                        newSet.add(type);
                                      } else {
                                        newSet.delete(type);
                                      }
                                      setFilteredNodeTypes(newSet);
                                    }}
                                    className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-purple-600 focus:ring-purple-500"
                                  />
                                  <span className="capitalize">{type}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>

                        {/* Status Filter */}
                        <div>
                          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 block">
                            Status
                          </label>
                          <div className="space-y-1">
                            {(["connected", "error", "unauthorized", "disabled", "unknown"] as const).map((status) => {
                              const isSelected = filteredStatuses.has(status);
                              return (
                                <label
                                  key={status}
                                  className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer hover:text-slate-100 transition-colors"
                                >
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      const newSet = new Set(filteredStatuses);
                                      if (e.target.checked) {
                                        newSet.add(status);
                                      } else {
                                        newSet.delete(status);
                                      }
                                      setFilteredStatuses(newSet);
                                    }}
                                    className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-purple-600 focus:ring-purple-500"
                                  />
                                  <span className="capitalize">{status}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>

                        {/* Edge Type Filter */}
                        <div>
                          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 block">
                            Edge Types
                          </label>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                        {([
                          "agent-tool",
                          "agent-resource",
                          "agent-server",
                          "environment-server",
                          "environment-policy",
                          "environment-resource",
                          "environment-prompt",
                          "server-tool",
                          "prompt-resource",
                          "policy-agent",
                          "policy-tool",
                          "policy-server",
                          "policy-resource",
                          "organization-environment",
                        ] as const).map((edgeType) => {
                              const isSelected = filteredEdgeTypes.has(edgeType);
                              return (
                                <label
                                  key={edgeType}
                                  className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer hover:text-slate-100 transition-colors"
                                >
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={(e) => {
                                      const newSet = new Set(filteredEdgeTypes);
                                      if (e.target.checked) {
                                        newSet.add(edgeType);
                                      } else {
                                        newSet.delete(edgeType);
                                      }
                                      setFilteredEdgeTypes(newSet);
                                    }}
                                    className="w-3 h-3 rounded border-slate-600 bg-slate-800 text-purple-600 focus:ring-purple-500"
                                  />
                                  <span className="truncate">{edgeType.replace("-", " → ")}</span>
                                </label>
                              );
                            })}
                          </div>
                        </div>

                        {/* Clear Filters Button */}
                        {(filteredNodeTypes.size > 0 || filteredEdgeTypes.size > 0 || filteredStatuses.size > 0) && (
                          <button
                            onClick={() => {
                              setFilteredNodeTypes(new Set());
                              setFilteredEdgeTypes(new Set());
                              setFilteredStatuses(new Set());
                            }}
                            className="w-full px-3 py-2 text-sm text-slate-300 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                          >
                            Clear All Filters
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </Panel>
            
            {/* Floating Plus Button for quick node creation */}
            <Panel position="top-right" className="m-2">
              <div className="flex flex-col gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleCreateNode("agent");
                  }}
                  className="w-12 h-12 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-110"
                  title="Create Agent"
                >
                  <Plus className="w-6 h-6" />
                </button>
              </div>
            </Panel>
            
            {/* Node Navigator for easy navigation */}
            <NodeNavigator nodes={nodes} />
          </ReactFlow>
        </div>

        {/* Node Sidebar */}
        {sidebarOpen && selectedNode && (
          <CanvasSidebar
            node={selectedNode}
            onClose={() => {
              setSidebarOpen(false);
              setSelectedNode(null);
            }}
            onUpdate={(updatedData) => {
              setNodes((nds) =>
                nds.map((node) =>
                  node.id === selectedNode.id
                    ? { ...node, data: { ...node.data, ...updatedData } }
                    : node
                )
              );
            }}
            onDelete={(nodeId) => {
              // Remove node from canvas
              setNodes((nds) => nds.filter((n) => n.id !== nodeId));
              // Remove connected edges
              setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
              // Close sidebar
              setSidebarOpen(false);
              setSelectedNode(null);
            }}
            connectedEdges={edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id)}
            availableNodes={nodes}
            onCreateConnection={async (sourceId, targetId) => {
              // Create new edge
              const sourceNode = nodes.find((n) => n.id === sourceId);
              const targetNode = nodes.find((n) => n.id === targetId);
              
              if (!sourceNode || !targetNode) {
                console.warn("Source or target node not found");
                return;
              }
              
              const sourceType = sourceNode.data.type;
              const targetType = targetNode.data.type;
              
              if (!isValidEdgeConnection(sourceType, targetType)) {
                console.warn(`Invalid edge connection: ${sourceType} -> ${targetType}`);
                alert(`Cannot connect ${sourceType} to ${targetType}`);
                return;
              }
              
              const defaultEdgeType = getDefaultEdgeType(sourceType, targetType);
              if (!defaultEdgeType) {
                console.warn(`No valid edge type for: ${sourceType} -> ${targetType}`);
                return;
              }
              
              const newEdgeId = `${sourceId}-${targetId}`;
              const newEdge: Edge<CanvasEdgeData> = {
                id: newEdgeId,
                source: sourceId,
                target: targetId,
                type: "smoothstep",
                data: {
                  type: defaultEdgeType,
                  config: { allowed: true },
                },
              };
              
              setEdges((eds) => {
                if (eds.some((e) => e.id === newEdgeId)) {
                  console.warn("Edge already exists");
                  return eds;
                }
                return [...eds, newEdge];
              });
              
              // Save to backend
              await saveEdgeToBackend(newEdge);
            }}
            onDeleteConnection={(edgeId) => {
              setEdges((eds) => eds.filter((e) => e.id !== edgeId));
            }}
          />
        )}

        {/* Edge Sidebar */}
        {edgeSidebarOpen && selectedEdge && (() => {
          const sourceNode = nodes.find((n) => n.id === selectedEdge.source);
          const targetNode = nodes.find((n) => n.id === selectedEdge.target);
          
          // Prepare available nodes for dropdowns
          const availableNodes = nodes.map((node) => ({
            id: node.id,
            label: node.data?.label || node.id,
            type: node.data?.type || "unknown",
          }));
          
          return (
            <CanvasEdgeSidebar
              edge={selectedEdge}
              onClose={() => {
                setEdgeSidebarOpen(false);
                setSelectedEdge(null);
              }}
              onUpdate={handleEdgeUpdate}
              onUpdateSourceTarget={handleEdgeUpdateSourceTarget}
              onDelete={handleEdgeDelete}
              sourceNodeType={sourceNode?.data?.type}
              targetNodeType={targetNode?.data?.type}
              availableNodes={availableNodes}
            />
          );
        })()}

        {showAgentDialog && (
          <AgentDialog
            isOpen={showAgentDialog}
            onClose={() => {
              setShowAgentDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            orgId={effectiveOrgId}
            onSuccess={handleAgentCreated}
            preselectedEnvironmentId={preselectedEnvironmentId}
          />
        )}

        {showToolDialog && (
          <ToolDialog
            isOpen={showToolDialog}
            onClose={() => {
              setShowToolDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            orgId={effectiveOrgId}
            tool={undefined}
            onSuccess={handleToolCreated}
            preselectedEnvironmentId={preselectedEnvironmentId}
            preselectedConnectionId={preselectedConnectionId}
          />
        )}

        {showResourceDialog && effectiveOrgId && (
          <ResourceDialog
            resource={undefined}
            onClose={() => {
              setShowResourceDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            orgId={effectiveOrgId}
            environments={Array.isArray(environmentsData) ? environmentsData : (environmentsData?.results || [])}
            onSuccess={handleResourceCreated}
            preselectedEnvironmentId={preselectedEnvironmentId}
          />
        )}

        {showConnectionDialog && (
          <ConnectionDialog
            isOpen={showConnectionDialog}
            onClose={() => {
              setShowConnectionDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            orgId={effectiveOrgId}
            connection={undefined}
            onSuccess={handleConnectionCreated}
            preselectedEnvironmentId={preselectedEnvironmentId}
          />
        )}

        {showEnvironmentDialog && (
          <EnvironmentDialog
            isOpen={showEnvironmentDialog}
            onClose={() => {
              setShowEnvironmentDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            orgId={effectiveOrgId || undefined}
            environment={undefined}
            onSuccess={handleEnvironmentCreated}
          />
        )}

        {showPolicyDialog && (
          <PolicyDialog
            isOpen={showPolicyDialog}
            onClose={() => {
              setShowPolicyDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
              setPreselectedEnvironmentId(undefined);
              setPreselectedConnectionId(undefined);
            }}
            policy={null}
            orgId={effectiveOrgId}
            onSuccess={handlePolicyCreated}
            preselectedEnvironmentId={preselectedEnvironmentId}
          />
        )}

        <PromptDialog
          isOpen={showPromptDialog}
          prompt={null}
          onClose={() => {
            setShowPromptDialog(false);
            setPendingNodeType(null);
            setPendingPosition(null);
            setPendingSourceNodeId(undefined);
            setPendingSide(undefined);
            setPreselectedEnvironmentId(undefined);
          }}
          orgId={effectiveOrgId || ""}
          environments={environmentsData || []}
          onSuccess={handlePromptCreated}
          preselectedEnvironmentId={preselectedEnvironmentId}
        />

        {/* Action Modals */}
        <TestConnectionModal
          isOpen={showTestModal}
          onClose={() => {
            setShowTestModal(false);
            setSelectedActionEntityId("");
            setSelectedActionEntityName("");
          }}
          connectionId={selectedActionEntityId}
          connectionName={selectedActionEntityName}
          orgId={effectiveOrgId || ""}
        />

        <SyncToolsModal
          isOpen={showSyncModal}
          onClose={() => {
            setShowSyncModal(false);
            setSelectedActionEntityId("");
            setSelectedActionEntityName("");
          }}
          connectionId={selectedActionEntityId}
          connectionName={selectedActionEntityName}
          orgId={effectiveOrgId || ""}
        />

        <RunToolModal
          isOpen={showRunModal}
          onClose={() => {
            setShowRunModal(false);
            setSelectedActionEntityId("");
            setSelectedActionEntityName("");
          }}
          toolId={selectedActionEntityId}
          toolName={selectedActionEntityName}
          orgId={effectiveOrgId || ""}
        />

        <PingAgentModal
          isOpen={showPingModal}
          onClose={() => {
            setShowPingModal(false);
            setSelectedActionEntityId("");
            setSelectedActionEntityName("");
          }}
          agentId={selectedActionEntityId}
          agentName={selectedActionEntityName}
          orgId={effectiveOrgId || ""}
        />
      </ReactFlowProvider>
    </div>
  );
}

