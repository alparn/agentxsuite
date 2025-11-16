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
        message: error.response?.data?.message || error.response?.data?.error || error.message || "Ping failed",
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
              pingResult.status === "success"
                ? "bg-green-500/10 border-green-500/30" 
                : pingResult.status === "warning"
                ? "bg-yellow-500/10 border-yellow-500/30"
                : "bg-red-500/10 border-red-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-3">
                {pingResult.status === "success" ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : pingResult.status === "warning" ? (
                  <XCircle className="w-5 h-5 text-yellow-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400" />
                )}
                <span className={`font-medium ${
                  pingResult.status === "success" 
                    ? "text-green-400" 
                    : pingResult.status === "warning"
                    ? "text-yellow-400"
                    : "text-red-400"
                }`}>
                  {pingResult.status === "success" 
                    ? "Agent is Online" 
                    : pingResult.status === "warning"
                    ? "Agent Warning"
                    : "Agent Unreachable"}
                </span>
              </div>
              
              {/* Message */}
              {pingResult.message && (
                <p className={`text-sm mt-2 ${
                  pingResult.status === "success" 
                    ? "text-green-300" 
                    : pingResult.status === "warning"
                    ? "text-yellow-300"
                    : "text-red-300"
                }`}>
                  {pingResult.message}
                </p>
              )}
              
              {/* Success Details */}
              {pingResult.status === "success" && (
                <div className="space-y-2 mt-3">
                  {pingResult.connection_status && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Connection:</span>{" "}
                      <span className="capitalize">{pingResult.connection_status}</span>
                      {pingResult.connection_name && (
                        <span className="text-slate-400"> ({pingResult.connection_name})</span>
                      )}
                    </div>
                  )}
                  {pingResult.connection_endpoint && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Endpoint:</span> {pingResult.connection_endpoint}
                    </div>
                  )}
                  {pingResult.agent_mode && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Mode:</span> <span className="capitalize">{pingResult.agent_mode}</span>
                    </div>
                  )}
                  {pingResult.inbound_auth_method && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Auth Method:</span> <span className="capitalize">{pingResult.inbound_auth_method}</span>
                    </div>
                  )}
                </div>
              )}
              
              {/* Warning/Error Details */}
              {(pingResult.status === "warning" || pingResult.status === "error") && (
                <div className="space-y-2 mt-3">
                  {pingResult.connection_status && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Connection Status:</span>{" "}
                      <span className="capitalize">{pingResult.connection_status}</span>
                    </div>
                  )}
                  {pingResult.connection_endpoint && (
                    <div className="text-sm text-slate-300">
                      <span className="text-slate-400">Endpoint:</span> {pingResult.connection_endpoint}
                    </div>
                  )}
                  {pingResult.note && (
                    <div className="text-sm text-slate-400 italic">
                      {pingResult.note}
                    </div>
                  )}
                </div>
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

