"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, userTokensApi, mcpServersApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { IssuedToken } from "@/lib/types";
import {
  Copy,
  Download,
  Wifi,
  CheckCircle2,
  Plus,
  Trash2,
  AlertCircle,
  Key,
  Calendar,
  Shield,
  X,
} from "lucide-react";
import { TokenRevealDialog } from "./TokenRevealDialog";

export function MCPConnectionView() {
  const t = useTranslations("mcpConnect");
  const tCommon = useTranslations("common");
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();

  const [selectedEnvId, setSelectedEnvId] = useState<string | null>(null);
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  
  // Token creation dialog state
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [dialogEnvId, setDialogEnvId] = useState<string | null>(null); // Frozen env for dialog
  const [tokenName, setTokenName] = useState("");
  const [tokenPurpose, setTokenPurpose] = useState("claude-desktop");
  const [tokenExpireDays, setTokenExpireDays] = useState("365");
  
  // Token reveal dialog state
  const [revealDialogOpen, setRevealDialogOpen] = useState(false);
  const [newTokenString, setNewTokenString] = useState("");
  const [newTokenName, setNewTokenName] = useState("");
  
  // Delete confirmation dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [tokenToDelete, setTokenToDelete] = useState<IssuedToken | null>(null);
  const [deleteAction, setDeleteAction] = useState<"revoke" | "delete">("revoke");

  // Fetch organizations and auto-select first one if none selected
  const { data: orgsResponse } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await api.get("/auth/me/orgs/");
      // Handle both old format (array) and new format (object with organizations)
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

  // Fetch environments (from backend, not from tokens!)
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

  // Fetch tokens
  const { data: tokens = [], isLoading: isLoadingTokens } = useQuery<IssuedToken[]>({
    queryKey: ["user-tokens", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await userTokensApi.list(orgId);
      
      console.log('[Token Fetch] Raw response:', response);
      console.log('[Token Fetch] response.data:', response.data);
      
      // Handle multiple response formats:
      // Type assertion needed because API can return different formats
      const responseData = response.data as any;
      
      // 1. Direct array: [...]
      if (Array.isArray(responseData)) {
        console.log('[Token Fetch] Direct array format');
        return responseData;
      }
      
      // 2. Paginated: { results: [...] }
      if (responseData?.results) {
        console.log('[Token Fetch] Paginated format');
        return responseData.results;
      }
      
      // 3. Nested data: { data: { results: [...] } }
      if (responseData?.data?.results) {
        console.log('[Token Fetch] Nested format');
        return responseData.data.results;
      }
      
      console.log('[Token Fetch] Fallback to empty array');
      return [];
    },
    enabled: !!orgId,
  });

  // Helper to get environment ID from token (handles both nested object and string)
  const getEnvId = (token: IssuedToken): string => {
    if (typeof token.environment === 'string') {
      return token.environment;
    }
    return token.environment.id;
  };

  // Helper to get environment name from token
  const getEnvName = (token: IssuedToken): string => {
    if (typeof token.environment === 'string') {
      return token.environment_name || token.environment;
    }
    return token.environment.name || token.environment.id;
  };

  // Filter tokens by selected environment
  const filteredTokens = selectedEnvId
    ? tokens.filter((t) => getEnvId(t) === selectedEnvId)
    : tokens;

  // Debug logging (can be removed later)
  useEffect(() => {
    console.log('[MCPConnectionView] Debug:', {
      orgId,
      selectedEnvId,
      tokensCount: tokens.length,
      filteredTokensCount: filteredTokens.length,
      tokens: tokens.map(t => ({
        id: t.id,
        name: t.name,
        envId: getEnvId(t),
      })),
    });
  }, [orgId, selectedEnvId, tokens, filteredTokens]);

  // Auto-select first environment
  useEffect(() => {
    if (!selectedEnvId && environments.length > 0) {
      setSelectedEnvId(environments[0].id);
    }
  }, [environments, selectedEnvId]);

  // Reset selected token when environment changes
  useEffect(() => {
    setSelectedTokenId(null);
  }, [selectedEnvId]);

  // Open dialog and freeze current environment
  const openCreateDialog = () => {
    if (!selectedEnvId) return;
    setDialogEnvId(selectedEnvId); // Freeze environment for this dialog session
    setCreateDialogOpen(true);
  };

  // Close dialog and reset
  const closeCreateDialog = () => {
    setCreateDialogOpen(false);
    setDialogEnvId(null);
    setTokenName("");
    setTokenPurpose("claude-desktop");
    setTokenExpireDays("365");
  };

  // Create token mutation - uses dialogEnvId (frozen)
  const createTokenMutation = useMutation({
    mutationFn: async () => {
      if (!orgId || !dialogEnvId) throw new Error("Missing org or env");
      return userTokensApi.create(orgId, {
        name: tokenName,
        purpose: tokenPurpose,
        environment_id: dialogEnvId, // Use frozen environment!
        expires_in_days: parseInt(tokenExpireDays),
        scopes: ["mcp:tools", "mcp:resources", "mcp:prompts"], // ✅ Correct MCP scopes
      });
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["user-tokens", orgId] });
      closeCreateDialog();
      setNewTokenString(response.data.token);
      setNewTokenName(tokenName);
      setRevealDialogOpen(true);
    },
  });

  // Revoke token mutation (soft delete)
  const revokeTokenMutation = useMutation({
    mutationFn: async (tokenId: string) => {
      if (!orgId) throw new Error("Missing org");
      return userTokensApi.revoke(orgId, tokenId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-tokens", orgId] });
      setDeleteDialogOpen(false);
      setTokenToDelete(null);
    },
  });

  // Delete token mutation (hard delete)
  const deleteTokenMutation = useMutation({
    mutationFn: async (tokenId: string) => {
      if (!orgId) throw new Error("Missing org");
      return userTokensApi.delete(orgId, tokenId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-tokens", orgId] });
      setDeleteDialogOpen(false);
      setTokenToDelete(null);
    },
  });

  const handleDeleteConfirm = () => {
    if (!tokenToDelete) return;
    
    if (deleteAction === "revoke") {
      revokeTokenMutation.mutate(tokenToDelete.id);
    } else {
      deleteTokenMutation.mutate(tokenToDelete.id);
    }
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

  const downloadClaudeConfig = () => {
    if (!orgId || !selectedEnvId) return;
    mcpServersApi.downloadConfig(orgId, {
      env_id: selectedEnvId,
      token_id: selectedTokenId || undefined,
      create_token: !selectedTokenId,
    });
  };

  const getTokenStatus = (
    token: IssuedToken
  ): { label: string; color: string } => {
    if (token.revoked_at) return { label: "Revoked", color: "bg-red-500/10 text-red-400 border-red-500/20" };
    if (token.expires_at && new Date(token.expires_at) < new Date()) {
      return { label: "Expired", color: "bg-slate-500/10 text-slate-400 border-slate-500/20" };
    }
    return { label: "Active", color: "bg-green-500/10 text-green-400 border-green-500/20" };
  };

  if (isLoadingEnvs || isLoadingTokens) {
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

      {/* Environment Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-2">Select Environment</h3>
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

      {/* Token Management Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Key className="w-5 h-5" />
              Access Tokens
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              Manage tokens for Claude Desktop and other MCP clients
            </p>
          </div>
          <button
            onClick={openCreateDialog}
            disabled={!selectedEnvId}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Token
          </button>
        </div>

        {filteredTokens.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No tokens found for this environment.</p>
            <p className="text-sm mt-1">Create one to get started with Claude Desktop.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredTokens.map((token) => {
              const status = getTokenStatus(token);
              const isSelected = selectedTokenId === token.id;
              return (
                <div
                  key={token.id}
                  className={`p-4 border rounded-lg transition-all cursor-pointer ${
                    isSelected
                      ? "border-purple-500 bg-purple-500/10"
                      : "border-slate-700 hover:border-slate-600"
                  }`}
                  onClick={() => setSelectedTokenId(isSelected ? null : token.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium text-white">{token.name}</h4>
                        <span className={`px-2 py-0.5 text-xs rounded border ${status.color}`}>
                          {status.label}
                        </span>
                        {isSelected && (
                          <span className="px-2 py-0.5 text-xs rounded border bg-slate-700/50 text-slate-300 border-slate-600">
                            Selected
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-slate-400 space-y-1">
                        <p className="flex items-center gap-2">
                          <Shield className="w-3 h-3" />
                          Purpose: {token.purpose}
                        </p>
                        <p className="flex items-center gap-2">
                          <Calendar className="w-3 h-3" />
                          Created: {new Date(token.created_at).toLocaleDateString()}
                        </p>
                        {token.expires_at && (
                          <p className="flex items-center gap-2">
                            <Calendar className="w-3 h-3" />
                            Expires: {new Date(token.expires_at).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Revoke Button */}
                      {!token.revoked_at && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setTokenToDelete(token);
                            setDeleteAction("revoke");
                            setDeleteDialogOpen(true);
                          }}
                          className="p-2 text-yellow-400 hover:bg-yellow-500/10 rounded-lg transition-colors"
                          title="Revoke token"
                        >
                          <AlertCircle className="w-4 h-4" />
                        </button>
                      )}
                      {/* Delete Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setTokenToDelete(token);
                          setDeleteAction("delete");
                          setDeleteDialogOpen(true);
                        }}
                        className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                        title="Delete token permanently"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Client Integration Cards */}
      {selectedEnvId && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Connect AI Clients</h3>
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
                <div className="flex items-center gap-2 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs text-slate-300">
                  <AlertCircle className="w-4 h-4 text-blue-400 flex-shrink-0" />
                  {selectedTokenId
                    ? "Selected token will be included"
                    : "New token will be auto-created"}
                </div>
                <button
                  onClick={downloadClaudeConfig}
                  className="w-full px-4 py-3 bg-black hover:bg-slate-900 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download Config
                </button>
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

      {/* Token Creation Dialog */}
      {createDialogOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-white">Create Access Token</h3>
              <button
                onClick={closeCreateDialog}
                className="p-1 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-slate-400 mb-4">
              Generate a new token for MCP client authentication
            </p>

            {/* Show frozen environment */}
            {dialogEnvId && (
              <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                <p className="text-xs text-slate-400 mb-1">Token will be created for:</p>
                <p className="text-sm font-medium text-white">
                  {environments.find((e: any) => e.id === dialogEnvId)?.name || "Unknown"} 
                  <span className="text-slate-400 ml-2">
                    ({environments.find((e: any) => e.id === dialogEnvId)?.type || ""})
                  </span>
                </p>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Token Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., My Claude Desktop Token"
                  value={tokenName}
                  onChange={(e) => setTokenName(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Purpose
                </label>
                <select
                  value={tokenPurpose}
                  onChange={(e) => setTokenPurpose(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="claude-desktop">Claude Desktop</option>
                  <option value="api">API Integration</option>
                  <option value="development">Development</option>
                  <option value="ci-cd">CI/CD</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Expires in (days)
                </label>
                <input
                  type="number"
                  value={tokenExpireDays}
                  onChange={(e) => setTokenExpireDays(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>

            <div className="flex items-center gap-3 mt-6">
              <button
                onClick={closeCreateDialog}
                className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => createTokenMutation.mutate()}
                disabled={!tokenName || createTokenMutation.isPending}
                className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createTokenMutation.isPending ? "Creating..." : "Create Token"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteDialogOpen && tokenToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-semibold text-white">
                {deleteAction === "revoke" ? "Revoke Token" : "Delete Token"}
              </h3>
              <button
                onClick={() => {
                  setDeleteDialogOpen(false);
                  setTokenToDelete(null);
                }}
                className="p-1 text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="p-3 bg-slate-800 rounded-lg">
                <p className="text-sm text-slate-400 mb-1">Token Name:</p>
                <p className="font-medium text-white">{tokenToDelete.name}</p>
              </div>

              {deleteAction === "revoke" ? (
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <p className="text-sm text-yellow-200">
                    <strong>Revoke:</strong> The token will be marked as revoked 
                    and can no longer be used. It will remain visible in the audit log.
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <p className="text-sm text-red-200">
                    <strong>⚠️ Delete Permanently:</strong> This will permanently remove the token 
                    from the database. This action cannot be undone!
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 mt-6">
              <button
                onClick={() => {
                  setDeleteDialogOpen(false);
                  setTokenToDelete(null);
                }}
                className="flex-1 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={revokeTokenMutation.isPending || deleteTokenMutation.isPending}
                className={`flex-1 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  deleteAction === "revoke"
                    ? "bg-yellow-600 hover:bg-yellow-700 text-white"
                    : "bg-red-600 hover:bg-red-700 text-white"
                }`}
              >
                {(revokeTokenMutation.isPending || deleteTokenMutation.isPending)
                  ? "Processing..."
                  : deleteAction === "revoke"
                  ? "Revoke Token"
                  : "Delete Permanently"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Token Reveal Dialog */}
      <TokenRevealDialog
        open={revealDialogOpen}
        onClose={() => setRevealDialogOpen(false)}
        tokenString={newTokenString}
        tokenName={newTokenName}
      />
    </div>
  );
}
