"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Copy, Download, ExternalLink, Wifi, CheckCircle2 } from "lucide-react";

export function MCPConnectionView() {
  const t = useTranslations("mcpConnect");
  const tCommon = useTranslations("common");
  const { currentOrgId: orgId } = useAppStore();
  const [selectedEnvId, setSelectedEnvId] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  // Fetch environments
  const { data: environmentsData, isLoading } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      return Array.isArray(response.data)
        ? response.data
        : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const environments = Array.isArray(environmentsData) ? environmentsData : [];

  // Auto-select first environment
  useEffect(() => {
    if (!selectedEnvId && environments.length > 0) {
      setSelectedEnvId(environments[0].id);
    }
  }, [environments, selectedEnvId]);

  // Get MCP URL for selected environment
  const mcpFabricBaseUrl =
    process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090";

  const getMCPUrl = (env: any) => {
    if (!orgId || !env) return "";
    return `${mcpFabricBaseUrl}/.well-known/mcp`;
  };

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const generateClaudeDesktopConfig = (env: any, token?: string) => {
    const mcpUrl = getMCPUrl(env);
    // Claude Desktop requires stdio-based MCP servers
    // We provide a bridge script that converts HTTP to stdio
    // IMPORTANT: Update the path to mcp-http-bridge.js to match your system
    const tokenPlaceholder = token || "YOUR_TOKEN_HERE";
    
    // Use absolute path - user must update this to match their system
    // Example: "/Users/username/AgentxSuite/docs/mcp-http-bridge.js"
    // Or relative from home: "~/AgentxSuite/docs/mcp-http-bridge.js"
    const bridgeScriptPath = "/path/to/AgentxSuite/docs/mcp-http-bridge.js";
    
    const config = {
      mcpServers: {
        agentxsuite: {
          command: "node",
          args: [
            bridgeScriptPath,
            mcpUrl,
            "--header",
            `Authorization: Bearer ${tokenPlaceholder}`,
          ],
        },
      },
    };
    return JSON.stringify(config, null, 2);
  };

  const downloadClaudeDesktopConfig = (env: any) => {
    const config = generateClaudeDesktopConfig(env);
    const blob = new Blob([config], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "claude-desktop-config.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const generateClaudeCodeCommand = (env: any) => {
    const mcpUrl = getMCPUrl(env);
    return `claude code --mcp-server agentxsuite=${mcpUrl}`;
  };

  const generateGeminiCLICommand = (env: any) => {
    const mcpUrl = getMCPUrl(env);
    return `gemini --mcp-server agentxsuite=${mcpUrl}`;
  };

  const selectedEnv = environments.find((e: any) => e.id === selectedEnvId);
  const mcpUrl = selectedEnv ? getMCPUrl(selectedEnv) : "";

  if (isLoading) {
    return (
      <div className="text-center py-12 text-slate-400">{tCommon("loading")}</div>
    );
  }

  if (!orgId || environments.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        {t("noEnvironments")}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-2">
          <Wifi className="w-8 h-8" />
          {t("title")}
        </h1>
        <p className="text-slate-400">{t("subtitle")}</p>
      </div>

      {/* Environment Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
        <label className="text-sm font-medium text-slate-300 mb-2 block">
          {t("selectEnvironment")}
        </label>
        <select
          value={selectedEnvId || ""}
          onChange={(e) => setSelectedEnvId(e.target.value)}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          {environments.map((env: any) => (
            <option key={env.id} value={env.id}>
              {env.name} ({env.type})
            </option>
          ))}
        </select>
      </div>

      {/* MCP Server URL Display */}
      {selectedEnv && mcpUrl && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-300">
              {t("mcpServerAddress")}
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={mcpUrl}
                className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
              <button
                onClick={() => copyToClipboard(mcpUrl, "url")}
                className="p-2 bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors relative"
                title={t("copy")}
              >
                {copied === "url" ? (
                  <CheckCircle2 className="w-5 h-5 text-green-400" />
                ) : (
                  <Copy className="w-5 h-5 text-white" />
                )}
              </button>
            </div>
            <p className="text-xs text-slate-400">{t("mcpServerDescription")}</p>
          </div>
        </div>
      )}

      {/* Connection Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Claude Desktop Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">✨</span>
            </div>
            <h3 className="text-xl font-semibold text-white">
              {t("claudeDesktop.title")}
            </h3>
          </div>
          <p className="text-slate-400 mb-4">{t("claudeDesktop.description")}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => selectedEnv && downloadClaudeDesktopConfig(selectedEnv)}
              disabled={!selectedEnv}
              className="flex-1 px-4 py-3 bg-black text-white rounded-lg hover:bg-slate-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("claudeDesktop.button")}
            </button>
            <button
              onClick={() =>
                selectedEnv &&
                copyToClipboard(generateClaudeDesktopConfig(selectedEnv), "claude")
              }
              disabled={!selectedEnv}
              className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
              title={t("copy")}
            >
              {copied === "claude" ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : (
                <Copy className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            {t("claudeDesktop.hint")}
          </p>
        </div>

        {/* Claude Code Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">✨</span>
            </div>
            <h3 className="text-xl font-semibold text-white">
              {t("claudeCode.title")}
            </h3>
          </div>
          <p className="text-slate-400 mb-4">{t("claudeCode.description")}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                selectedEnv &&
                copyToClipboard(generateClaudeCodeCommand(selectedEnv), "claudeCode")
              }
              disabled={!selectedEnv}
              className="flex-1 px-4 py-3 bg-black text-white rounded-lg hover:bg-slate-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("claudeCode.button")}
            </button>
            <button
              onClick={() =>
                selectedEnv &&
                copyToClipboard(generateClaudeCodeCommand(selectedEnv), "claudeCode")
              }
              disabled={!selectedEnv}
              className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
              title={t("copy")}
            >
              {copied === "claudeCode" ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : (
                <Copy className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            {t("claudeCode.hint")}
          </p>
        </div>

        {/* Gemini CLI Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">💎</span>
            </div>
            <h3 className="text-xl font-semibold text-white">
              {t("geminiCLI.title")}
            </h3>
          </div>
          <p className="text-slate-400 mb-4">{t("geminiCLI.description")}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                selectedEnv &&
                copyToClipboard(generateGeminiCLICommand(selectedEnv), "gemini")
              }
              disabled={!selectedEnv}
              className="flex-1 px-4 py-3 bg-black text-white rounded-lg hover:bg-slate-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("geminiCLI.button")}
            </button>
            <button
              onClick={() =>
                selectedEnv &&
                copyToClipboard(generateGeminiCLICommand(selectedEnv), "gemini")
              }
              disabled={!selectedEnv}
              className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
              title={t("copy")}
            >
              {copied === "gemini" ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : (
                <Copy className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            {t("geminiCLI.hint")}
          </p>
        </div>

        {/* Cursor Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-white">C</span>
            </div>
            <h3 className="text-xl font-semibold text-white">
              {t("cursor.title")}
            </h3>
          </div>
          <p className="text-slate-400 mb-4">{t("cursor.description")}</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                if (selectedEnv && mcpUrl) {
                  // Try to open Cursor with connection prompt
                  window.open(
                    `cursor://mcp/connect?url=${encodeURIComponent(mcpUrl)}`,
                    "_blank"
                  );
                }
              }}
              disabled={!selectedEnv}
              className="flex-1 px-4 py-3 bg-black text-white rounded-lg hover:bg-slate-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("cursor.button")}
            </button>
            <button
              onClick={() => selectedEnv && copyToClipboard(mcpUrl, "cursor")}
              disabled={!selectedEnv}
              className="p-3 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
              title={t("copy")}
            >
              {copied === "cursor" ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : (
                <Copy className="w-5 h-5 text-white" />
              )}
            </button>
          </div>
          <p className="text-xs text-slate-500 text-center mt-2">
            {t("cursor.hint")}
          </p>
        </div>
      </div>
    </div>
  );
}

