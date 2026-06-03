"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter, useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { claudeAgentApi } from "@/lib/api";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Copy,
  AlertTriangle,
  ArrowRight,
  Key,
} from "lucide-react";

export default function ClaudeAgentCallbackPage() {
  const t = useTranslations();
  const searchParams = useSearchParams();
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) || "en";
  
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [tokenInfo, setTokenInfo] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get code and state from URL
        const code = searchParams?.get("code");
        const state = searchParams?.get("state");
        const errorParam = searchParams?.get("error");
        const errorDescription = searchParams?.get("error_description");

        // Check for OAuth error
        if (errorParam) {
          throw new Error(errorDescription || errorParam);
        }

        // Validate required parameters
        if (!code) {
          throw new Error("Authorization code not found in URL");
        }

        // Verify state token (CSRF protection)
        const storedState = sessionStorage.getItem("claude_oauth_state");
        if (storedState && state !== storedState) {
          throw new Error("State mismatch - possible CSRF attack");
        }

        // Clear stored state
        sessionStorage.removeItem("claude_oauth_state");

        // Exchange code for token
        const response = await claudeAgentApi.exchangeToken({
          code: code,
          state: state || undefined,
        });

        // Success!
        setAccessToken(response.data.access_token);
        setTokenInfo(response.data);
        setStatus("success");
      } catch (err: any) {
        console.error("OAuth callback error:", err);
        setError(
          err.response?.data?.error_description ||
          err.response?.data?.error ||
          err.message ||
          "Failed to exchange authorization code"
        );
        setStatus("error");
      }
    };

    handleCallback();
  }, [searchParams]);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleDone = () => {
    router.push(`/${locale}/claude-agent/authorize`);
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {status === "loading" && (
          <div className="text-center space-y-6">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-purple-500/20 rounded-full">
              <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white mb-2">
                Processing Authorization...
              </h1>
              <p className="text-slate-400">
                Exchanging authorization code for access token
              </p>
            </div>
          </div>
        )}

        {status === "success" && accessToken && (
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 space-y-6">
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-500/20 rounded-full">
                <CheckCircle2 className="w-8 h-8 text-green-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white mb-2">
                  {t("oauth.success")}
                </h1>
                <p className="text-slate-400">
                  Your Claude agent now has access to AgentxSuite
                </p>
              </div>
            </div>

            <div className="space-y-4">
              {/* Access Token */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                  <Key className="w-4 h-4 text-purple-400" />
                  Access Token
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={accessToken}
                    readOnly
                    className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 font-mono text-sm"
                  />
                  <button
                    onClick={() => {
                      copyToClipboard(accessToken);
                    }}
                    className="px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors flex items-center gap-2"
                  >
                    <Copy className="w-4 h-4" />
                    {copied ? "Copied!" : t("oauth.copyToken")}
                  </button>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Store this token securely. It will be used to authenticate API requests.
                </p>
              </div>

              {/* Token Info */}
              {tokenInfo && (
                <div className="bg-slate-800/50 rounded-lg p-4 space-y-3">
                  <h3 className="text-sm font-semibold text-white">Token Information</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-slate-500">Token Type:</span>
                      <span className="ml-2 text-white">{tokenInfo.token_type}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Expires In:</span>
                      <span className="ml-2 text-white">
                        {Math.floor(tokenInfo.expires_in / 3600)} hours
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500">Scopes:</span>
                      <span className="ml-2 text-white">{tokenInfo.scope}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Organization:</span>
                      <span className="ml-2 text-white font-mono text-xs">
                        {tokenInfo.organization_id?.substring(0, 8)}...
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Usage Instructions */}
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-blue-300 mb-2">
                  How to use this token:
                </h3>
                <ol className="list-decimal list-inside space-y-1 text-sm text-blue-400/90">
                  <li>Copy the access token above</li>
                  <li>Add it to your Claude agent configuration</li>
                  <li>Use it in the Authorization header: <code className="font-mono text-xs bg-blue-500/20 px-1 rounded">Bearer {"{token}"}</code></li>
                  <li>Make API calls to AgentxSuite endpoints</li>
                </ol>
              </div>

              {/* Actions */}
              <div className="flex justify-center pt-4">
                <button
                  onClick={handleDone}
                  className="px-6 py-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg font-semibold transition-all shadow-lg hover:shadow-purple-500/50 flex items-center gap-2"
                >
                  Done
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="bg-slate-900 border border-red-500/20 rounded-lg p-8 space-y-6">
            <div className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-red-500/20 rounded-full">
                <XCircle className="w-8 h-8 text-red-400" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white mb-2">
                  Authorization Failed
                </h1>
                <p className="text-slate-400">
                  There was a problem completing the authorization
                </p>
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-red-300 mb-1">Error Details</h3>
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-center pt-4">
              <button
                onClick={handleDone}
                className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-semibold transition-all flex items-center gap-2"
              >
                Back to Authorization
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

