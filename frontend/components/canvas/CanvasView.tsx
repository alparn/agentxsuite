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
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CanvasNode } from "./CanvasNode";
import { CanvasSidebar } from "./CanvasSidebar";
import { CanvasEdgeSidebar } from "./CanvasEdgeSidebar";
import { CanvasToolbar } from "./CanvasToolbar";
import { AgentDialog } from "../AgentDialog";
import { ToolDialog } from "../ToolDialog";
import { ResourceDialog } from "../ResourceDialog";
import { ConnectionDialog } from "../ConnectionDialog";
import { api, agentsApi, canvasApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CanvasNodeData, CanvasEdgeData, CanvasState, CanvasNodeType } from "@/lib/canvasTypes";
import { isValidEdgeConnection, getDefaultEdgeType, getValidEdgeTypes } from "@/lib/canvasEdgeValidation";
import { Plus, Download, Upload, Save, RefreshCw, Layers, Filter, X } from "lucide-react";
import { cn } from "@/lib/utils";

const nodeTypes = {
  canvasNode: CanvasNode,
};

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
  const [pendingNodeType, setPendingNodeType] = useState<CanvasNodeType | null>(null);
  const [pendingPosition, setPendingPosition] = useState<{ x: number; y: number } | null>(null);
  const [pendingSourceNodeId, setPendingSourceNodeId] = useState<string | undefined>(undefined);
  const [pendingSide, setPendingSide] = useState<"left" | "right" | undefined>(undefined);
  
  // Filter state
  const [showFilter, setShowFilter] = useState(false);
  const [filteredNodeTypes, setFilteredNodeTypes] = useState<Set<CanvasNodeType>>(new Set());
  const [filteredEdgeTypes, setFilteredEdgeTypes] = useState<Set<string>>(new Set());
  const [filteredStatuses, setFilteredStatuses] = useState<Set<string>>(new Set());
  const filterMenuRef = useRef<HTMLDivElement>(null);

  // Fetch organizations and auto-select first one if none selected
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  // Fetch all entities
  const { data: agentsData } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/agents/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: toolsData } = useQuery({
    queryKey: ["tools", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/tools/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: resourcesData } = useQuery({
    queryKey: ["resources", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/resources/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: policiesData } = useQuery({
    queryKey: ["policies", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/policies/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: connectionsData } = useQuery({
    queryKey: ["connections", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/connections/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const { data: environmentsData, isLoading: environmentsLoading } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      try {
        // Try organization-specific endpoint first
        const response = await api.get(`/orgs/${orgId}/environments/`);
        return Array.isArray(response.data) ? response.data : response.data?.results || [];
      } catch (error: any) {
        // Fallback: try direct environments endpoint with org filter
        if (error.response?.status === 404) {
          try {
            const response = await api.get(`/environments/`, { params: { organization: orgId } });
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
    enabled: !!orgId,
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
        },
      });
    });

    // Add tools - position near their connections
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

    const maxAgentY = agentPositions.length > 0 ? Math.max(...agentPositions.map(p => p.y)) : currentY;
    const toolStartY = maxAgentY + sectionSpacing;
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
        },
      });
    });

    // Add resources
    const maxToolY = toolPositions.length > 0 ? Math.max(...toolPositions.map(p => p.y)) : toolStartY;
    const resourceStartY = maxToolY + sectionSpacing;
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
        },
      });
    });

    // Add policies
    const maxResourceY = resourcePositions.length > 0 ? Math.max(...resourcePositions.map(p => p.y)) : resourceStartY;
    const policyStartY = maxResourceY + sectionSpacing;
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
        },
      });
    });

    // Add servers/connections
    const maxPolicyY = policyPositions.length > 0 ? Math.max(...policyPositions.map(p => p.y)) : policyStartY;
    const connectionStartY = maxPolicyY + sectionSpacing;
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
        },
      });
    });

    return nodes;
  }, [agentsData, toolsData, resourcesData, policiesData, connectionsData, environmentsData, calculateLayout, ensureValidPosition]);

  // Generate initial edges from backend relationships
  const initialEdges = useMemo(() => {
    const edges: Edge<CanvasEdgeData>[] = [];

    // Agent → Connection (server)
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

    // Agent → Environment
    (agentsData || []).forEach((agent: any) => {
      const envId = agent.environment?.id || agent.environment_id;
      if (envId) {
        edges.push({
          id: `agent-${agent.id}-env-${envId}`,
          source: `agent-${agent.id}`,
          target: `env-${envId}`,
          type: "smoothstep",
          data: {
            type: "agent-environment",
            config: { allowed: true },
          },
        });
      }
    });

    // Tool → Connection (server)
    (toolsData || []).forEach((tool: any) => {
      const connectionId = tool.connection?.id || tool.connection_id;
      if (connectionId) {
        edges.push({
          id: `tool-${tool.id}-server-${connectionId}`,
          source: `tool-${tool.id}`,
          target: `server-${connectionId}`,
          type: "smoothstep",
          data: {
            type: "tool-server",
            config: { allowed: true },
          },
        });
      }
    });

    // Tool → Environment
    (toolsData || []).forEach((tool: any) => {
      const envId = tool.environment?.id || tool.environment_id;
      if (envId) {
        edges.push({
          id: `tool-${tool.id}-env-${envId}`,
          source: `tool-${tool.id}`,
          target: `env-${envId}`,
          type: "smoothstep",
          data: {
            type: "environment-server",
            config: { allowed: true },
          },
        });
      }
    });

    // Resource → Environment
    (resourcesData || []).forEach((resource: any) => {
      const envId = resource.environment?.id || resource.environment_id;
      if (envId) {
        edges.push({
          id: `resource-${resource.id}-env-${envId}`,
          source: `resource-${resource.id}`,
          target: `env-${envId}`,
          type: "smoothstep",
          data: {
            type: "environment-server",
            config: { allowed: true },
          },
        });
      }
    });

    return edges;
  }, [agentsData, toolsData, resourcesData, policiesData, connectionsData, environmentsData]);

  // Load saved canvas state from backend
  const { data: savedCanvasState } = useQuery({
    queryKey: ["canvas-state", orgId],
    queryFn: async () => {
      if (!orgId) return null;
      try {
        const response = await canvasApi.getDefault(orgId);
        return response.data?.state_json || null;
      } catch (error: any) {
        // 404 is ok - no saved state yet
        if (error.response?.status === 404) {
          return null;
        }
        console.error("Failed to load canvas state from backend:", error);
        // Fallback to localStorage
        try {
          const saved = localStorage.getItem(`canvas-state-${orgId}`);
          if (saved) {
            return JSON.parse(saved);
          }
        } catch (e) {
          console.error("Failed to load canvas state from localStorage:", e);
        }
        return null;
      }
    },
    enabled: !!orgId,
    staleTime: 30000, // Cache for 30 seconds
  });

  // Load saved canvas state from localStorage (fallback)
  const loadCanvasState = useCallback(() => {
    // Prefer backend state
    if (savedCanvasState) {
      return savedCanvasState;
    }
    
    // Fallback to localStorage
    if (!orgId) return null;
    try {
      const saved = localStorage.getItem(`canvas-state-${orgId}`);
      if (saved) {
        const state = JSON.parse(saved);
        return state;
      }
    } catch (error) {
      console.error("Failed to load canvas state:", error);
    }
    return null;
  }, [orgId, savedCanvasState]);

  // Save canvas state mutation
  const saveCanvasStateMutation = useMutation({
    mutationFn: async (state: any) => {
      if (!orgId) throw new Error("Organization ID is required");
      return canvasApi.saveDefault(orgId, state);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["canvas-state", orgId] });
    },
    onError: (error: any, state: any) => {
      console.error("Failed to save canvas state to backend:", error);
      // Fallback to localStorage
      if (orgId && state) {
        try {
          localStorage.setItem(`canvas-state-${orgId}`, JSON.stringify(state));
        } catch (e) {
          console.error("Failed to save canvas state to localStorage:", e);
        }
      }
    },
  });

  // Save canvas state to backend (with localStorage fallback)
  const saveCanvasState = useCallback((nodesToSave: Node<CanvasNodeData>[], edgesToSave: Edge<CanvasEdgeData>[]) => {
    if (!orgId) return;
    
    const state = {
      nodes: nodesToSave.map((n) => ({
        id: n.id,
        position: n.position,
        data: {
          type: n.data.type,
          agentId: n.data.agentId,
          toolId: n.data.toolId,
          resourceId: n.data.resourceId,
          policyId: n.data.policyId,
          connectionId: n.data.connectionId,
          environmentId: n.data.environmentId,
          organizationId: n.data.organizationId,
        },
      })),
      edges: edgesToSave.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        data: e.data,
      })),
      viewport: { x: 0, y: 0, zoom: 1 },
      groups: {},
      savedAt: new Date().toISOString(),
    };
    
    // Save to backend
    saveCanvasStateMutation.mutate(state);
    
    // Also save to localStorage as backup
    try {
      localStorage.setItem(`canvas-state-${orgId}`, JSON.stringify(state));
    } catch (error) {
      console.error("Failed to save canvas state to localStorage:", error);
    }
  }, [orgId, saveCanvasStateMutation]);

  // Merge saved positions with current data
  const mergedNodes = useMemo(() => {
    const savedState = loadCanvasState();
    if (!savedState || !savedState.nodes) return initialNodes;

    // Create a map of saved positions by entity ID
    const savedPositions = new Map<string, { x: number; y: number }>();
    savedState.nodes.forEach((savedNode: any) => {
      const entityId = savedNode.data.agentId || savedNode.data.toolId || 
                       savedNode.data.resourceId || savedNode.data.policyId ||
                       savedNode.data.connectionId || savedNode.data.environmentId;
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
          edgeIdMap.set(key, e as Edge<CanvasEdgeData>);
        }
      });
      
      edgesToUse = Array.from(edgeIdMap.values());
    }
    
    return edgesToUse;
  }, [mergedNodes, initialEdges, loadCanvasState]);

  const [nodes, setNodes, onNodesChange] = useNodesState(mergedNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<CanvasEdgeData>>(initialEdgesComputed);

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

  // Handle creating new nodes (defined after setNodes is available)
  const handleCreateNode = useCallback((type: CanvasNodeType, position?: { x: number; y: number }, side?: "left" | "right", sourceNodeId?: string) => {
    // Use provided position or center of viewport
    const nodePosition = position || { x: 400, y: 300 };
    
    if (type === "agent") {
      // Open agent dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setShowAgentDialog(true);
    } else if (type === "tool") {
      // Open tool dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setShowToolDialog(true);
    } else if (type === "resource") {
      // Open resource dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setShowResourceDialog(true);
    } else if (type === "server") {
      // Open connection/server dialog
      setPendingNodeType(type);
      setPendingPosition(nodePosition);
      setPendingSourceNodeId(sourceNodeId); // Store source node ID for connection
      setPendingSide(side); // Store side for connection
      setShowConnectionDialog(true);
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
            setTimeout(() => {
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

  // Use a ref to track the last handleCreateNode reference to prevent infinite loops
  const lastHandleCreateNodeRef = useRef(handleCreateNode);
  const lastEdgesLengthRef = useRef(edges.length);
  
  useEffect(() => {
    // Only update if handleCreateNode reference actually changed or edges length changed
    const handleCreateNodeChanged = lastHandleCreateNodeRef.current !== handleCreateNode;
    const edgesLengthChanged = lastEdgesLengthRef.current !== edges.length;
    
    if (!handleCreateNodeChanged && !edgesLengthChanged) {
      return; // Nothing changed, skip update
    }
    
    // Update refs
    lastHandleCreateNodeRef.current = handleCreateNode;
    lastEdgesLengthRef.current = edges.length;
    
    setNodes((currentNodes) => {
      // Only update if something actually changed
      const needsUpdate = currentNodes.some((node) => {
        const hasConnections = nodesWithConnectionsSet.has(node.id);
        // Compare function references and connection status
        const onCreateNodeChanged = node.data.onCreateNode !== handleCreateNode;
        const hasConnectionsChanged = node.data.hasConnections !== hasConnections;
        return onCreateNodeChanged || hasConnectionsChanged;
      });

      if (!needsUpdate) {
        return currentNodes; // Return same reference to prevent re-render
      }

      return currentNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          onCreateNode: handleCreateNode,
          hasConnections: nodesWithConnectionsSet.has(node.id),
        },
      }));
    });
  }, [setNodes, handleCreateNode, nodesWithConnectionsSet, edges.length]);


  // Save state when nodes or edges change (debounced)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      saveCanvasState(nodes, edges);
    }, 1000); // Debounce: save 1 second after last change

    return () => clearTimeout(timeoutId);
  }, [nodes, edges, saveCanvasState]);

  // Initialize nodes on mount and when mergedNodes change
  const nodesInitializedRef = useRef(false);
  const prevMergedNodesRef = useRef<Node<CanvasNodeData>[]>([]);
  
  useEffect(() => {
    // Check if mergedNodes actually changed
    const prevIds = new Set(prevMergedNodesRef.current.map((n) => n.id));
    const currentIds = new Set(mergedNodes.map((n) => n.id));
    const idsChanged = 
      prevIds.size !== currentIds.size ||
      Array.from(currentIds).some((id) => !prevIds.has(id)) ||
      Array.from(prevIds).some((id) => !currentIds.has(id));
    
    // Only update if mergedNodes changed or we haven't initialized yet
    if (!idsChanged && nodesInitializedRef.current && prevMergedNodesRef.current.length > 0) {
      return; // No change, skip
    }
    
    // Update refs
    prevMergedNodesRef.current = mergedNodes;
    
    setNodes((currentNodes) => {
      // If we haven't initialized yet or nodes are empty, use mergedNodes directly
      if (!nodesInitializedRef.current || currentNodes.length === 0) {
        nodesInitializedRef.current = true;
        return mergedNodes.length > 0 ? mergedNodes : currentNodes;
      }
      
      // Otherwise, merge positions
      const currentPositions = new Map(currentNodes.map((n) => [n.id, n.position]));
      const updatedNodes = mergedNodes.map((node) => {
        const savedPosition = currentPositions.get(node.id);
        if (savedPosition && typeof savedPosition.x === 'number' && typeof savedPosition.y === 'number' &&
            !isNaN(savedPosition.x) && !isNaN(savedPosition.y)) {
          return { ...node, position: savedPosition };
        }
        // Ensure node position is valid
        const nodePos = node.position || { x: 0, y: 0 };
        if (typeof nodePos.x !== 'number' || typeof nodePos.y !== 'number' ||
            isNaN(nodePos.x) || isNaN(nodePos.y)) {
          return { ...node, position: { x: 0, y: 0 } };
        }
        return node;
      });
      
      // Add any new nodes that don't exist yet (user-created nodes)
      const existingIds = new Set(updatedNodes.map((n) => n.id));
      const newNodes = currentNodes.filter((n) => !existingIds.has(n.id));
      
      return [...updatedNodes, ...newNodes];
    });
  }, [mergedNodes, setNodes]);

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

    if (!sourceNode || !targetNode || !orgId) return;

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
          await api.patch(`/orgs/${orgId}/agents/${agentId}/`, {
            connection_id: connectionId,
          });
          queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
        }
      } else if (edge.data?.type === "agent-environment" && sourceNode.data.type === "agent" && targetNode.data.type === "environment") {
        // Update agent's environment
        const agentId = sourceNode.data.agentId;
        const environmentId = targetNode.data.environmentId;
        
        if (agentId && environmentId) {
          await api.patch(`/orgs/${orgId}/agents/${agentId}/`, {
            environment_id: environmentId,
          });
          queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
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
  }, [nodes, orgId, queryClient]);

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
    queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
    queryClient.invalidateQueries({ queryKey: ["tools", orgId] });
    queryClient.invalidateQueries({ queryKey: ["resources", orgId] });
    queryClient.invalidateQueries({ queryKey: ["policies", orgId] });
    queryClient.invalidateQueries({ queryKey: ["connections", orgId] });
    queryClient.invalidateQueries({ queryKey: ["environments", orgId] });
  }, [queryClient, orgId]);

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
      organizationId: orgId || "",
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
            setTimeout(() => {
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
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
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
            setTimeout(() => {
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
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
    }
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode]);

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
            setTimeout(() => {
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
          }
        }
        
        return updatedNodes;
      });
      
      // Clear pending state
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
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
            setTimeout(() => {
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
          }
        }
        
        return updatedNodes;
      });
      
      setPendingNodeType(null);
      setPendingPosition(null);
      setPendingSourceNodeId(undefined);
      setPendingSide(undefined);
    }
    queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
  }, [pendingPosition, pendingNodeType, pendingSourceNodeId, pendingSide, setNodes, nodes, setEdges, handleCreateNode, queryClient, orgId]);

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
            fitView
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
                  const colorMap: Record<string, string> = {
                    agent: "#a855f7",
                    tool: "#3b82f6",
                    resource: "#10b981",
                    policy: "#eab308",
                    server: "#06b6d4",
                    environment: "#ec4899",
                    organization: "#6366f1",
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
              style={{
                backgroundColor: "#0f172a",
                border: "1px solid #334155",
                borderRadius: "8px",
              }}
            />

            <Panel position="top-left" className="bg-slate-900/90 rounded-lg p-2 m-2">
              <div className="flex items-center gap-2">
                <CanvasToolbar onCreateNode={handleCreateNode} />
                <button
                  onClick={handleRefresh}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  onClick={handleExport}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors flex items-center gap-2"
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
                            {(["agent", "tool", "resource", "policy", "server", "environment", "organization"] as CanvasNodeType[]).map((type) => {
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
                              "agent-environment",
                              "tool-server",
                              "resource-server",
                              "policy-agent",
                              "policy-tool",
                              "policy-server",
                              "policy-resource",
                              "environment-server",
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
          />
        )}

        {/* Edge Sidebar */}
        {edgeSidebarOpen && selectedEdge && (() => {
          const sourceNode = nodes.find((n) => n.id === selectedEdge.source);
          const targetNode = nodes.find((n) => n.id === selectedEdge.target);
          return (
            <CanvasEdgeSidebar
              edge={selectedEdge}
              onClose={() => {
                setEdgeSidebarOpen(false);
                setSelectedEdge(null);
              }}
              onUpdate={handleEdgeUpdate}
              onDelete={handleEdgeDelete}
              sourceNodeType={sourceNode?.data?.type}
              targetNodeType={targetNode?.data?.type}
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
            }}
            orgId={orgId}
            onSuccess={handleAgentCreated}
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
            }}
            orgId={orgId}
            tool={undefined}
            onSuccess={handleToolCreated}
          />
        )}

        {showResourceDialog && orgId && (
          <ResourceDialog
            resource={undefined}
            onClose={() => {
              setShowResourceDialog(false);
              setPendingNodeType(null);
              setPendingPosition(null);
              setPendingSourceNodeId(undefined);
              setPendingSide(undefined);
            }}
            orgId={orgId}
            environments={Array.isArray(environmentsData) ? environmentsData : (environmentsData?.results || [])}
            onSuccess={handleResourceCreated}
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
            }}
            orgId={orgId}
            connection={undefined}
            onSuccess={handleConnectionCreated}
          />
        )}
      </ReactFlowProvider>
    </div>
  );
}

