"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { X, Link as LinkIcon, AlertCircle } from "lucide-react";
import type { Agent } from "@/lib/types";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "warning";
}

interface ServiceAccountDialogProps {
  agents: Agent[];
  orgId: string | null;
  isOpen: boolean;
  onClose: () => void;
  preselectedAgentId?: string;
}

export function ServiceAccountDialog({
  agents,
  orgId,
  isOpen,
  onClose,
  preselectedAgentId,
}: ServiceAccountDialogProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(preselectedAgentId || "");
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [issuer, setIssuer] = useState("");
  const [audience, setAudience] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const queryClient = useQueryClient();

  // Update selectedAgentId when preselectedAgentId changes
  useEffect(() => {
    if (preselectedAgentId) {
      setSelectedAgentId(preselectedAgentId);
    }
  }, [preselectedAgentId]);

  // Reset form when dialog opens/closes
  useEffect(() => {
    if (isOpen) {
      setName("");
      setSubject("");
      setIssuer("");
      setAudience("");
      if (preselectedAgentId) {
        setSelectedAgentId(preselectedAgentId);
      }
    }
  }, [isOpen, preselectedAgentId]);

  // Get MCP Canonical URI from settings (default)
  useEffect(() => {
    if (!audience) {
      setAudience(process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090/mcp");
    }
    if (!issuer) {
      setIssuer(process.env.NEXT_PUBLIC_OIDC_ISSUER || "https://agentxsuite.local");
    }
  }, [audience, issuer]);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      if (!orgId) throw new Error("Organization not selected");
      const response = await api.post(`/orgs/${orgId}/service-accounts/`, data);
      return response.data;
    },
    onSuccess: async (data) => {
      // Link ServiceAccount to Agent
      if (selectedAgentId) {
        try {
          await api.patch(`/orgs/${orgId}/agents/${selectedAgentId}/`, {
            service_account: data.id,
          });
          addToast("ServiceAccount erstellt und mit Agent verknüpft", "success");
          queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
          onClose();
        } catch (error: any) {
          addToast(
            error.response?.data?.message || "Fehler beim Verknüpfen des ServiceAccounts mit dem Agent",
            "error"
          );
        }
      } else {
        addToast("ServiceAccount erstellt", "success");
        queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
        onClose();
      }
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.message || "Fehler beim Erstellen des ServiceAccounts",
        "error"
      );
    },
  });

  const addToast = (message: string, type: "success" | "error" | "warning") => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgentId) {
      addToast("Bitte wählen Sie einen Agent aus", "warning");
      return;
    }
    if (!name || !subject || !issuer || !audience) {
      addToast("Bitte füllen Sie alle Pflichtfelder aus", "warning");
      return;
    }

    createMutation.mutate({
      name,
      subject,
      issuer,
      audience,
      environment: selectedAgent?.environment?.id,
      scope_allowlist: ["mcp:run", "mcp:tools", "mcp:manifest"],
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <LinkIcon className="w-5 h-5 text-blue-400" />
            <h2 className="text-xl font-semibold text-white">ServiceAccount erstellen</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Agent *
            </label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              required
              disabled={!!preselectedAgentId}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="">-- Agent auswählen --</option>
              {agents
                .filter((a) => !a.service_account) // Only show agents without ServiceAccount
                .map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} ({agent.environment?.name || "N/A"})
                  </option>
                ))}
            </select>
            {preselectedAgentId && (
              <p className="mt-1 text-xs text-slate-500">
                Agent ist bereits ausgewählt
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="z.B. claude-desktop-sa"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Subject *
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              placeholder="z.B. agent:claude@org/env"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="mt-1 text-xs text-slate-500">
              Eindeutiger Identifier für den externen Agent
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Issuer *
            </label>
            <input
              type="text"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              required
              placeholder="https://agentxsuite.local"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="mt-1 text-xs text-slate-500">
              OIDC Issuer URL
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Audience *
            </label>
            <input
              type="text"
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              required
              placeholder="http://localhost:8090/mcp"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="mt-1 text-xs text-slate-500">
              MCP Fabric URL
            </p>
          </div>

          <div className="flex items-center gap-4 pt-4">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createMutation.isPending ? "Erstellen..." : "ServiceAccount erstellen"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </form>

        {/* Toast notifications */}
        <div className="fixed bottom-4 right-4 space-y-2 z-50">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`p-4 rounded-lg shadow-lg flex items-center gap-3 ${
                toast.type === "success"
                  ? "bg-green-500/20 border border-green-500/30 text-green-400"
                  : toast.type === "error"
                  ? "bg-red-500/20 border border-red-500/30 text-red-400"
                  : "bg-yellow-500/20 border border-yellow-500/30 text-yellow-400"
              }`}
            >
              <AlertCircle className="w-5 h-5" />
              <span className="text-sm font-medium">{toast.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

