"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation } from "@tanstack/react-query";
import { claudeAgentApi, api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  Shield,
  CheckCircle2,
  Copy,
  ExternalLink,
  AlertCircle,
  Key,
  Globe,
  Loader2,
  ArrowRight,
  Info,
} from "lucide-react";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "info";
}

const AVAILABLE_SCOPES = [
  {
    name: "agent:execute",
    description: "Execute agents and tools",
    default: true,
  },
  {
    name: "tools:read",
    description: "Read available tools",
    default: true,
  },
  {
    name: "runs:read",
    description: "Read execution history",
    default: false,
  },
  {
    name: "agent:read",
    description: "Read agent information",
    default: false,
  },
];

export function ClaudeAgentAuthView() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const [selectedScopes, setSelectedScopes] = useState<string[]>(
    AVAILABLE_SCOPES.filter((s) => s.default).map((s) => s.name)
  );
  const [authorizationUrl, setAuthorizationUrl] = useState<string | null>(null);
  const [generatedState, setGeneratedState] = useState<string | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [tokenInfo, setTokenInfo] = useState<any>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [redirectUri, setRedirectUri] = useState("");

  // Fetch organizations
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

  useEffect(() => {
    if (!orgId && organizations && organizations.length > 0) {
      setCurrentOrg(organizations[0].id);
    }
  }, [organizations, orgId, setCurrentOrg]);

  // Fetch environments
  const { data: environmentsData } = useQuery({
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
    if (!envId && environments && environments.length > 0) {
      setCurrentEnv(environments[0].id);
    }
  }, [environments, envId, setCurrentEnv]);

  // Set default redirect URI
  useEffect(() => {
    if (typeof window !== "undefined" && !redirectUri) {
      const baseUrl = window.location.origin;
      const locale = window.location.pathname.split("/")[1] || "en";
      setRedirectUri(`${baseUrl}/${locale}/claude-agent/callback`);
    }
  }, [redirectUri]);

  // Fetch manifest
  const { data: manifest } = useQuery({
    queryKey: ["claude-agent-manifest"],
    queryFn: async () => {
      const response = await claudeAgentApi.getManifest();
      return response.data;
    },
  });

  const addToast = (message: string, type: "success" | "error" | "info" = "success") => {
    const id = Date.now().toString();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
      addToast(`${label} copied to clipboard`, "success");
    } catch (err) {
      addToast("Failed to copy to clipboard", "error");
    }
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope)
        ? prev.filter((s) => s !== scope)
        : [...prev, scope]
    );
  };

  // Initiate OAuth flow mutation
  const initiateMutation = useMutation({
    mutationFn: async () => {
      if (!orgId || !envId) {
        throw new Error("Please select organization and environment");
      }

      // Call backend to initiate OAuth flow
      // This generates a secure state token and stores it in the cache
      const response = await claudeAgentApi.initiateAuth({
        organization_id: orgId,
        environment_id: envId,
        scopes: selectedScopes,
        redirect_uri: redirectUri,
      });

      const authUrl = response.data.authorization_url;
      const state = response.data.state;

      setGeneratedState(state);
      setAuthorizationUrl(authUrl);
      
      return authUrl;
    },
    onSuccess: () => {
      addToast("Authorization URL generated", "success");
    },
    onError: (error: any) => {
      addToast(
        error.response?.data?.error || error.message || "Failed to initiate OAuth flow",
        "error"
      );
    },
  });

  const handleInitiate = () => {
    initiateMutation.mutate();
  };

  const handleOpenAuthUrl = () => {
    if (authorizationUrl) {
      // Store state in sessionStorage for verification
      if (generatedState) {
        sessionStorage.setItem("claude_oauth_state", generatedState);
      }
      window.open(authorizationUrl, "_blank");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 p-4 md:p-8">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg border shadow-lg ${
              toast.type === "success"
                ? "bg-green-500/10 border-green-500/20 text-green-400"
                : toast.type === "error"
                ? "bg-red-500/10 border-red-500/20 text-red-400"
                : "bg-blue-500/10 border-blue-500/20 text-blue-400"
            }`}
          >
            {toast.type === "success" ? (
              <CheckCircle2 className="w-5 h-5" />
            ) : toast.type === "error" ? (
              <AlertCircle className="w-5 h-5" />
            ) : (
              <Info className="w-5 h-5" />
            )}
            <span className="text-sm">{toast.message}</span>
          </div>
        ))}
      </div>

      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-purple-500/20 rounded-full mb-4">
            <Shield className="w-8 h-8 text-purple-400" />
          </div>
          <h1 className="text-3xl font-bold text-white">
            {t("oauth.title")}
          </h1>
          <p className="text-slate-400 max-w-2xl mx-auto">
            Grant Claude Hosted Agents access to AgentxSuite tools and capabilities via OAuth 2.0
          </p>
        </div>

        {/* Organization & Environment Selection */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Globe className="w-5 h-5 text-purple-400" />
            Organization & Environment
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                {t("oauth.selectOrg")}
              </label>
              <select
                value={orgId || ""}
                onChange={(e) => {
                  setCurrentOrg(e.target.value);
                  setCurrentEnv(null);
                  setAuthorizationUrl(null);
                  setAccessToken(null);
                }}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {organizations.map((org: any) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                {t("oauth.selectEnv")}
              </label>
              <select
                value={envId || ""}
                onChange={(e) => {
                  setCurrentEnv(e.target.value);
                  setAuthorizationUrl(null);
                  setAccessToken(null);
                }}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                disabled={!orgId}
              >
                {environments.map((env: any) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.type})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Redirect URI Configuration */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-purple-400" />
            Redirect URI
          </h2>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Callback URL
            </label>
            <input
              type="text"
              value={redirectUri}
              onChange={(e) => setRedirectUri(e.target.value)}
              placeholder="https://your-domain.com/callback"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="mt-2 text-xs text-slate-500">
              The URL where users will be redirected after authorization
            </p>
          </div>
        </div>

        {/* Scope Selection */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-400" />
            {t("oauth.selectScopes")}
          </h2>
          <div className="space-y-2">
            {AVAILABLE_SCOPES.map((scope) => (
              <label
                key={scope.name}
                className="flex items-start gap-3 p-3 bg-slate-800/50 hover:bg-slate-800 rounded-lg cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedScopes.includes(scope.name)}
                  onChange={() => toggleScope(scope.name)}
                  className="mt-0.5 w-4 h-4 rounded border-slate-600 text-purple-500 focus:ring-2 focus:ring-purple-500"
                />
                <div className="flex-1">
                  <div className="font-medium text-white">{scope.name}</div>
                  <div className="text-sm text-slate-400">{scope.description}</div>
                </div>
                {scope.default && (
                  <span className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
                    Recommended
                  </span>
                )}
              </label>
            ))}
          </div>
        </div>

        {/* Generate Authorization Button */}
        <div className="flex justify-center">
          <button
            onClick={handleInitiate}
            disabled={!orgId || !envId || selectedScopes.length === 0 || initiateMutation.isPending}
            className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-semibold transition-all shadow-lg hover:shadow-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {initiateMutation.isPending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Shield className="w-5 h-5" />
                {t("oauth.authorize")}
              </>
            )}
          </button>
        </div>

        {/* Authorization URL Result */}
        {authorizationUrl && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-400" />
                {t("oauth.success")}
              </h2>
            </div>
            
            <div className="space-y-3">
              {/* Authorization URL */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Authorization URL
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={authorizationUrl}
                    readOnly
                    className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 font-mono text-sm"
                  />
                  <button
                    onClick={() => {
                      copyToClipboard(authorizationUrl, "Authorization URL");
                    }}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
                    title="Copy URL"
                  >
                    <Copy className={`w-4 h-4 ${copied === "Authorization URL" ? "text-green-400" : "text-slate-400"}`} />
                  </button>
                </div>
              </div>

              {/* State Token */}
              {generatedState && (
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    State Token (for verification)
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={generatedState}
                      readOnly
                      className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 font-mono text-sm"
                    />
                  <button
                    onClick={() => {
                      copyToClipboard(generatedState, "State Token");
                    }}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
                    title="Copy State"
                  >
                    <Copy className={`w-4 h-4 ${copied === "State Token" ? "text-green-400" : "text-slate-400"}`} />
                  </button>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Store this state token securely. You'll need it to verify the callback.
                  </p>
                </div>
              )}

              {/* Open Authorization Button */}
              <div className="flex justify-center pt-4">
                <button
                  onClick={handleOpenAuthUrl}
                  className="px-6 py-3 bg-purple-500 hover:bg-purple-600 text-white rounded-lg font-semibold transition-all flex items-center gap-2"
                >
                  Open Authorization Page
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="space-y-2 text-sm text-blue-300">
              <p className="font-semibold">How to use:</p>
              <ol className="list-decimal list-inside space-y-1 text-blue-400/90">
                <li>Select your organization and environment</li>
                <li>Choose the scopes (permissions) you want to grant</li>
                <li>Click "Generate Authorization URL"</li>
                <li>Open the authorization page and approve the request</li>
                <li>You'll be redirected back with an access token</li>
                <li>Use the access token to make API calls from Claude agents</li>
              </ol>
            </div>
          </div>
        </div>

        {/* Manifest Info */}
        {manifest && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-white mb-4">
              AgentxSuite Agent Manifest
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-slate-500">Name:</span>
                <span className="ml-2 text-white">{manifest.name}</span>
              </div>
              <div>
                <span className="text-slate-500">Version:</span>
                <span className="ml-2 text-white">{manifest.version}</span>
              </div>
              <div>
                <span className="text-slate-500">Available Tools:</span>
                <span className="ml-2 text-white">{manifest.tools?.length || 0}</span>
              </div>
              <div>
                <span className="text-slate-500">Auth Type:</span>
                <span className="ml-2 text-white">{manifest.authentication?.type}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

