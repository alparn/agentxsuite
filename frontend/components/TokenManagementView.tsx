"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, agentsApi, tokensApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Key, Plus, Copy, Trash2, Ban, CheckCircle2, XCircle, Clock, AlertCircle, Link as LinkIcon } from "lucide-react";
import type { Agent, IssuedToken, TokenGenerateRequest } from "@/lib/types";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "warning";
}

export function TokenManagementView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const queryClient = useQueryClient();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [showGenerateDialog, setShowGenerateDialog] = useState(false);
  const [showServiceAccountDialog, setShowServiceAccountDialog] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

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

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  // Fetch agents
  const { data: agentsData, isLoading: agentsLoading } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await agentsApi.list(orgId);
      return Array.isArray(response.data) ? response.data : response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const agents = (Array.isArray(agentsData) ? agentsData : []) as Agent[];

  // Filter agents with ServiceAccount
  const agentsWithServiceAccount = agents.filter((agent) => agent.service_account);

  // Fetch tokens for selected agent
  const { data: tokensData, isLoading: tokensLoading, refetch: refetchTokens } = useQuery({
    queryKey: ["tokens", orgId, selectedAgent?.id],
    queryFn: async () => {
      if (!orgId || !selectedAgent?.id) return [];
      const response = await tokensApi.list(orgId, selectedAgent.id);
      return Array.isArray(response.data) ? response.data : [];
    },
    enabled: !!orgId && !!selectedAgent?.id,
  });

  const tokens = (Array.isArray(tokensData) ? tokensData : []) as IssuedToken[];

  // Generate token mutation
  const generateMutation = useMutation({
    mutationFn: async (data: TokenGenerateRequest) => {
      if (!orgId || !selectedAgent?.id) throw new Error("Agent not selected");
      const response = await tokensApi.generate(orgId, selectedAgent.id, data);
      return response.data;
    },
    onSuccess: (data) => {
      setNewToken(data.token);
      setShowGenerateDialog(true);
      refetchTokens();
      addToast("Token generated successfully", "success");
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.message || "Failed to generate token",
        "error"
      );
    },
  });

  // Revoke token mutation
  const revokeMutation = useMutation({
    mutationFn: async (jti: string) => {
      if (!orgId || !selectedAgent?.id) throw new Error("Agent not selected");
      await tokensApi.revoke(orgId, selectedAgent.id, jti);
    },
    onSuccess: () => {
      refetchTokens();
      addToast("Token revoked successfully", "success");
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.message || "Failed to revoke token",
        "error"
      );
    },
  });

  // Delete token mutation
  const deleteMutation = useMutation({
    mutationFn: async (jti: string) => {
      if (!orgId || !selectedAgent?.id) throw new Error("Agent not selected");
      await tokensApi.delete(orgId, selectedAgent.id, jti);
    },
    onSuccess: () => {
      refetchTokens();
      addToast("Token deleted successfully", "success");
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.message || "Failed to delete token",
        "error"
      );
    },
  });

  const addToast = (message: string, type: "success" | "error" | "warning") => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    addToast("Copied to clipboard", "success");
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getTokenStatus = (token: IssuedToken) => {
    if (token.is_revoked) return { label: "Revoked", icon: Ban, color: "text-red-400" };
    if (token.is_expired) return { label: "Expired", icon: Clock, color: "text-yellow-400" };
    return { label: "Active", icon: CheckCircle2, color: "text-green-400" };
  };

  const handleGenerateToken = (data: TokenGenerateRequest) => {
    generateMutation.mutate(data);
  };

  const handleRevokeToken = (jti: string) => {
    if (confirm("Are you sure you want to revoke this token?")) {
      revokeMutation.mutate(jti);
    }
  };

  const handleDeleteToken = (jti: string) => {
    if (confirm("Are you sure you want to delete this token? This action cannot be undone.")) {
      deleteMutation.mutate(jti);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Token Management</h1>
        <p className="text-slate-400">Generate and manage JWT tokens for external agents</p>
      </div>

      {/* ServiceAccount Info - Always visible */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <LinkIcon className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm text-blue-400 font-medium mb-1">
              ServiceAccount erforderlich
            </p>
            <p className="text-sm text-slate-400 mb-3">
              Agents benötigen einen ServiceAccount, um Tokens zu generieren. Erstellen Sie zuerst einen ServiceAccount für einen Agent.
            </p>
            {agents.length > 0 && (
              <button
                onClick={() => setShowServiceAccountDialog(true)}
                className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors flex items-center gap-2 text-sm"
              >
                <LinkIcon className="w-4 h-4" />
                ServiceAccount für Agent erstellen
              </button>
            )}
            {agents.length === 0 && (
              <p className="text-xs text-slate-500 italic">
                Erstellen Sie zuerst einen Agent, bevor Sie einen ServiceAccount erstellen können.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Agent Selection */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Select Agent
        </label>
        <select
          value={selectedAgent?.id || ""}
          onChange={(e) => {
            const agent = agents.find((a) => a.id === e.target.value);
            setSelectedAgent(agent || null);
          }}
          className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="">-- Select an agent --</option>
          {agentsWithServiceAccount.map((agent) => (
            <option key={agent.id} value={agent.id}>
              {agent.name} ({agent.environment?.name || "N/A"})
            </option>
          ))}
        </select>
        {agentsWithServiceAccount.length === 0 && (
          <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm text-yellow-400 font-medium mb-2">
                  No agents with ServiceAccount found
                </p>
                <p className="text-sm text-slate-400 mb-3">
                  Agents need a ServiceAccount to generate tokens. Create a ServiceAccount for an agent first.
                </p>
                {agents.length > 0 && (
                  <button
                    onClick={() => setShowServiceAccountDialog(true)}
                    className="px-4 py-2 bg-yellow-500/20 text-yellow-400 rounded-lg hover:bg-yellow-500/30 transition-colors flex items-center gap-2 text-sm"
                  >
                    <LinkIcon className="w-4 h-4" />
                    Create ServiceAccount for Agent
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Token List */}
      {selectedAgent && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">
              Tokens for {selectedAgent.name}
            </h2>
            <button
              onClick={() => setShowGenerateDialog(true)}
              className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Generate Token
            </button>
          </div>

          {tokensLoading ? (
            <p className="text-slate-400">Loading tokens...</p>
          ) : tokens.length === 0 ? (
            <p className="text-slate-400">No tokens generated yet.</p>
          ) : (
            <div className="space-y-3">
              {tokens.map((token) => {
                const status = getTokenStatus(token);
                const StatusIcon = status.icon;
                return (
                  <div
                    key={token.id}
                    className="bg-slate-800 border border-slate-700 rounded-lg p-4"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Key className="w-4 h-4 text-purple-400" />
                          <code className="text-sm text-slate-300 font-mono">
                            {token.jti.substring(0, 8)}...
                          </code>
                          <StatusIcon className={`w-4 h-4 ${status.color}`} />
                          <span className={`text-xs ${status.color}`}>{status.label}</span>
                        </div>
                        <div className="text-sm text-slate-400 space-y-1">
                          <div>Expires: {formatDate(token.expires_at)}</div>
                          {token.revoked_at && (
                            <div>Revoked: {formatDate(token.revoked_at)}</div>
                          )}
                          <div>Scopes: {token.scopes.join(", ")}</div>
                          {token.metadata?.description && (
                            <div>Description: {token.metadata.description}</div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {!token.is_revoked && !token.is_expired && (
                          <button
                            onClick={() => handleRevokeToken(token.jti)}
                            className="p-2 text-yellow-400 hover:bg-slate-700 rounded transition-colors"
                            title="Revoke token"
                          >
                            <Ban className="w-4 h-4" />
                          </button>
                        )}
                        {(token.is_revoked || token.is_expired) && (
                          <button
                            onClick={() => handleDeleteToken(token.jti)}
                            className="p-2 text-red-400 hover:bg-slate-700 rounded transition-colors"
                            title="Delete token"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ServiceAccount Creation Dialog */}
      {showServiceAccountDialog && (
        <ServiceAccountDialog
          agents={agents}
          orgId={orgId}
          isOpen={showServiceAccountDialog}
          onClose={() => {
            setShowServiceAccountDialog(false);
            queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
          }}
        />
      )}

      {/* Generate Token Dialog */}
      {showGenerateDialog && selectedAgent && (
        <GenerateTokenDialog
          agent={selectedAgent}
          isOpen={showGenerateDialog}
          onClose={() => {
            setShowGenerateDialog(false);
            setNewToken(null);
          }}
          onGenerate={handleGenerateToken}
          newToken={newToken}
          isGenerating={generateMutation.isPending}
        />
      )}

      {/* Toast Notifications */}
      <div className="fixed bottom-4 right-4 space-y-2 z-50">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
              toast.type === "success"
                ? "bg-green-500 text-white"
                : toast.type === "error"
                ? "bg-red-500 text-white"
                : "bg-yellow-500 text-white"
            }`}
          >
            {toast.type === "success" && <CheckCircle2 className="w-5 h-5" />}
            {toast.type === "error" && <XCircle className="w-5 h-5" />}
            {toast.type === "warning" && <AlertCircle className="w-5 h-5" />}
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface GenerateTokenDialogProps {
  agent: Agent;
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (data: TokenGenerateRequest) => void;
  newToken: string | null;
  isGenerating: boolean;
}

function GenerateTokenDialog({
  agent,
  isOpen,
  onClose,
  onGenerate,
  newToken,
  isGenerating,
}: GenerateTokenDialogProps) {
  const [ttlMinutes, setTtlMinutes] = useState(30);
  const [description, setDescription] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      ttl_minutes: ttlMinutes,
      scopes: ["mcp:run", "mcp:tools", "mcp:manifest"],
      metadata: description ? { description } : undefined,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {newToken ? (
          <div>
            <h2 className="text-xl font-semibold text-white mb-4">Token Generated</h2>
            <p className="text-slate-400 mb-4">
              Copy this token now. It will not be shown again.
            </p>
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-4">
              <div className="flex items-center justify-between mb-2">
                <code className="text-sm text-slate-300 break-all">{newToken}</code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(newToken);
                  }}
                  className="ml-2 p-2 text-purple-400 hover:bg-slate-700 rounded transition-colors"
                  title="Copy token"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-full px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <h2 className="text-xl font-semibold text-white mb-4">
              Generate Token for {agent.name}
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  TTL (minutes)
                </label>
                <input
                  type="number"
                  min="1"
                  max="1440"
                  value={ttlMinutes}
                  onChange={(e) => setTtlMinutes(parseInt(e.target.value) || 30)}
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <p className="text-xs text-slate-400 mt-1">Maximum: 1440 minutes (24 hours)</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Description (optional)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g., Token for Claude Desktop"
                  className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
            <div className="flex items-center gap-3 mt-6">
              <button
                type="submit"
                disabled={isGenerating}
                className="flex-1 px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors disabled:opacity-50"
              >
                {isGenerating ? "Generating..." : "Generate Token"}
              </button>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

interface ServiceAccountDialogProps {
  agents: Agent[];
  orgId: string | null;
  isOpen: boolean;
  onClose: () => void;
  preselectedAgentId?: string;
}

function ServiceAccountDialog({
  agents,
  orgId,
  isOpen,
  onClose,
  preselectedAgentId,
}: ServiceAccountDialogProps) {
  const [selectedAgentId, setSelectedAgentId] = useState<string>(preselectedAgentId || "");
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [issuer, setIssuer] = useState("");
  const [audience, setAudience] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const queryClient = useQueryClient();

  // Update selectedAgentId when preselectedAgentId changes
  useEffect(() => {
    if (preselectedAgentId) {
      setSelectedAgentId(preselectedAgentId);
    }
  }, [preselectedAgentId]);

  // Reset form when dialog opens/closes
  useEffect(() => {
    if (isOpen) {
      setName("");
      setSubject("");
      setIssuer("");
      setAudience("");
      if (preselectedAgentId) {
        setSelectedAgentId(preselectedAgentId);
      }
    }
  }, [isOpen, preselectedAgentId]);

  // Get MCP Canonical URI from settings (default)
  useEffect(() => {
    if (!audience) {
      setAudience(process.env.NEXT_PUBLIC_MCP_FABRIC_URL || "http://localhost:8090/mcp");
    }
    if (!issuer) {
      setIssuer(process.env.NEXT_PUBLIC_OIDC_ISSUER || "https://agentxsuite.local");
    }
  }, [audience, issuer]);

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      if (!orgId) throw new Error("Organization not selected");
      const response = await api.post(`/orgs/${orgId}/service-accounts/`, data);
      return response.data;
    },
    onSuccess: async (data) => {
      // Link ServiceAccount to Agent
      if (selectedAgentId) {
        try {
          await api.patch(`/orgs/${orgId}/agents/${selectedAgentId}/`, {
            service_account: data.id,
          });
          addToast("ServiceAccount created and linked to agent", "success");
          queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
          onClose();
        } catch (error: any) {
          addToast(
            error.response?.data?.message || "Failed to link ServiceAccount to agent",
            "error"
          );
        }
      } else {
        addToast("ServiceAccount created", "success");
        queryClient.invalidateQueries({ queryKey: ["agents", orgId] });
        onClose();
      }
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.message || "Failed to create ServiceAccount",
        "error"
      );
    },
  });

  const addToast = (message: string, type: "success" | "error" | "warning") => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAgentId) {
      addToast("Please select an agent", "warning");
      return;
    }
    if (!name || !subject || !issuer || !audience) {
      addToast("Please fill all required fields", "warning");
      return;
    }

    createMutation.mutate({
      name,
      subject,
      issuer,
      audience,
      environment: selectedAgent?.environment?.id,
      scope_allowlist: ["mcp:run", "mcp:tools", "mcp:manifest"],
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-semibold text-white mb-4">Create ServiceAccount</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Agent *
            </label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            >
              <option value="">-- Select an agent --</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name} ({agent.environment?.name || "N/A"})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Claude Desktop - Marketing"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Subject (sub) *
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder='e.g., agent:claude-desktop@org/env'
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            />
            <p className="text-xs text-slate-400 mt-1">
              Unique identifier for this ServiceAccount. Format: agent:name@org/env
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Issuer (iss) *
            </label>
            <input
              type="text"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
              placeholder="https://agentxsuite.local"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            />
            <p className="text-xs text-slate-400 mt-1">
              Token issuer URL (must match JWT_ISSUER)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Audience (aud) *
            </label>
            <input
              type="text"
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              placeholder="http://localhost:8090/mcp"
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              required
            />
            <p className="text-xs text-slate-400 mt-1">
              MCP Canonical URI (must match MCP_CANONICAL_URI)
            </p>
          </div>

          <div className="flex items-center gap-3 mt-6">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="flex-1 px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating..." : "Create & Link to Agent"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>

        {/* Toast Notifications */}
        <div className="fixed bottom-4 right-4 space-y-2 z-50">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
                toast.type === "success"
                  ? "bg-green-500 text-white"
                  : toast.type === "error"
                  ? "bg-red-500 text-white"
                  : "bg-yellow-500 text-white"
              }`}
            >
              {toast.type === "success" && <CheckCircle2 className="w-5 h-5" />}
              {toast.type === "error" && <XCircle className="w-5 h-5" />}
              {toast.type === "warning" && <AlertCircle className="w-5 h-5" />}
              <span>{toast.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

