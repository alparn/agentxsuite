"use client";

import { memo, useState, useEffect, useRef } from "react";
import { Handle, Position, NodeProps, Node, useReactFlow } from "@xyflow/react";
import { Bot, Wrench, Database, Shield, Server, Globe, Building2, CheckCircle2, XCircle, AlertCircle, PowerOff, Plus, Play, Wifi, RefreshCw, MessageSquare } from "lucide-react";
import type { CanvasNodeData, CanvasNodeType } from "@/lib/canvasTypes";
import { cn } from "@/lib/utils";
import { getValidTargetTypes, getValidSourceTypes, getAllowedChildNodes, getValidParentTypes } from "@/lib/canvasEdgeValidation";

const nodeIcons = {
  agent: Bot,
  tool: Wrench,
  resource: Database,
  policy: Shield,
  server: Server,
  environment: Globe,
  organization: Building2,
  prompt: MessageSquare,
};

const statusColors = {
  connected: "bg-green-500/20 border-green-500/50 text-green-400",
  error: "bg-red-500/20 border-red-500/50 text-red-400",
  unauthorized: "bg-yellow-500/20 border-yellow-500/50 text-yellow-400",
  disabled: "bg-slate-500/20 border-slate-500/50 text-slate-400",
  unknown: "bg-slate-500/20 border-slate-500/50 text-slate-400",
};

const statusIcons = {
  connected: CheckCircle2,
  error: XCircle,
  unauthorized: AlertCircle,
  disabled: PowerOff,
  unknown: AlertCircle,
};

const nodeTypeOptions: Array<{ type: CanvasNodeType; label: string; icon: typeof Bot }> = [
  { type: "agent", label: "Agent", icon: Bot },
  { type: "tool", label: "Tool", icon: Wrench },
  { type: "resource", label: "Resource", icon: Database },
  { type: "policy", label: "Policy", icon: Shield },
  { type: "server", label: "Server", icon: Server },
  { type: "environment", label: "Environment", icon: Globe },
  { type: "organization", label: "Organization", icon: Building2 },
  { type: "prompt", label: "Prompt", icon: MessageSquare },
];

export const CanvasNode = memo(({ data, selected, id }: NodeProps<Node<CanvasNodeData>>) => {
  const { getNode } = useReactFlow();
  const Icon = nodeIcons[data.type] || Bot;
  const status = data.status || "unknown";
  const StatusIcon = statusIcons[status];
  const statusColor = statusColors[status];
  const [isHovered, setIsHovered] = useState(false);
  const [showMenu, setShowMenu] = useState<"left" | "right" | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  // Show buttons if onCreateNode is available (always show if node can create children/parents)
  const showButtons = !!data.onCreateNode;

  // Close menu when clicking outside
  useEffect(() => {
    if (!showMenu) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (!menuRef.current || !event.target) return;

      const target = event.target as HTMLElement;
      
      // Check if click is inside the menu
      if (menuRef.current.contains(target)) {
        return; // Click is inside menu, don't close
      }

      // Check if click is on a plus button (should toggle menu, not close)
      const isPlusButton = target.closest('button[title*="Create node"]');
      if (isPlusButton) {
        return; // Click is on plus button, let handleCreateNode handle it
      }

      // Click is outside menu and not on plus button, close menu
      setShowMenu(null);
    };

    // Use a small timeout to avoid immediate closing when opening the menu
    const timeoutId = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside, true);
    }, 10);
    
    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener("mousedown", handleClickOutside, true);
    };
  }, [showMenu]);

  const handleCreateNode = (side: "left" | "right", e: React.MouseEvent) => {
    e.stopPropagation();
    if (!data.onCreateNode) return;
    
    // Toggle menu: if same side is clicked again, close it; otherwise open/switch
    if (showMenu === side) {
      setShowMenu(null);
    } else {
      setShowMenu(side);
    }
  };

  const handleSelectNodeType = (nodeType: CanvasNodeType) => {
    if (!data.onCreateNode) return;
    
    // Get current node position from React Flow
    const node = getNode(id);
    const currentPosition = node?.position || { x: 0, y: 0 };
    
    const offsetX = showMenu === "left" ? -250 : 250;
    const newNodePosition = {
      x: currentPosition.x + offsetX,
      y: currentPosition.y,
    };
    
    // Create the selected node type and pass the current node ID as source
    data.onCreateNode(nodeType, newNodePosition, showMenu || "right", id);
    setShowMenu(null);
  };

  // Get node type color for border
  const getNodeBorderColor = () => {
    if (!selected) return "border-slate-700";
    switch (data.type) {
      case "agent": return "border-purple-500 shadow-purple-500/20";
      case "tool": return "border-green-500 shadow-green-500/20";
      case "resource": return "border-amber-500 shadow-amber-500/20";
      case "policy": return "border-yellow-600 shadow-yellow-600/20";
      case "server": return "border-rose-500 shadow-rose-500/20";
      case "environment": return "border-cyan-500 shadow-cyan-500/20";
      case "organization": return "border-indigo-500 shadow-indigo-500/20";
      case "prompt": return "border-blue-500 shadow-blue-500/20";
      default: return "border-purple-500 shadow-purple-500/20";
    }
  };

  return (
    <div
      className={cn(
        "px-4 py-3 rounded-lg border-2 min-w-[180px] bg-slate-900 shadow-lg transition-all relative group",
        getNodeBorderColor(),
        statusColor
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Plus Button Left */}
      {showButtons && data.onCreateNode && data.type !== "policy" && data.type !== "prompt" && data.type !== "environment" && data.type !== "organization" && (() => {
        // Only show left button if there are valid parent types that can create this node
        // Top-level nodes (environment, organization) should not have left button
        const validParentTypes = getValidParentTypes(data.type);
        return validParentTypes.length > 0;
      })() ? (
        <div className="absolute -left-6 top-1/2 -translate-y-1/2 z-50 pointer-events-auto">
          <button
            onClick={(e) => handleCreateNode("left", e)}
            className={cn(
              "w-8 h-8 rounded-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white shadow-lg flex items-center justify-center transition-all hover:scale-110",
              "opacity-100"
            )}
            title="Create parent node"
          >
            <Plus className="w-4 h-4" />
          </button>
          
          {/* Menu for left side */}
          {showMenu === "left" && (() => {
            // When creating on the left, we want to create a PARENT node that can CREATE this node
            // So we need nodes that can create the current node type as a child
            const validParentTypes = getValidParentTypes(data.type);
            const availableOptions = nodeTypeOptions.filter((opt) => validParentTypes.includes(opt.type));
            
            return (
              <div ref={menuRef} className="absolute left-10 top-0 bg-slate-800 border border-slate-700 rounded-lg shadow-xl min-w-[180px] py-2 z-50">
                <div className="px-3 py-2 text-xs font-semibold text-slate-400 border-b border-slate-700">
                  Create Parent (can create {data.type})
                </div>
                {availableOptions.length > 0 ? (
                  availableOptions.map((option) => {
                    const OptionIcon = option.icon;
                    return (
                      <button
                        key={option.type}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectNodeType(option.type);
                        }}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="w-full px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2 transition-colors"
                      >
                        <OptionIcon className="w-4 h-4" />
                        {option.label}
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-2 text-sm text-slate-500">
                    No parent nodes available
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      ) : null}

      {/* Node content */}
      <div className="flex items-start gap-3">
        <div className={cn(
          "p-2 rounded-lg",
          data.type === "agent" && "bg-purple-500/20 text-purple-400",
          data.type === "tool" && "bg-green-500/20 text-green-400",
          data.type === "resource" && "bg-amber-500/20 text-amber-400",
          data.type === "policy" && "bg-yellow-600/20 text-yellow-500",
          data.type === "server" && "bg-rose-500/20 text-rose-400",
          data.type === "environment" && "bg-cyan-500/20 text-cyan-400",
          data.type === "organization" && "bg-indigo-500/20 text-indigo-400",
          data.type === "prompt" && "bg-blue-500/20 text-blue-400",
        )}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-sm text-white truncate">{data.label}</h3>
            {StatusIcon && (
              <StatusIcon className={cn("w-4 h-4 flex-shrink-0", statusColor)} />
            )}
          </div>
          <p className="text-xs text-slate-400 capitalize">{data.type}</p>
          {data.status && (
            <span className={cn("text-xs px-2 py-0.5 rounded mt-1 inline-block", statusColor)}>
              {status}
            </span>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      {data.onAction && (data.type === "server" || data.type === "tool" || data.type === "agent") && (
        <div className="flex items-center gap-1 mt-2 pt-2 border-t border-slate-700/50">
          {data.type === "server" && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  data.onAction?.("test", data.connectionId);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 rounded transition-colors"
                title="Test Connection"
              >
                <Wifi className="w-3 h-3" />
                Test
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  data.onAction?.("sync", data.connectionId);
                }}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-green-500/10 hover:bg-green-500/20 text-green-400 rounded transition-colors"
                title="Sync Tools"
              >
                <RefreshCw className="w-3 h-3" />
                Sync
              </button>
            </>
          )}
          {data.type === "tool" && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                data.onAction?.("run", data.toolId);
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 rounded transition-colors"
              title="Run Tool"
            >
              <Play className="w-3 h-3" />
              Run
            </button>
          )}
          {data.type === "agent" && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                data.onAction?.("ping", data.agentId);
              }}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 rounded transition-colors"
              title="Ping Agent"
            >
              <Wifi className="w-3 h-3" />
              Ping
            </button>
          )}
        </div>
      )}

      {/* Plus Button Right */}
      {showButtons && data.onCreateNode && data.type !== "policy" && data.type !== "prompt" && (() => {
        // Only show right button if there are valid child types that can be created
        const allowedChildren = getAllowedChildNodes(data.type);
        return allowedChildren.length > 0;
      })() && (
        <div className="absolute -right-6 top-1/2 -translate-y-1/2 z-50 pointer-events-auto">
          <button
            onClick={(e) => handleCreateNode("right", e)}
            className={cn(
              "w-8 h-8 rounded-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white shadow-lg flex items-center justify-center transition-all hover:scale-110",
              "opacity-100"
            )}
            title="Create child node"
          >
            <Plus className="w-4 h-4" />
          </button>
          
          {/* Menu for right side */}
          {showMenu === "right" && (() => {
            // When creating on the right, we want to create a CHILD node that this node can CREATE
            // So we need nodes that this node type is allowed to create
            const allowedChildren = getAllowedChildNodes(data.type);
            const availableOptions = nodeTypeOptions.filter((opt) => allowedChildren.includes(opt.type));
            
            return (
              <div ref={menuRef} className="absolute right-10 top-0 bg-slate-800 border border-slate-700 rounded-lg shadow-xl min-w-[180px] py-2 z-50">
                <div className="px-3 py-2 text-xs font-semibold text-slate-400 border-b border-slate-700">
                  Create Child (from {data.type})
                </div>
                {availableOptions.length > 0 ? (
                  availableOptions.map((option) => {
                    const OptionIcon = option.icon;
                    return (
                      <button
                        key={option.type}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectNodeType(option.type);
                        }}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="w-full px-3 py-2 text-left text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2 transition-colors"
                      >
                        <OptionIcon className="w-4 h-4" />
                        {option.label}
                      </button>
                    );
                  })
                ) : (
                  <div className="px-3 py-2 text-sm text-slate-500">
                    No child nodes available
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* Input handles (left side) */}
      {data.type !== "organization" && (
        <Handle
          type="target"
          position={Position.Left}
          id="target-left"
          className="w-3 h-3 bg-green-500 border-2 border-slate-900 hover:bg-green-400 transition-colors"
          style={{ cursor: "crosshair", zIndex: 10 }}
        />
      )}

      {/* Output handles (right side) */}
      {data.type !== "organization" && (
        <Handle
          type="source"
          position={Position.Right}
          id="source-right"
          className="w-3 h-3 bg-purple-500 border-2 border-slate-900 hover:bg-purple-400 transition-colors"
          style={{ cursor: "crosshair", zIndex: 10 }}
        />
      )}
    </div>
  );
});

CanvasNode.displayName = "CanvasNode";

