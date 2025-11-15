"use client";

import { useState } from "react";
import { Bot, Wrench, Database, Shield, Server, Globe, Plus, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CanvasNodeType } from "@/lib/canvasTypes";

interface CanvasToolbarProps {
  onCreateNode: (type: CanvasNodeType, position: { x: number; y: number }) => void;
}

const nodeTypeOptions: Array<{ type: CanvasNodeType; label: string; icon: any; color: string }> = [
  { type: "agent", label: "Agent", icon: Bot, color: "text-purple-400" },
  { type: "tool", label: "Tool", icon: Wrench, color: "text-blue-400" },
  { type: "resource", label: "Resource", icon: Database, color: "text-green-400" },
  { type: "policy", label: "Policy", icon: Shield, color: "text-yellow-400" },
  { type: "server", label: "Server", icon: Server, color: "text-cyan-400" },
  { type: "environment", label: "Environment", icon: Globe, color: "text-pink-400" },
];

export function CanvasToolbar({ onCreateNode }: CanvasToolbarProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleCreate = (type: CanvasNodeType) => {
    // Place new node in center of viewport
    const position = { x: 400, y: 300 };
    onCreateNode(type, position);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors shadow-lg"
      >
        <Plus className="w-4 h-4" />
        <span>Create</span>
        <ChevronDown className={cn("w-4 h-4 transition-transform", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute top-full left-0 mt-2 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-20 min-w-[200px]">
            <div className="p-2">
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-2 py-1 mb-1">
                Create Node
              </div>
              {nodeTypeOptions.map((option) => {
                const Icon = option.icon;
                return (
                  <button
                    key={option.type}
                    onClick={() => handleCreate(option.type)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left text-slate-300 hover:bg-slate-700 rounded-lg transition-colors"
                  >
                    <Icon className={cn("w-5 h-5", option.color)} />
                    <span>{option.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

