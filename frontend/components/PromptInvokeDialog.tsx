"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";
import { mcpFabric } from "@/lib/mcpFabric";
import { X, CheckCircle2, XCircle } from "lucide-react";
import type { Prompt } from "@/lib/types";

interface PromptInvokeDialogProps {
  prompt: Prompt;
  onClose: () => void;
  orgId: string;
  envId: string;
  agentToken?: string | null; // Add agentToken prop
}

export function PromptInvokeDialog({
  prompt,
  onClose,
  orgId,
  envId,
  agentToken,
}: PromptInvokeDialogProps) {
  const t = useTranslations();
  const [inputValues, setInputValues] = useState<Record<string, any>>({});
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Parse input schema
  const inputSchema = prompt.input_schema || {};
  const properties = inputSchema.properties || {};
  const required = inputSchema.required || [];

  const invokeMutation = useMutation({
    mutationFn: async (input: Record<string, any>) => {
      // Check if token is available
      if (!agentToken) {
        throw new Error("Agent token is required. Please ensure an agent with a ServiceAccount is selected.");
      }
      return mcpFabric.invokePrompt(orgId, envId, prompt.name, input, agentToken);
    },
    onSuccess: (data) => {
      setResult(data);
      setError(null);
    },
    onError: (err: any) => {
      setError(err.message || t("prompts.invokeError"));
      setResult(null);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    invokeMutation.mutate(inputValues);
  };

  const updateInput = (key: string, value: any) => {
    setInputValues((prev) => ({ ...prev, [key]: value }));
  };

  const renderSchemaField = (key: string, prop: any, value: any, onChange: (key: string, val: any) => void, requiredFields: string[]) => {
    const isRequired = requiredFields.includes(key);
    const fieldType = prop.type || "string";

    switch (fieldType) {
      case "number":
      case "integer":
        return (
          <input
            type="number"
            value={value || ""}
            onChange={(e) => onChange(key, fieldType === "integer" ? parseInt(e.target.value) : parseFloat(e.target.value))}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            required={isRequired}
            placeholder={prop.default?.toString() || ""}
          />
        );
      case "boolean":
        return (
          <input
            type="checkbox"
            checked={value || false}
            onChange={(e) => onChange(key, e.target.checked)}
            className="w-4 h-4 text-purple-600 bg-slate-800 border-slate-700 rounded focus:ring-purple-500"
          />
        );
      case "array":
        return (
          <textarea
            value={Array.isArray(value) ? JSON.stringify(value, null, 2) : ""}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                if (Array.isArray(parsed)) {
                  onChange(key, parsed);
                }
              } catch {
                // Invalid JSON, ignore
              }
            }}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-purple-500"
            rows={3}
            placeholder="[]"
          />
        );
      default:
        return (
          <input
            type="text"
            value={value || ""}
            onChange={(e) => onChange(key, e.target.value)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            required={isRequired}
            placeholder={prop.default || ""}
          />
        );
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-white">{t("prompts.invokePrompt")}</h2>
            <p className="text-slate-400 text-sm mt-1">{prompt.name}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          {prompt.description && (
            <div className="p-3 bg-slate-800 rounded-lg text-slate-300 text-sm">
              {prompt.description}
            </div>
          )}

          {/* Input Fields */}
          {Object.keys(properties).length > 0 ? (
            Object.entries(properties).map(([key, prop]: [string, any]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  {prop.title || key}
                  {required.includes(key) && <span className="text-red-500 ml-1">*</span>}
                </label>
                {prop.description && (
                  <p className="text-xs text-slate-400 mb-2">{prop.description}</p>
                )}
                {renderSchemaField(key, prop, inputValues[key], updateInput, required)}
              </div>
            ))
          ) : (
            <p className="text-slate-400 text-sm">{t("prompts.noInputRequired")}</p>
          )}

          {/* Buttons */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-300 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={invokeMutation.isPending}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {invokeMutation.isPending ? t("common.loading") : t("prompts.invoke")}
            </button>
          </div>

          {/* Result */}
          {result && (
            <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
                <h3 className="font-semibold text-green-400">{t("prompts.invokeSuccess")}</h3>
              </div>
              <div className="space-y-2 text-sm text-slate-300">
                {result.messages?.map((msg: any, idx: number) => (
                  <div key={idx} className="p-2 bg-slate-800 rounded">
                    <div className="text-xs text-slate-400 mb-1">{msg.role}</div>
                    <div className="text-white">
                      {typeof msg.content === "string"
                        ? msg.content
                        : Array.isArray(msg.content)
                        ? msg.content.map((c: any, i: number) => (
                            <div key={i}>{c.text || JSON.stringify(c)}</div>
                          ))
                        : JSON.stringify(msg.content, null, 2)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-5 h-5 text-red-400" />
                <h3 className="font-semibold text-red-400">{t("common.error")}</h3>
              </div>
              <p className="text-red-300 text-sm">{error}</p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}

