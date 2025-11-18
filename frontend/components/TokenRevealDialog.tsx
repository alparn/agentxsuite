"use client";

import React, { useState } from "react";
import { CheckCircle2, Copy, AlertCircle, X } from "lucide-react";

interface TokenRevealDialogProps {
  open: boolean;
  onClose: () => void;
  tokenString: string;
  tokenName: string;
}

export function TokenRevealDialog({
  open,
  onClose,
  tokenString,
  tokenName,
}: TokenRevealDialogProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(tokenString);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-2xl w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <h3 className="text-xl font-semibold text-white">Token Created Successfully</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-slate-400 mb-6">
          Your token <strong className="text-white">{tokenName}</strong> has been created.
          <br />
          <span className="text-amber-600 font-semibold flex items-center gap-1 mt-2">
            <AlertCircle className="h-4 w-4" />
            Copy it now - you won't see it again!
          </span>
        </p>

        <div className="space-y-4">
          <div className="relative">
            <input
              type="text"
              value={tokenString}
              readOnly
              className="w-full px-4 py-2 pr-24 bg-slate-800 border border-slate-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <button
              onClick={handleCopy}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded transition-colors flex items-center gap-1"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy
                </>
              )}
            </button>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-sm text-amber-800">
            <strong>Security Notice:</strong> Store this token securely (e.g., in
            Claude Desktop config). It won't be displayed again.
          </div>

          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              I've Saved the Token
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
