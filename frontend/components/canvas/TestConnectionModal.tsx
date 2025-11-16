"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { X, Wifi, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface TestConnectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  connectionId: string;
  connectionName: string;
  orgId: string;
}

export function TestConnectionModal({
  isOpen,
  onClose,
  connectionId,
  connectionName,
  orgId,
}: TestConnectionModalProps) {
  const [testResult, setTestResult] = useState<any>(null);

  const testMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/connections/${connectionId}/test/`);
      return response.data;
    },
    onSuccess: (data) => {
      setTestResult(data);
    },
    onError: (error: any) => {
      console.error("Test error details:", error.response?.data);
      const errorDetails = error.response?.data?.error || error.response?.data || error.message || "Test failed";
      const errorMessage = typeof errorDetails === "string" 
        ? errorDetails 
        : JSON.stringify(errorDetails, null, 2);
      setTestResult({
        status: "error",
        error: errorMessage,
      });
    },
  });

  const handleTest = () => {
    setTestResult(null);
    testMutation.mutate();
  };

  const handleClose = () => {
    setTestResult(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg max-w-md w-full shadow-xl">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wifi className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Test Connection</h2>
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

          {/* Test Result */}
          {testResult && (
            <div className={`p-4 rounded-lg border ${
              testResult.status === "ok" 
                ? "bg-green-500/10 border-green-500/30" 
                : "bg-red-500/10 border-red-500/30"
            }`}>
              <div className="flex items-center gap-2 mb-2">
                {testResult.status === "ok" ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-400" />
                )}
                <span className={`font-medium ${
                  testResult.status === "ok" ? "text-green-400" : "text-red-400"
                }`}>
                  {testResult.status === "ok" ? "Connection Successful" : "Connection Failed"}
                </span>
              </div>
              {testResult.last_seen_at && (
                <p className="text-sm text-slate-300">
                  Last seen: {new Date(testResult.last_seen_at).toLocaleString()}
                </p>
              )}
              {testResult.error && (
                <p className="text-sm text-red-400 mt-2">
                  Error: {testResult.error}
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
            onClick={handleTest}
            disabled={testMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            {testMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <Wifi className="w-4 h-4" />
                Test Connection
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

