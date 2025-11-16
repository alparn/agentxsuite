"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X, Wifi, CheckCircle, XCircle, Loader2, Activity } from "lucide-react";
import { api } from "@/lib/api";

interface PingAgentModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentId: string;
  agentName: string;
  orgId: string;
}

export function PingAgentModal({
  isOpen,
  onClose,
  agentId,
  agentName,
  orgId,
}: PingAgentModalProps) {
  const [pingResult, setPingResult] = useState<any>(null);

  const pingMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/orgs/${orgId}/agents/${agentId}/ping/`);
      return response.data;
    },
    onSuccess: (data) => {
      setPingResult(data);
    },
    onError: (error: any) => {
      setPingResult({
        status: "error",
        error: error.response?.data?.error || error.message || "Ping failed",
      });
    },
  });

  const handlePing = () => {
    setPingResult(null);
    pingMutation.mutate();
  };

  const handleClose = () => {
    setPingResult(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-md w-full shadow-xl">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wifi className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Ping Agent</h2>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Agent</label>
            <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
              {agentName}
            </div>
          </div>

          {/* Ping Result */}
          {pingResult && (
            <div className={`p-4 rounded-lg border ${
              pingResult.status === "ok" || pingResult.status === "alive"
                ? "bg-green-500/10 border-green-500/30" 
                : "bg-red-500/10 border-red-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-3">
                {pingResult.status === "ok" || pingResult.status === "alive" ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400" />
                )}
                <span className={`font-medium ${
                  pingResult.status === "ok" || pingResult.status === "alive" ? "text-green-400" : "text-red-400"
                }`}>
                  {pingResult.status === "ok" || pingResult.status === "alive" ? "Agent is Online" : "Agent Unreachable"}
                </span>
              </div>
              
              {(pingResult.status === "ok" || pingResult.status === "alive") && (
                <div className="space-y-2">
                  {pingResult.latency_ms !== undefined && (
                    <div className="flex items-center gap-2 text-sm text-slate-300">
                      <Activity className="w-4 h-4 text-cyan-400" />
                      <span>Latency: <strong className="text-cyan-400">{pingResult.latency_ms}ms</strong></span>
                    </div>
                  )}
                  {pingResult.last_seen_at && (
                    <div className="text-sm text-slate-300">
                      Last seen: {new Date(pingResult.last_seen_at).toLocaleString()}
                    </div>
                  )}
                  {pingResult.version && (
                    <div className="text-sm text-slate-300">
                      Version: {pingResult.version}
                    </div>
                  )}
                  {pingResult.mode && (
                    <div className="text-sm text-slate-300">
                      Mode: <span className="capitalize">{pingResult.mode}</span>
                    </div>
                  )}
                </div>
              )}
              
              {pingResult.error && (
                <p className="text-sm text-red-400 mt-2">
                  Error: {pingResult.error}
                </p>
              )}
            </div>
          )}

          <p className="text-xs text-slate-400 italic">
            Ping verifies agent connectivity and retrieves health status.
          </p>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 flex items-center gap-2 justify-end">
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
          >
            Close
          </button>
          <button
            onClick={handlePing}
            disabled={pingMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {pingMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Pinging...
              </>
            ) : (
              <>
                <Wifi className="w-4 h-4" />
                Ping Agent
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

