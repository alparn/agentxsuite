"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Node } from "@xyflow/react";
import { X, Save, Trash2 } from "lucide-react";
import { api, agentsApi, policiesApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CanvasNodeData } from "@/lib/canvasTypes";
import { DeleteConfirmModal } from "./DeleteConfirmModal";

interface CanvasSidebarProps {
  node: Node<CanvasNodeData>;
  onClose: () => void;
  onUpdate: (data: Partial<CanvasNodeData>) => void;
  onDelete?: (nodeId: string) => void;
}

export function CanvasSidebar({ node, onClose, onUpdate, onDelete }: CanvasSidebarProps) {
  const t = useTranslations();
  const { currentOrgId: orgId } = useAppStore();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const nodeData = node.data;

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
      agent: t("agents.deleteTitle") || "Delete Agent",
      tool: t("tools.deleteTitle") || "Delete Tool",
      policy: t("policies.deleteTitle") || "Delete Policy",
      resource: t("resources.deleteTitle") || "Delete Resource",
      server: t("connections.deleteTitle") || "Delete Connection",
      environment: t("environments.deleteTitle") || "Delete Environment",
      organization: t("organizations.deleteTitle") || "Delete Organization",
    };
    return typeLabels[nodeData.type] || "Delete Item";
  };

  const getDeleteMessage = () => {
    const typeMessages: Record<string, string> = {
      agent: t("agents.deleteMessage") || "Are you sure you want to delete this agent? This action cannot be undone.",
      tool: t("tools.deleteMessage") || "Are you sure you want to delete this tool? This action cannot be undone.",
      policy: t("policies.deleteMessage") || "Are you sure you want to delete this policy? This action cannot be undone.",
      resource: t("resources.deleteMessage") || "Are you sure you want to delete this resource? This action cannot be undone.",
      server: t("connections.deleteMessage") || "Are you sure you want to delete this connection? This action cannot be undone.",
      environment: t("environments.deleteMessage") || "Are you sure you want to delete this environment? This action cannot be undone.",
      organization: t("organizations.deleteMessage") || "Are you sure you want to delete this organization? This action cannot be undone.",
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

