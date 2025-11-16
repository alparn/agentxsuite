"use client";

import { useState, useEffect } from "react";
import { Edge } from "@xyflow/react";
import { X, Save, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CanvasEdgeData, CanvasEdgeType } from "@/lib/canvasTypes";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { getValidEdgeTypes } from "@/lib/canvasEdgeValidation";

interface CanvasEdgeSidebarProps {
  edge: Edge<CanvasEdgeData>;
  onClose: () => void;
  onUpdate: (edgeId: string, data: Partial<CanvasEdgeData>) => void;
  onUpdateSourceTarget?: (edgeId: string, newSource: string, newTarget: string) => void;
  onDelete?: (edgeId: string) => void;
  sourceNodeType?: string;
  targetNodeType?: string;
  availableNodes?: Array<{ id: string; label: string; type: string }>;
}

const edgeTypeOptions: CanvasEdgeType[] = [
  "agent-tool",
  "agent-resource",
  "agent-server",
  "agent-environment",
  "tool-server",
  "tool-environment",
  "resource-environment",
  "environment-resource",
  "policy-agent",
  "policy-tool",
  "policy-server",
  "policy-resource",
  "policy-environment",
  "environment-policy",
  "environment-agent",
  "environment-prompt",
  "prompt-resource",
  "server-environment",
  "environment-server",
  "server-tool",
  "organization-environment",
];

export function CanvasEdgeSidebar({ edge, onClose, onUpdate, onUpdateSourceTarget, onDelete, sourceNodeType, targetNodeType, availableNodes = [] }: CanvasEdgeSidebarProps) {
  const { currentOrgId: orgId } = useAppStore();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedSource, setSelectedSource] = useState(edge.source);
  const [selectedTarget, setSelectedTarget] = useState(edge.target);

  const edgeData = edge.data || { type: "agent-tool" };
  
  // Update local state when edge changes
  useEffect(() => {
    setSelectedSource(edge.source);
    setSelectedTarget(edge.target);
  }, [edge.source, edge.target]);

  // Get current source and target node types for validation
  const currentSourceNode = availableNodes.find((n) => n.id === selectedSource);
  const currentTargetNode = availableNodes.find((n) => n.id === selectedTarget);
  const currentSourceType = currentSourceNode?.type || sourceNodeType;
  const currentTargetType = currentTargetNode?.type || targetNodeType;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Use current selected source/target (may have been changed)
      const currentSource = selectedSource;
      const currentTarget = selectedTarget;
      const currentEdgeId = `${currentSource}-${currentTarget}`;
      
      // Update edge in backend if it has an ID
      if (currentEdgeId && orgId) {
        try {
          // Try to update existing edge
          await api.patch(`/orgs/${orgId}/canvas/edges/${edge.id}/`, {
            id: currentEdgeId,
            source: currentSource,
            target: currentTarget,
            type: edgeData.type,
            config: edgeData.config,
            metadata: edgeData.metadata,
          });
        } catch (error: any) {
          // If edge doesn't exist in backend, create it
          if (error.response?.status === 404) {
            await api.post(`/orgs/${orgId}/canvas/edges/`, {
              id: currentEdgeId,
              source: currentSource,
              target: currentTarget,
              type: edgeData.type,
              config: edgeData.config,
              metadata: edgeData.metadata,
            });
          } else {
            throw error;
          }
        }
      }
      
      // Update edge in canvas with current source/target
      onUpdate(edge.id, {
        ...edgeData,
      });
      
      // If source/target changed, also update them
      if (onUpdateSourceTarget && (currentSource !== edge.source || currentTarget !== edge.target)) {
        onUpdateSourceTarget(edge.id, currentSource, currentTarget);
      }
    } catch (error) {
      console.error("Failed to save edge:", error);
      // TODO: Show error toast
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      // Delete from backend if it exists
      if (edge.id && orgId) {
        try {
          await api.delete(`/orgs/${orgId}/canvas/edges/${edge.id}/`);
        } catch (error: any) {
          // Ignore 404 errors (edge might not exist in backend)
          if (error.response?.status !== 404) {
            throw error;
          }
        }
      }
      
      // Remove edge from canvas
      if (onDelete) {
        onDelete(edge.id);
      }
      
      setShowDeleteModal(false);
      onClose();
    } catch (error) {
      console.error("Failed to delete edge:", error);
      // TODO: Show error toast
    }
  };

  const updateConfig = (key: string, value: any) => {
    onUpdate(edge.id, {
      ...edgeData,
      config: {
        ...edgeData.config,
        [key]: value,
      },
    });
  };

  return (
    <div className="w-96 bg-slate-900 border-l border-slate-800 flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Edge Configuration</h2>
        <button
          onClick={onClose}
          className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 space-y-4">
        {/* Edge ID */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Edge ID</label>
          <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
            {edge.id}
          </div>
        </div>

        {/* Source and Target */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Source</label>
            {availableNodes.length > 0 ? (
              <select
                value={selectedSource}
                onChange={(e) => {
                  const newSource = e.target.value;
                  setSelectedSource(newSource);
                  if (onUpdateSourceTarget) {
                    onUpdateSourceTarget(edge.id, newSource, selectedTarget);
                  }
                }}
                disabled={isSaving}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {availableNodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label} ({node.type})
                  </option>
                ))}
              </select>
            ) : (
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {edge.source}
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Target</label>
            {availableNodes.length > 0 ? (
              <select
                value={selectedTarget}
                onChange={(e) => {
                  const newTarget = e.target.value;
                  setSelectedTarget(newTarget);
                  if (onUpdateSourceTarget) {
                    onUpdateSourceTarget(edge.id, selectedSource, newTarget);
                  }
                }}
                disabled={isSaving}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {availableNodes.map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.label} ({node.type})
                  </option>
                ))}
              </select>
            ) : (
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-sm">
                {edge.target}
              </div>
            )}
          </div>
        </div>

        {/* Edge Type */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Edge Type</label>
          {currentSourceType && currentTargetType ? (
            <select
              value={edgeData.type}
              onChange={(e) => {
                const newType = e.target.value as CanvasEdgeType;
                // Validate the new edge type is valid for this connection
                const validTypes = getValidEdgeTypes(currentSourceType as any, currentTargetType as any);
                if (validTypes.includes(newType)) {
                  onUpdate(edge.id, { ...edgeData, type: newType });
                } else {
                  console.warn(`Invalid edge type ${newType} for ${currentSourceType} -> ${currentTargetType}`);
                }
              }}
              disabled={isSaving}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {getValidEdgeTypes(currentSourceType as any, currentTargetType as any).map((type) => (
                <option key={type} value={type}>
                  {type.replace("-", " → ")}
                </option>
              ))}
            </select>
          ) : (
            <select
              value={edgeData.type}
              onChange={(e) => onUpdate(edge.id, { ...edgeData, type: e.target.value as CanvasEdgeType })}
              disabled={isSaving}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {edgeTypeOptions.map((type) => (
                <option key={type} value={type}>
                  {type.replace("-", " → ")}
                </option>
              ))}
            </select>
          )}
          {currentSourceType && currentTargetType && (
            <p className="text-xs text-slate-500 mt-1">
              Valid types for {currentSourceType} → {currentTargetType}
            </p>
          )}
        </div>

        {/* Configuration */}
        <div>
          <label className="block text-sm font-medium text-slate-400 mb-2">Configuration</label>
          <div className="space-y-3 bg-slate-800 rounded-lg p-3">
            {/* Allowed */}
            <div className="flex items-center justify-between">
              <label className="text-sm text-slate-300">Allowed</label>
              <input
                type="checkbox"
                checked={edgeData.config?.allowed ?? true}
                onChange={(e) => updateConfig("allowed", e.target.checked)}
                className="w-4 h-4 rounded border-slate-600 bg-slate-700 text-purple-600 focus:ring-purple-500"
              />
            </div>

            {/* Effect (for policy edges) */}
            {edgeData.type.startsWith("policy-") && (
              <div>
                <label className="block text-sm text-slate-300 mb-1">Effect</label>
                <select
                  value={edgeData.config?.effect || "allow"}
                  onChange={(e) => updateConfig("effect", e.target.value)}
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="allow">Allow</option>
                  <option value="deny">Deny</option>
                </select>
              </div>
            )}

            {/* Permissions (for agent-resource edges) */}
            {edgeData.type === "agent-resource" && (
              <div>
                <label className="block text-sm text-slate-300 mb-1">Permissions</label>
                <input
                  type="text"
                  value={Array.isArray(edgeData.config?.permissions) ? edgeData.config.permissions.join(", ") : ""}
                  onChange={(e) => {
                    const permissions = e.target.value.split(",").map((p) => p.trim()).filter(Boolean);
                    updateConfig("permissions", permissions);
                  }}
                  placeholder="read, write, delete"
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            )}

            {/* Rule ID (for policy edges) */}
            {edgeData.type.startsWith("policy-") && (
              <div>
                <label className="block text-sm text-slate-300 mb-1">Rule ID</label>
                <input
                  type="text"
                  value={edgeData.config?.ruleId || ""}
                  onChange={(e) => updateConfig("ruleId", e.target.value)}
                  placeholder="rule-123"
                  className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            )}
          </div>
        </div>

        {/* Policy Information (for policy-governed edges) */}
        {edgeData.metadata?.policyGoverned && (
          <div className="space-y-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></div>
              <label className="block text-sm font-medium text-yellow-400">Policy-Governed Connection</label>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Policy Name</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-yellow-400 font-medium text-sm">
                {edgeData.metadata.policyName || "Unknown"}
              </div>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Policy ID</label>
              <div className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 font-mono text-xs">
                {edgeData.metadata.policyId || "N/A"}
              </div>
            </div>
            <p className="text-xs text-slate-400 italic">
              This connection is controlled by the policy above. Removing the policy will break this connection.
            </p>
          </div>
        )}

        {/* Metadata */}
        {edgeData.metadata && Object.keys(edgeData.metadata).length > 0 && !edgeData.metadata.policyGoverned && (
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Metadata</label>
            <pre className="px-3 py-2 bg-slate-800 rounded-lg text-slate-300 text-xs overflow-x-auto">
              {JSON.stringify(edgeData.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800 flex items-center gap-2">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Save className="w-4 h-4" />
          {isSaving ? "Saving..." : "Save Changes"}
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
        title="Delete Edge"
        message="Are you sure you want to delete this edge? This action cannot be undone."
        itemName={`${edge.source} → ${edge.target}`}
        isLoading={false}
      />
    </div>
  );
}

