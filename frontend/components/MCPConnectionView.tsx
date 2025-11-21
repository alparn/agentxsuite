"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api, mcpServersApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  Copy,
  Download,
  Wifi,
  CheckCircle2,
  Key,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import Link from "next/link";

export function MCPConnectionView() {
  const t = useTranslations("mcpConnect");
  const tCommon = useTranslations("common");
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();

  const [selectedEnvId, setSelectedEnvId] = useState<string | null>(null);
  const [agentToken, setAgentToken] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  
  // Fetch organizations and auto-select first one if none selected
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      return Array.isArray(response.data) 
        ? response.data 
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsResponse) ? orgsResponse : (orgsResponse?.organizations || []);

  // Auto-select first organization if none selected
  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  // Fetch environments
  const { data: environmentsData, isLoading: isLoadingEnvs } = useQuery({
    queryKey: ["environments", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/environments/`);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
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

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const downloadClaudeConfig = async () => {
    if (!orgId || !selectedEnvId || !agentToken) return;
    
    try {
      await mcpServersApi.downloadConfig(orgId, {
        env_id: selectedEnvId,
        token: agentToken,
      });
    } catch (error) {
      console.error("Download failed:", error);
      alert("Failed to download config. Please check your token.");
    }
  };

  if (isLoadingEnvs) {
    return (
      <div className="text-center py-12 text-slate-400">{tCommon("loading")}</div>
    );
  }

  if (!orgId) {
    return (
      <div className="text-center py-12 text-slate-400">
        No organization selected
      </div>
    );
  }

  if (environments.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        No environments found. Please create an environment first.
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

      {/* 1. Environment Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-2">1. Select Environment</h3>
        <p className="text-sm text-slate-400 mb-4">
          Choose the environment for your MCP connection
        </p>
        <select
          value={selectedEnvId || ""}
          onChange={(e) => setSelectedEnvId(e.target.value)}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="">Select environment...</option>
          {environments.map((env: any) => (
            <option key={env.id} value={env.id}>
              {env.name} ({env.type})
            </option>
          ))}
        </select>
      </div>

      {/* 2. Agent Token Input */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Key className="w-5 h-5" />
              2. Provide Agent Token
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              Paste the token from your Agent's Service Account here.
            </p>
          </div>
          <Link 
            href="/agents"
            className="text-sm text-purple-400 hover:text-purple-300 flex items-center gap-1"
          >
            Go to Agents <ExternalLink className="w-3 h-3" />
          </Link>
        </div>

        <div className="space-y-3">
              <input
            type="password"
            value={agentToken}
            onChange={(e) => setAgentToken(e.target.value)}
            placeholder="Paste your agent token (ey...)"
            className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono text-sm"
              />
          {!agentToken && (
            <div className="flex items-center gap-2 text-xs text-amber-400/80">
              <AlertCircle className="w-3 h-3" />
              You need an Agent Token to generate configuration files.
            </div>
          )}
        </div>
      </div>

      {/* 3. Client Integration Cards */}
      {selectedEnvId && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">3. Connect AI Clients</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Claude Desktop Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">✨</span>
            </div>
                <h4 className="text-xl font-semibold text-white">Claude Desktop</h4>
          </div>
              <p className="text-slate-400 mb-4">
                One-click configuration for Claude Desktop with native stdio support
              </p>
              <div className="space-y-3">
            <button
                  onClick={downloadClaudeConfig}
                  disabled={!agentToken}
                  className="w-full px-4 py-3 bg-black hover:bg-slate-900 text-white rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
                  <Download className="w-4 h-4" />
                  Download Config
            </button>
                {!agentToken && (
                  <p className="text-xs text-center text-slate-500">
                    Enter token above to enable download
                  </p>
              )}
          </div>
        </div>

        {/* Claude Code Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-orange-500/20 rounded-lg flex items-center justify-center">
                  <span className="text-2xl">💻</span>
            </div>
                <h4 className="text-xl font-semibold text-white">Claude Code</h4>
          </div>
              <p className="text-slate-400 mb-4">
                Command-line interface for Claude with MCP support
              </p>
            <button
                onClick={() => {
                  const mcpUrl = `${process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090"}/.well-known/mcp`;
                  copyToClipboard(`claude code --mcp-server agentxsuite=${mcpUrl}`, "claude-code");
                }}
                className="w-full px-4 py-3 bg-black hover:bg-slate-900 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
            >
                {copied === "claude-code" ? (
                  <><CheckCircle2 className="w-4 h-4" /> Copied!</>
              ) : (
                  <><Copy className="w-4 h-4" /> Copy Command</>
              )}
            </button>
        </div>

        {/* Gemini CLI Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <span className="text-2xl">💎</span>
            </div>
                <h4 className="text-xl font-semibold text-white">Gemini CLI</h4>
          </div>
              <p className="text-slate-400 mb-4">
                Google Gemini command-line with MCP integration
              </p>
            <button
                onClick={() => {
                  const mcpUrl = `${process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090"}/.well-known/mcp`;
                  copyToClipboard(`gemini --mcp-server agentxsuite=${mcpUrl}`, "gemini");
                }}
                className="w-full px-4 py-3 bg-black hover:bg-slate-900 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {copied === "gemini" ? (
                  <><CheckCircle2 className="w-4 h-4" /> Copied!</>
              ) : (
                  <><Copy className="w-4 h-4" /> Copy Command</>
              )}
            </button>
        </div>

        {/* Cursor Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 hover:border-purple-500/50 transition-colors">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 bg-slate-700 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold text-white">C</span>
            </div>
                <h4 className="text-xl font-semibold text-white">Cursor IDE</h4>
          </div>
              <p className="text-slate-400 mb-4">
                AI-powered code editor with MCP protocol support
              </p>
            <button
              onClick={() => {
                  const mcpUrl = `${process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090"}/.well-known/mcp`;
                  copyToClipboard(mcpUrl, "cursor");
                }}
                className="w-full px-4 py-3 bg-black hover:bg-slate-900 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {copied === "cursor" ? (
                  <><CheckCircle2 className="w-4 h-4" /> Copied!</>
              ) : (
                  <><Copy className="w-4 h-4" /> Copy MCP URL</>
              )}
            </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
