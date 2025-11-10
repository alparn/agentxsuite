"use client";

import { useState } from "react";
import { X } from "lucide-react";

interface ToolRunDialogProps {
  tool: any;
  onRun: (inputJson: Record<string, any>) => void;
  onClose: () => void;
  running: boolean;
  result: any;
  error: string | null;
}

export function ToolRunDialog({
  tool,
  onRun,
  onClose,
  running,
  result,
  error,
}: ToolRunDialogProps) {
  const [args, setArgs] = useState<Record<string, any>>({});

  // Parse JSON Schema to generate form fields
  const schema = tool.schema_json || {};
  const properties = schema.properties || {};
  const required = schema.required || [];
  
  // Get description from schema
  const toolDescription = schema.description || "";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRun(args);
  };

  const updateArg = (key: string, value: any) => {
    setArgs((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-white">Run Tool: {tool.name}</h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded transition-colors"
            disabled={running}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {toolDescription && (
          <p className="text-slate-400 mb-4">{toolDescription}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {Object.entries(properties).map(([key, prop]: [string, any]) => (
            <div key={key}>
              <label className="block text-sm font-medium mb-1 text-slate-300">
                {prop.title || key}
                {required.includes(key) && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </label>
              {renderSchemaField(key, prop, args, updateArg, required)}
            </div>
          ))}

          {Object.keys(properties).length === 0 && (
            <p className="text-slate-400">No parameters required</p>
          )}

          <div className="flex gap-2 justify-end mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors"
              disabled={running}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={running}
            >
              {running ? "Running..." : "Run Tool"}
            </button>
          </div>
        </form>

        {result && (
          <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded">
            <h3 className="font-semibold mb-2 text-green-400">Result:</h3>
            <div className="space-y-2 text-sm text-green-300">
              {result.status && (
                <div>
                  <span className="font-medium">Status:</span>{" "}
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    result.status === "succeeded"
                      ? "bg-green-500/20 text-green-400"
                      : result.status === "failed"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-yellow-500/20 text-yellow-400"
                  }`}>
                    {result.status}
                  </span>
                </div>
              )}
              {result.output_json && (
                <div>
                  <span className="font-medium">Output:</span>
                  <pre className="mt-1 whitespace-pre-wrap overflow-x-auto">
                    {formatResult(result.output_json)}
                  </pre>
                </div>
              )}
              {result.error_text && (
                <div>
                  <span className="font-medium">Error:</span>{" "}
                  <span className="text-red-300">{result.error_text}</span>
                </div>
              )}
              {result.id && (
                <div className="text-xs text-slate-400 mt-2">
                  Run ID: {result.id}
                </div>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded">
            <h3 className="font-semibold mb-2 text-red-400">Error:</h3>
            <pre className="whitespace-pre-wrap text-sm text-red-300 overflow-x-auto">
              {error}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function renderSchemaField(
  key: string,
  prop: any,
  args: Record<string, any>,
  updateArg: (key: string, value: any) => void,
  required: string[]
) {
  const propType = prop.type || (Array.isArray(prop.type) ? prop.type[0] : "string");
  const isRequired = required.includes(key);

  // Handle enum
  if (prop.enum && Array.isArray(prop.enum)) {
    return (
      <>
        <select
          value={args[key] || ""}
          onChange={(e) => updateArg(key, e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
        >
          <option value="">Select {key}...</option>
          {prop.enum.map((value: any) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle boolean
  if (propType === "boolean") {
    return (
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={args[key] || false}
          onChange={(e) => updateArg(key, e.target.checked)}
          className="w-4 h-4 rounded"
        />
        <span className="text-slate-400 text-sm">
          {prop.description || key}
        </span>
      </div>
    );
  }

  // Handle array
  if (propType === "array") {
    const arrayValue = Array.isArray(args[key]) ? args[key] : [];
    return (
      <>
        <textarea
          value={JSON.stringify(arrayValue, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (Array.isArray(parsed)) {
                updateArg(key, parsed);
              }
            } catch {
              // Invalid JSON, ignore
            }
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
          placeholder='["item1", "item2"]'
          rows={3}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle object
  if (propType === "object") {
    const objectValue = typeof args[key] === "object" && args[key] !== null ? args[key] : {};
    return (
      <>
        <textarea
          value={JSON.stringify(objectValue, null, 2)}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (typeof parsed === "object" && parsed !== null) {
                updateArg(key, parsed);
              }
            } catch {
              // Invalid JSON, ignore
            }
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
          placeholder='{"key": "value"}'
          rows={4}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle string with format
  if (propType === "string" && prop.format === "textarea") {
    return (
      <>
        <textarea
          value={args[key] || ""}
          onChange={(e) => updateArg(key, e.target.value)}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
          placeholder={prop.description || key}
          rows={4}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Handle number/integer
  if (propType === "number" || propType === "integer") {
    return (
      <>
        <input
          type="number"
          value={args[key] || ""}
          onChange={(e) => {
            const value = propType === "integer" 
              ? parseInt(e.target.value, 10) || 0
              : parseFloat(e.target.value) || 0;
            updateArg(key, value);
          }}
          className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          required={isRequired}
          placeholder={prop.description || key}
          min={prop.minimum}
          max={prop.maximum}
          step={propType === "integer" ? 1 : undefined}
        />
        {prop.description && (
          <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
        )}
      </>
    );
  }

  // Default: text input
  return (
    <>
      <input
        type="text"
        value={args[key] || ""}
        onChange={(e) => updateArg(key, e.target.value)}
        className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
        required={isRequired}
        placeholder={prop.description || key}
        pattern={prop.pattern}
        minLength={prop.minLength}
        maxLength={prop.maxLength}
      />
      {prop.description && (
        <p className="text-xs text-slate-500 mt-1">{prop.description}</p>
      )}
    </>
  );
}

function formatResult(result: any): string {
  // Try to parse and format as JSON if possible
  if (typeof result === "object") {
    return JSON.stringify(result, null, 2);
  }
  try {
    const parsed = JSON.parse(result);
    return JSON.stringify(parsed, null, 2);
  } catch {
    // Not JSON, return as-is
    return String(result);
  }
}

