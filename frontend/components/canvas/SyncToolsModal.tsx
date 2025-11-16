"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, RefreshCw, CheckCircle, XCircle, Loader2, Wrench } from "lucide-react";
import { api } from "@/lib/api";

interface SyncToolsModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionId: string;
  connectionName: string;
  orgId: string;
}

export function SyncToolsModal({
  isOpen,
  onClose,
  connectionId,
  connectionName,
  orgId,
}: SyncToolsModalProps) {
  const queryClient = useQueryClient();
  const [syncResult, setSyncResult] = useState<any>(null);

  const syncMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/connections/${connectionId}/sync/`);
      return response.data;
    },
    onSuccess: (data) => {
      setSyncResult(data);
      queryClient.invalidateQueries({ queryKey: ["connections", orgId] });
      queryClient.invalidateQueries({ queryKey: ["tools", orgId] });
    },
    onError: (error: any) => {
      console.error("Sync error details:", error.response?.data);
      const errorDetails = error.response?.data?.error || error.response?.data || error.message || "Sync failed";
      const errorMessage = typeof errorDetails === "string" 
        ? errorDetails 
        : JSON.stringify(errorDetails, null, 2);
      setSyncResult({
        error: errorMessage,
      });
    },
  });

  const handleSync = () => {
    setSyncResult(null);
    syncMutation.mutate();
  };

  const handleClose = () => {
    setSyncResult(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-lg w-full shadow-xl">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-green-400" />
            <h2 className="text-lg font-semibold text-white">Sync Tools</h2>
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
            <label className="block text-sm font-medium text-slate-400 mb-2">Connection</label>
            <div className="px-3 py-2 bg-slate-800 rounded-lg text-white">
              {connectionName}
            </div>
          </div>

          {/* Sync Result */}
          {syncResult && (
            <div className={`p-4 rounded-lg border ${
              syncResult.error 
                ? "bg-red-500/10 border-red-500/30" 
                : "bg-green-500/10 border-green-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-3">
                {syncResult.error ? (
                  <XCircle className="w-5 h-5 text-red-400" />
                ) : (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                )}
                <span className={`font-medium ${
                  syncResult.error ? "text-red-400" : "text-green-400"
                }`}>
                  {syncResult.error ? "Sync Failed" : syncResult.message || "Sync Successful"}
                </span>
              </div>
              
              {!syncResult.error && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <Wrench className="w-4 h-4" />
                    <span>Tools created: {syncResult.tools_created || 0}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-slate-300">
                    <RefreshCw className="w-4 h-4" />
                    <span>Tools updated: {syncResult.tools_updated || 0}</span>
                  </div>
                  {syncResult.tool_ids && syncResult.tool_ids.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs text-slate-400 mb-1">Synced Tool IDs:</p>
                      <div className="max-h-32 overflow-y-auto space-y-1">
                        {syncResult.tool_ids.map((toolId: string) => (
                          <div key={toolId} className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300 font-mono">
                            {toolId}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {syncResult.error && (
                <p className="text-sm text-red-400 mt-2">
                  Error: {syncResult.error}
                </p>
              )}
            </div>
          )}
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
            onClick={handleSync}
            disabled={syncMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {syncMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Syncing...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Sync Now
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

