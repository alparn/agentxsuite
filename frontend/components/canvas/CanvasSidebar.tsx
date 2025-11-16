"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Node, Edge } from "@xyflow/react";
import { X, Save, Trash2, Plus, Link as LinkIcon, Trash } from "lucide-react";
import { api, agentsApi, policiesApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CanvasNodeData, CanvasEdgeData } from "@/lib/canvasTypes";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { getValidTargetTypes } from "@/lib/canvasEdgeValidation";
import { cn } from "@/lib/utils";

interface CanvasSidebarProps {
  node: Node<CanvasNodeData>;
  onClose: () => void;
  onUpdate: (data: Partial<CanvasNodeData>) => void;
  onDelete?: (nodeId: string) => void;
  connectedEdges?: Edge<CanvasEdgeData>[];
  availableNodes?: Node<CanvasNodeData>[];
  onCreateConnection?: (sourceId: string, targetId: string) => void;
  onDeleteConnection?: (edgeId: string) => void;
}

export function CanvasSidebar({ 
  node, 
  onClose, 
  onUpdate, 
  onDelete, 
  connectedEdges = [], 
  availableNodes = [],
  onCreateConnection,
  onDeleteConnection 
}: CanvasSidebarProps) {
  const t = useTranslations();
  const { currentOrgId: orgId } = useAppStore();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showAddConnection, setShowAddConnection] = useState(false);

  const nodeData = node.data;

  // Get incoming and outgoing edges
  const incomingEdges = connectedEdges.filter((e) => e.target === node.id);
  const outgoingEdges = connectedEdges.filter((e) => e.source === node.id);

  // Get valid target node types for this node
  const validTargetTypes = getValidTargetTypes(nodeData.type);

  // Filter available nodes that can be connected
  const connectableNodes = availableNodes.filter((n) => 
    n.id !== node.id && 
    validTargetTypes.includes(n.data.type) &&
    !outgoingEdges.some((e) => e.target === n.id)
  );

  const handleSave = async () => {
    // Update the entity based on node type
    if (nodeData.type === "agent" && nodeData.agentId) {
      // Update agent
      await api.patch(`/orgs/${orgId}/agents/${nodeData.agentId}/`, {
        name: nodeData.label,
        enabled: nodeData.status === "connected",
      });
      queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
    } else if (nodeData.type === "tool" && nodeData.toolId) {
      // Update tool
      await api.patch(`/orgs/${orgId}/tools/${nodeData.toolId}/`, {
        enabled: nodeData.status === "connected",
      });
      queryClient.invalidateQueries({ queryKey: ["tools", orgId] });
    }
    // ... handle other types
    setIsEditing(false);
  };

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!orgId) throw new Error("Organization ID is required");

      if (nodeData.type === "agent" && nodeData.agentId) {
        return agentsApi.delete(orgId, nodeData.agentId);
      } else if (nodeData.type === "tool" && nodeData.toolId) {
        return api.delete(`/orgs/${orgId}/tools/${nodeData.toolId}/`);
      } else if (nodeData.type === "policy" && nodeData.policyId) {
        return policiesApi.delete(orgId, nodeData.policyId);
      } else if (nodeData.type === "resource" && nodeData.resourceId) {
        return api.delete(`/orgs/${orgId}/resources/${nodeData.resourceId}/`);
      } else if (nodeData.type === "server" && nodeData.connectionId) {
        return api.delete(`/orgs/${orgId}/connections/${nodeData.connectionId}/`);
      } else if (nodeData.type === "environment" && nodeData.environmentId) {
        return api.delete(`/orgs/${orgId}/environments/${nodeData.environmentId}/`);
      } else if (nodeData.type === "prompt" && nodeData.promptId) {
        return api.delete(`/orgs/${orgId}/prompts/${nodeData.promptId}/`);
      } else if (nodeData.type === "organization" && nodeData.organizationId) {
        // Organizations might not be deletable via API, or require special permissions
        // For now, we'll just remove the node from canvas without backend deletion
        // If backend deletion is needed, uncomment the line below:
        // return api.delete(`/orgs/${nodeData.organizationId}/`);
        return Promise.resolve({ data: { id: nodeData.organizationId } });
      }
      // For placeholder nodes or unknown types, just allow deletion from canvas
      console.warn(`Node type "${nodeData.type}" cannot be deleted from backend, removing from canvas only`);
      return Promise.resolve({ data: { id: node.id } });
    },
    onSuccess: () => {
      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
      queryClient.invalidateQueries({ queryKey: ["tools", orgId] });
      queryClient.invalidateQueries({ queryKey: ["policies", orgId] });
      queryClient.invalidateQueries({ queryKey: ["resources", orgId] });
      queryClient.invalidateQueries({ queryKey: ["prompts", orgId] });
      queryClient.invalidateQueries({ queryKey: ["connections", orgId] });
      queryClient.invalidateQueries({ queryKey: ["environments", orgId] });
      
      // Call onDelete callback to remove node from canvas
      if (onDelete) {
        onDelete(node.id);
      }
      
      setShowDeleteModal(false);
      onClose();
    },
    onError: (error: any) => {
      console.error("Failed to delete:", error);
      // TODO: Show error toast
    },
  });

  const handleDelete = () => {
    deleteMutation.mutate();
  };

  const getDeleteTitle = () => {
    const typeLabels: Record<string, string> = {
      agent: "Delete Agent",
      tool: "Delete Tool",
      policy: "Delete Policy",
      resource: "Delete Resource",
      prompt: "Delete Prompt",
      server: "Delete Connection",
      environment: "Delete Environment",
      organization: "Delete Organization",
    };
    return typeLabels[nodeData.type] || "Delete Item";
  };

  const getDeleteMessage = () => {
    const typeMessages: Record<string, string> = {
      agent: "Are you sure you want to delete this agent? This action cannot be undone.",
      tool: "Are you sure you want to delete this tool? This action cannot be undone.",
      policy: "Are you sure you want to delete this policy? This action cannot be undone.",
      resource: "Are you sure you want to delete this resource? This action cannot be undone.",
      prompt: "Are you sure you want to delete this prompt? This action cannot be undone.",
      server: "Are you sure you want to delete this connection? This action cannot be undone.",
      environment: "Are you sure you want to delete this environment? This action cannot be undone.",
      organization: "Are you sure you want to delete this organization? This action cannot be undone.",
    };
    return typeMessages[nodeData.type] || "Are you sure you want to delete this item? This action cannot be undone.";
  };

  return (
    <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Node Configuration</h2>
        <button
          onClick={onClose}
          className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-4">
        {/* Node Type */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Type</label>
          <div className="px-3 py-2 bg-slate-800 rounded-lg text-white capitalize">
            {nodeData.type}
          </div>
        </div>

        {/* Label */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Label</label>
          <input
            type="text"
            value={nodeData.label}
            onChange={(e) => onUpdate({ label: e.target.value })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>

        {/* Status */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Status</label>
          <select
            value={nodeData.status || "unknown"}
            onChange={(e) => onUpdate({ status: e.target.value as any })}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="connected">Connected</option>
            <option value="error">Error</option>
            <option value="unauthorized">Unauthorized</option>
            <option value="disabled">Disabled</option>
            <option value="unknown">Unknown</option>
          </select>
        </div>

        {/* Entity-specific configuration */}
        {nodeData.type === "agent" && nodeData.agent && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Agent ID</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {nodeData.agent.id}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Mode</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white capitalize">
                {nodeData.agent.mode}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Version</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
                {nodeData.agent.version}
              </div>
            </div>
          </div>
        )}

        {nodeData.type === "tool" && nodeData.tool && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Tool ID</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {nodeData.tool.id}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Version</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
                {nodeData.tool.version}
              </div>
            </div>
          </div>
        )}

        {nodeData.type === "policy" && nodeData.policy && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Policy ID</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {nodeData.policy.id}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Version</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
                {nodeData.policy.version}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Active</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
                {nodeData.policy.is_active ? "Yes" : "No"}
              </div>
            </div>
          </div>
        )}

        {nodeData.type === "prompt" && nodeData.prompt && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Prompt ID</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {nodeData.prompt.id}
              </div>
            </div>
            {nodeData.prompt.description && (
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Description</label>
                <div className="px-3 py-2 bg-slate-800 rounded-lg text-white text-sm">
                  {nodeData.prompt.description}
                </div>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Uses Resources</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white text-sm">
                {nodeData.prompt.uses_resources && nodeData.prompt.uses_resources.length > 0 ? (
                  <div className="space-y-1">
                    {nodeData.prompt.uses_resources.map((resourceName: string, idx: number) => (
                      <div key={idx} className="px-2 py-1 bg-slate-700 rounded text-xs text-amber-400">
                        {resourceName}
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="text-slate-500 text-xs">No resources</span>
                )}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Enabled</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
                {nodeData.prompt.enabled ? "Yes" : "No"}
              </div>
            </div>
          </div>
        )}

        {/* Connections Section */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-slate-400">Connections</label>
            {onCreateConnection && connectableNodes.length > 0 && (
              <button
                onClick={() => setShowAddConnection(!showAddConnection)}
                className="p-1 text-purple-400 hover:text-purple-300 rounded hover:bg-slate-800 transition-colors"
                title="Add Connection"
              >
                <Plus className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Outgoing Connections (this node → other nodes) */}
          {outgoingEdges.length > 0 && (
            <div>
              <div className="text-xs text-slate-500 mb-2">Outgoing ({outgoingEdges.length})</div>
              <div className="space-y-2">
                {outgoingEdges.map((edge) => {
                  const targetNode = availableNodes.find((n) => n.id === edge.target);
                  const isPolicyGoverned = edge.data?.metadata?.policyGoverned;
                  const policyName = edge.data?.metadata?.policyName;
                  
                  return (
                    <div
                      key={edge.id}
                      className={cn(
                        "flex items-center justify-between px-3 py-2 rounded-lg text-sm",
                        isPolicyGoverned ? "bg-yellow-500/10 border border-yellow-500/30" : "bg-slate-800"
                      )}
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <LinkIcon className={cn(
                          "w-4 h-4 flex-shrink-0",
                          isPolicyGoverned ? "text-yellow-400" : "text-purple-400"
                        )} />
                        <div className="flex-1 min-w-0">
                          <div className="text-white truncate">{targetNode?.data.label || edge.target}</div>
                          <div className="text-xs text-slate-500 capitalize">{edge.data?.type?.replace('-', ' → ')}</div>
                          {isPolicyGoverned && policyName && (
                            <div className="text-xs text-yellow-400 mt-1 flex items-center gap-1">
                              <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse"></div>
                              via {policyName}
                            </div>
                          )}
                        </div>
                      </div>
                      {onDeleteConnection && !isPolicyGoverned && (
                        <button
                          onClick={() => onDeleteConnection(edge.id)}
                          className="p-1 text-red-400 hover:text-red-300 rounded hover:bg-slate-700 transition-colors flex-shrink-0 ml-2"
                          title="Remove Connection"
                        >
                          <Trash className="w-3 h-3" />
                        </button>
                      )}
                      {isPolicyGoverned && (
                        <div className="text-xs text-slate-500 flex-shrink-0 ml-2" title="Cannot delete policy-governed connection">
                          🔒
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Incoming Connections (other nodes → this node) */}
          {incomingEdges.length > 0 && (
            <div>
              <div className="text-xs text-slate-500 mb-2">Incoming ({incomingEdges.length})</div>
              <div className="space-y-2">
                {incomingEdges.map((edge) => {
                  const sourceNode = availableNodes.find((n) => n.id === edge.source);
                  const isPolicyGoverned = edge.data?.metadata?.policyGoverned;
                  const policyName = edge.data?.metadata?.policyName;
                  
                  return (
                    <div
                      key={edge.id}
                      className={cn(
                        "flex items-center justify-between px-3 py-2 rounded-lg text-sm",
                        isPolicyGoverned ? "bg-yellow-500/10 border border-yellow-500/30" : "bg-slate-800/50"
                      )}
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <LinkIcon className={cn(
                          "w-4 h-4 flex-shrink-0",
                          isPolicyGoverned ? "text-yellow-400" : "text-blue-400"
                        )} />
                        <div className="flex-1 min-w-0">
                          <div className="text-white truncate">{sourceNode?.data.label || edge.source}</div>
                          <div className="text-xs text-slate-500 capitalize">{edge.data?.type?.replace('-', ' → ')}</div>
                          {isPolicyGoverned && policyName && (
                            <div className="text-xs text-yellow-400 mt-1 flex items-center gap-1">
                              <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse"></div>
                              via {policyName}
                            </div>
                          )}
                        </div>
                      </div>
                      {onDeleteConnection && !isPolicyGoverned && (
                        <button
                          onClick={() => onDeleteConnection(edge.id)}
                          className="p-1 text-red-400 hover:text-red-300 rounded hover:bg-slate-700 transition-colors flex-shrink-0 ml-2"
                          title="Remove Connection"
                        >
                          <Trash className="w-3 h-3" />
                        </button>
                      )}
                      {isPolicyGoverned && (
                        <div className="text-xs text-slate-500 flex-shrink-0 ml-2" title="Cannot delete policy-governed connection">
                          🔒
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Add Connection Menu */}
          {showAddConnection && onCreateConnection && (
            <div className="border border-slate-700 rounded-lg p-3 space-y-2">
              <div className="text-xs text-slate-400 mb-2">Available Nodes to Connect:</div>
              {connectableNodes.length > 0 ? (
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {connectableNodes.map((targetNode) => (
                    <button
                      key={targetNode.id}
                      onClick={() => {
                        onCreateConnection(node.id, targetNode.id);
                        setShowAddConnection(false);
                      }}
                      className="w-full px-3 py-2 text-left text-sm bg-slate-800 hover:bg-slate-700 rounded transition-colors flex items-center gap-2"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-white truncate">{targetNode.data.label}</div>
                        <div className="text-xs text-slate-500 capitalize">{targetNode.data.type}</div>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-slate-500 text-center py-2">
                  No available nodes to connect
                </div>
              )}
            </div>
          )}

          {/* No Connections Message */}
          {outgoingEdges.length === 0 && incomingEdges.length === 0 && (
            <div className="px-3 py-2 bg-slate-800/50 rounded-lg text-sm text-slate-500 text-center">
              No connections
            </div>
          )}
        </div>

        {/* Metadata */}
        {nodeData.metadata && Object.keys(nodeData.metadata).length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Metadata</label>
            <pre className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 text-xs overflow-x-auto">
              {JSON.stringify(nodeData.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 flex items-center gap-2">
        <button
          onClick={handleSave}
          className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Save className="w-4 h-4" />
          Save Changes
        </button>
        <button
          onClick={() => setShowDeleteModal(true)}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Trash2 className="w-4 h-4" />
          Delete
        </button>
      </div>

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onConfirm={handleDelete}
        title={getDeleteTitle()}
        message={getDeleteMessage()}
        itemName={nodeData.label}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

