"use client";

import { useState, useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, agentsApi, tokensApi } from "@/lib/api";
import { mcpFabric } from "@/lib/mcpFabric";
import { useAppStore } from "@/lib/store";
import {
  Send,
  Bot,
  ChevronDown,
  Plus,
  ArrowUp,
  Play,
  Bell,
  Wrench,
  Globe,
  Loader2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Copy,
  ChevronRight,
  Info,
  Zap,
  Trash2,
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  toolCalls?: Array<{
    tool: string;
    input: Record<string, any>;
    result?: any;
    error?: string;
  }>;
}

interface Thread {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export function AxCoreChat() {
  const t = useTranslations();
  const { currentOrgId: orgId, currentEnvId: envId, setCurrentOrg, setCurrentEnv } = useAppStore();
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [agentToken, setAgentToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
  const [showAgentSelect, setShowAgentSelect] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showSidebar, setShowSidebar] = useState(false); // Hidden on mobile by default
  const [showCreateAgentDialog, setShowCreateAgentDialog] = useState(false);
  const [newAgentName, setNewAgentName] = useState("");
  const [expandedMessages, setExpandedMessages] = useState<Set<string>>(new Set());
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [showCommandSuggestions, setShowCommandSuggestions] = useState(false);
  const [commandQuery, setCommandQuery] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Show sidebar on desktop by default
  useEffect(() => {
    const checkScreenSize = () => {
      if (window.innerWidth >= 1024) {
        setShowSidebar(true);
      }
    };
    checkScreenSize();
    window.addEventListener("resize", checkScreenSize);
    return () => window.removeEventListener("resize", checkScreenSize);
  }, []);

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

  // Auto-select first environment if none selected
  useEffect(() => {
    if (!envId && environments && environments.length > 0 && orgId) {
      setCurrentEnv(environments[0].id);
    }
  }, [environments, envId, orgId, setCurrentEnv]);

  // Fetch AxCore agents
  const { data: agentsData } = useQuery({
    queryKey: ["agents", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/agents/`);
      if (Array.isArray(response.data)) {
        return response.data;
      }
      return response.data?.results || [];
    },
    enabled: !!orgId,
  });

  const agents = Array.isArray(agentsData)
    ? agentsData.filter((a: any) => a.is_axcore || a.tags?.includes("axcore"))
    : [];

  // Auto-select first AxCore agent
  useEffect(() => {
    if (agents.length > 0 && !selectedAgent && orgId && envId) {
      const firstAgent = agents[0];
      setSelectedAgent(firstAgent);
      loadAgentToken(firstAgent.id);
    }
  }, [agents, orgId, envId]);

  // Load token for agent
  const loadAgentToken = async (agentId: string) => {
    if (!orgId) return;
    try {
      // Try to get existing tokens first
      const tokensResponse = await tokensApi.list(orgId, agentId);
      const tokens = tokensResponse.data || [];
      
      // Find non-revoked, non-expired token
      const activeToken = tokens.find(
        (t: any) => !t.revoked_at && new Date(t.expires_at) > new Date()
      );

      if (activeToken) {
        // Token exists but we need the actual token string
        // We'll need to generate a new one or store it
        generateNewToken(agentId);
      } else {
        generateNewToken(agentId);
      }
    } catch (error) {
      console.error("Failed to load tokens:", error);
      generateNewToken(agentId);
    }
  };

  const generateNewToken = async (agentId: string) => {
    if (!orgId || !envId) return;
    try {
      const response = await tokensApi.generate(orgId, agentId, {
        ttl_minutes: 60,
        scopes: ["mcp:run", "mcp:tools", "mcp:manifest"],
      });
      setAgentToken(response.data.token);
    } catch (error: any) {
      console.error("Failed to generate token:", error);
      const errorMessage = error.response?.data?.message || 
                          error.response?.data?.error || 
                          "Failed to generate agent token. Please ensure the agent has a ServiceAccount configured.";
      // Show error to user (could be displayed in UI)
      console.error("Token generation error:", errorMessage);
      // Don't set token if generation fails
      setAgentToken(null);
    }
  };

  // Reset token when environment changes
  useEffect(() => {
    setAgentToken(null);
    setSelectedAgent(null);
  }, [envId]);

  // Fetch available tools with agent token
  // IMPORTANT: Include envId in queryKey so tools are refetched when environment changes
  const { data: toolsData, error: toolsError } = useQuery({
    queryKey: ["mcp-tools", orgId, envId, agentToken],
    queryFn: async () => {
      if (!orgId || !envId || !agentToken) return [];
      try {
        // Use mcpFabric client for consistent response handling
        const response = await mcpFabric.getTools(orgId, envId, agentToken);
        // Handle both formats: {tools: [...]} or direct array
        return Array.isArray(response) ? response : (Array.isArray(response?.tools) ? response.tools : []);
      } catch (error: any) {
        console.error("Failed to fetch tools:", error);
        // Log detailed error for debugging
        if (error.response) {
          console.error("Response status:", error.response.status);
          console.error("Response data:", error.response.data);
        } else if (error.request) {
          console.error("No response received. Server might be down or unreachable.");
        } else {
          console.error("Error setting up request:", error.message);
        }
        throw error; // Re-throw to let React Query handle it
      }
    },
    enabled: !!orgId && !!envId && !!agentToken,
    retry: 2, // Retry twice on failure
    retryDelay: 1000, // Wait 1 second between retries
  });

  const tools = toolsData || [];
  
  // Filter system tools (agentxsuite_*)
  const systemTools = tools.filter((tool: any) => tool.name?.startsWith("agentxsuite_"));

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load threads from localStorage
  useEffect(() => {
    const savedThreads = localStorage.getItem("axcore_threads");
    if (savedThreads) {
      try {
        const parsed = JSON.parse(savedThreads);
        setThreads(parsed.map((t: any) => ({
          ...t,
          createdAt: new Date(t.createdAt),
          updatedAt: new Date(t.updatedAt),
          messages: t.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp),
          })),
        })));
      } catch (error) {
        console.error("Failed to load threads:", error);
      }
    }
  }, []);

  // Save threads to localStorage
  const saveThreads = (updatedThreads: Thread[]) => {
    localStorage.setItem("axcore_threads", JSON.stringify(updatedThreads));
    setThreads(updatedThreads);
  };

  // Create new thread
  const createNewThread = (): Thread => {
    const thread: Thread = {
      id: Date.now().toString(),
      title: "New conversation",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    const updated = [thread, ...threads];
    saveThreads(updated);
    return thread;
  };

  // Update thread title from first user message
  const updateThreadTitle = (threadId: string, title: string) => {
    const updated = threads.map((t) =>
      t.id === threadId ? { ...t, title, updatedAt: new Date() } : t
    );
    saveThreads(updated);
  };

  // Delete thread
  const deleteThread = (threadId: string, e?: React.MouseEvent) => {
    e?.stopPropagation(); // Prevent thread selection when clicking delete
    if (confirm("Are you sure you want to delete this thread?")) {
      const updated = threads.filter((t) => t.id !== threadId);
      saveThreads(updated);
      // If deleted thread was current, clear it
      if (currentThreadId === threadId) {
        setCurrentThreadId(null);
        setMessages([]);
      }
    }
  };

  // Process user message and call tools
  const processMessage = async (userMessage: string) => {
    if (!orgId || !envId || !agentToken || !selectedAgent) {
      addMessage("system", "Please select an AxCore agent first.");
      return;
    }

    setIsProcessing(true);

    // Add user message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: userMessage,
      timestamp: new Date(),
    };
    addMessage("user", userMessage);

    try {
      // Check for slash commands first
      const slashCommand = parseSlashCommand(userMessage);
      const toolCalls: Array<{ tool: string; input: Record<string, any> }> = [];

      if (slashCommand) {
        toolCalls.push(slashCommand);
      } else {
        // Fallback to natural language detection
        // Simple tool detection - check if message contains tool names
        // In a real implementation, you'd use an LLM to determine which tools to call
        if (userMessage.toLowerCase().includes("list agents") || userMessage.toLowerCase().includes("show agents")) {
          toolCalls.push({
            tool: "agentxsuite_list_agents",
            input: { enabled_only: true },
          });
        } else if (userMessage.toLowerCase().includes("list tools")) {
          toolCalls.push({
            tool: "agentxsuite_list_tools",
            input: { enabled_only: true },
          });
        } else if (userMessage.toLowerCase().includes("list connections")) {
          toolCalls.push({
            tool: "agentxsuite_list_connections",
            input: {},
          });
        } else if (userMessage.toLowerCase().includes("list runs")) {
          toolCalls.push({
            tool: "agentxsuite_list_runs",
            input: { limit: 10 },
          });
        } else if (userMessage.toLowerCase().includes("create agent")) {
          // Extract agent name from message (simple extraction)
          const nameMatch = userMessage.match(/create agent (?:named|called)?\s*["']?([^"']+)["']?/i);
          if (nameMatch) {
            toolCalls.push({
              tool: "agentxsuite_create_agent",
              input: {
                name: nameMatch[1],
                mode: "runner",
                enabled: true,
              },
            });
          } else {
            addMessage(
              "assistant",
              "To create an agent, please specify a name. Example: '/create agent MyAgent' or 'Create agent named MyAgent'"
            );
            setIsProcessing(false);
            return;
          }
        }
      }

      // If no tool detected, provide help
      if (toolCalls.length === 0) {
        addMessage(
          "assistant",
          `I can help you manage AgentxSuite. Available commands:

**Slash Commands:**
- /list agents - Show all agents
- /list tools - Show all tools
- /list connections - Show all connections
- /list runs - Show recent runs
- /create agent [name] - Create a new agent

**Natural Language:**
- "List agents" - Show all agents
- "Create agent named [name]" - Create a new agent

You can also ask questions about your systems.`
        );
        setIsProcessing(false);
        return;
      }

      // Execute tool calls
      const toolResults: Array<{
        tool: string;
        input: Record<string, any>;
        result?: any;
        error?: string;
      }> = [];

      for (const toolCall of toolCalls) {
        try {
          // Use mcpFabric client for consistent response handling
          const { mcpFabric } = await import("@/lib/mcpFabric");
          const result = await mcpFabric.runTool(
            orgId!,
            envId!,
            toolCall.tool,
            toolCall.input,
            agentToken
          );

          if (result.isError) {
            toolResults.push({
              tool: toolCall.tool,
              input: toolCall.input,
              error: result.content?.[0]?.text || "Unknown error",
            });
          } else {
            const resultText = result.content
              ?.map((item: any) => item.text || JSON.stringify(item))
              .join("\n") || JSON.stringify(result, null, 2);
            
            toolResults.push({
              tool: toolCall.tool,
              input: toolCall.input,
              result: resultText,
            });
          }
        } catch (error: any) {
          toolResults.push({
            tool: toolCall.tool,
            input: toolCall.input,
            error: error.message || "Failed to execute tool",
          });
        }
      }

      // Format response (only show errors, not raw results)
      let responseText = "";
      for (const result of toolResults) {
        if (result.error) {
          responseText += `**${result.tool}** failed: ${result.error}\n\n`;
        }
      }

      // Add assistant message with tool results
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: responseText.trim() || "Tool executed successfully.",
        timestamp: new Date(),
        toolCalls: toolResults,
      };
      addMessage("assistant", assistantMsg.content, toolResults);

      // Update thread title if it's the first user message
      if (currentThreadId && messages.length === 0) {
        const title = userMessage.substring(0, 50);
        updateThreadTitle(currentThreadId, title);
      }
    } catch (error: any) {
      addMessage(
        "assistant",
        `Error: ${error.message || "Failed to process request"}`
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const addMessage = (
    role: "user" | "assistant" | "system",
    content: string,
    toolCalls?: Array<{
      tool: string;
      input: Record<string, any>;
      result?: any;
      error?: string;
    }>
  ) => {
    const message: Message = {
      id: Date.now().toString(),
      role,
      content,
      timestamp: new Date(),
      toolCalls,
    };

    setMessages((prev) => [...prev, message]);

    // Update current thread
    if (currentThreadId) {
      const updated = threads.map((t) =>
        t.id === currentThreadId
          ? {
              ...t,
              messages: [...t.messages, message],
              updatedAt: new Date(),
            }
          : t
      );
      saveThreads(updated);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const message = input.trim();
    setInput("");

    // Create thread if none exists
    if (!currentThreadId) {
      const thread = createNewThread();
      setCurrentThreadId(thread.id);
    }

    processMessage(message);
  };

  const loadThread = (threadId: string) => {
    const thread = threads.find((t) => t.id === threadId);
    if (thread) {
      setCurrentThreadId(threadId);
      setMessages(thread.messages);
      updateThreadTitle(threadId, thread.title);
    }
  };

  const startNewThread = () => {
    setCurrentThreadId(null);
    setMessages([]);
  };

  const handleCreateAgent = async () => {
    if (!newAgentName.trim() || !selectedAgent || !envId) {
      return;
    }

    setShowCreateAgentDialog(false);
    const agentName = newAgentName.trim();
    setNewAgentName("");

    // Create a new thread if needed
    if (!currentThreadId) {
      const thread = createNewThread();
      setCurrentThreadId(thread.id);
    }

    // Send the create agent message
    const message = `Create agent named ${agentName}`;
    setInput(message);
    setTimeout(() => {
      processMessage(message);
    }, 100);
  };

  const toggleMessageExpansion = (messageId: string) => {
    setExpandedMessages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  const copyToClipboard = async (text: string, messageId: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedText(messageId);
      setTimeout(() => setCopiedText(null), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const formatJSON = (text: string): any => {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  };

  // Slash command definitions
  const slashCommands = [
    {
      command: "/list agents",
      description: "List all agents",
      tool: "agentxsuite_list_agents",
      input: { enabled_only: true },
    },
    {
      command: "/list tools",
      description: "List all tools",
      tool: "agentxsuite_list_tools",
      input: { enabled_only: true },
    },
    {
      command: "/list connections",
      description: "List all connections",
      tool: "agentxsuite_list_connections",
      input: {},
    },
    {
      command: "/list runs",
      description: "List recent runs",
      tool: "agentxsuite_list_runs",
      input: { limit: 10 },
    },
    {
      command: "/create agent",
      description: "Create a new agent (requires name)",
      tool: "agentxsuite_create_agent",
      input: null, // Will prompt for name
    },
  ];

  const getCommandSuggestions = (query: string) => {
    if (!query.startsWith("/")) return [];
    const searchTerm = query.toLowerCase().substring(1);
    return slashCommands.filter((cmd) =>
      cmd.command.toLowerCase().includes(searchTerm) ||
      cmd.description.toLowerCase().includes(searchTerm)
    );
  };

  const parseSlashCommand = (message: string): { tool: string; input: Record<string, any> } | null => {
    if (!message.trim().startsWith("/")) return null;

    const parts = message.trim().split(/\s+/);
    const command = parts[0].toLowerCase();

    // Find matching command
    const cmd = slashCommands.find((c) => c.command.toLowerCase() === command);
    if (!cmd) return null;

    // Handle create agent command (needs name parameter)
    if (cmd.tool === "agentxsuite_create_agent") {
      const name = parts.slice(1).join(" ").trim();
      if (!name) {
        // Open dialog if no name provided
        setShowCreateAgentDialog(true);
        return null;
      }
      return {
        tool: cmd.tool,
        input: {
          name,
          mode: "runner",
          enabled: true,
        },
      };
    }

    // For other commands, use default input
    return {
      tool: cmd.tool,
      input: cmd.input || {},
    };
  };

  const renderToolResult = (result: any, toolName: string) => {
    const isExpanded = expandedMessages.has(`tool-${toolName}`);
    const isJSONExpanded = expandedMessages.has(`json-${toolName}`);
    const jsonData = typeof result === "string" ? formatJSON(result) : result;
    const isJSON = jsonData !== null;
    const resultString = typeof result === "string" ? result : JSON.stringify(result, null, 2);
    
    // Check if it's a list of items (agents, tools, connections, runs)
    const isList = isJSON && Array.isArray(jsonData.agents || jsonData.tools || jsonData.connections || jsonData.runs);
    const listKey = isList ? Object.keys(jsonData).find(k => Array.isArray(jsonData[k])) : null;
    const items = isList && listKey ? jsonData[listKey] : null;

    // Extract tool name from full identifier (e.g., "agentxsuite_create_agent-0" -> "agentxsuite_create_agent")
    const displayName = toolName.split("-")[0];

    return (
      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-purple-400" />
            <span className="text-xs font-semibold text-purple-400">{displayName}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => copyToClipboard(resultString, `tool-${toolName}`)}
              className="p-1 hover:bg-slate-700 rounded transition-colors"
              title="Copy to clipboard"
            >
              <Copy className={`w-3 h-3 ${copiedText === `tool-${toolName}` ? "text-green-400" : "text-slate-400"}`} />
            </button>
            {isJSON && (
              <button
                onClick={() => toggleMessageExpansion(`tool-${toolName}`)}
                className="p-1 hover:bg-slate-700 rounded transition-colors"
                title={isExpanded ? "Collapse" : "Expand"}
              >
                {isExpanded ? (
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                ) : (
                  <ChevronRight className="w-3 h-3 text-slate-400" />
                )}
              </button>
            )}
          </div>
        </div>

        {isList && items && items.length > 0 ? (
          <>
            <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden">
              <div className="p-3 bg-slate-800/50 border-b border-slate-700">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-300">
                    {items.length} {listKey?.replace(/s$/, "") || "item"}{items.length !== 1 ? "s" : ""}
                  </span>
                  {items.length > 5 && !isExpanded && (
                    <button
                      onClick={() => toggleMessageExpansion(`tool-${toolName}`)}
                      className="text-xs text-purple-400 hover:text-purple-300"
                    >
                      Show all
                    </button>
                  )}
                </div>
              </div>
              <div className="divide-y divide-slate-700">
                {(isExpanded ? items : items.slice(0, 5)).map((item: any, idx: number) => (
                  <div key={idx} className="p-3 hover:bg-slate-800/30 transition-colors">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                      {Object.entries(item).map(([key, value]: [string, any]) => (
                        <div key={key} className="flex gap-2">
                          <span className="text-slate-500 font-medium min-w-[80px] capitalize">{key.replace(/_/g, " ")}:</span>
                          <span className="text-slate-300 break-words">
                            {typeof value === "boolean" ? (
                              <span className={`px-1.5 py-0.5 rounded text-xs ${value ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                                {value ? "Yes" : "No"}
                              </span>
                            ) : key === "id" ? (
                              <span className="font-mono text-purple-300 text-xs">{String(value)}</span>
                            ) : (
                              String(value || "-")
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {items.length > 5 && !isExpanded && (
                <div className="p-2 text-center border-t border-slate-700">
                  <button
                    onClick={() => toggleMessageExpansion(`tool-${toolName}`)}
                    className="text-xs text-purple-400 hover:text-purple-300"
                  >
                    Show {items.length - 5} more...
                  </button>
                </div>
              )}
            </div>
            {/* Show JSON when expanded */}
            {isJSONExpanded && (
              <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden mt-2">
                <div className="p-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-300">Full JSON Result</span>
                  <button
                    onClick={() => copyToClipboard(JSON.stringify(jsonData, null, 2), `json-${toolName}`)}
                    className="p-1 hover:bg-slate-700 rounded transition-colors"
                    title="Copy JSON"
                  >
                    <Copy className={`w-3 h-3 ${copiedText === `json-${toolName}` ? "text-green-400" : "text-slate-400"}`} />
                  </button>
                </div>
                <pre className="p-4 text-xs overflow-x-auto max-h-96 overflow-y-auto">
                  <code className="text-slate-300">{JSON.stringify(jsonData, null, 2)}</code>
                </pre>
                <div className="p-2 border-t border-slate-700 bg-slate-800/50">
                  <button
                    onClick={() => toggleMessageExpansion(`json-${toolName}`)}
                    className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 w-full justify-center"
                  >
                    <ChevronDown className="w-3 h-3" />
                    Hide JSON
                  </button>
                </div>
              </div>
            )}
          </>
        ) : isJSON && jsonData.agent ? (
          // Single agent object (e.g., from create_agent)
          <>
            <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden">
              <div className="p-3 bg-slate-800/50 border-b border-slate-700">
                <span className="text-xs font-medium text-slate-300">Agent Created</span>
              </div>
              <div className="p-4">
                <div className="space-y-2">
                  {Object.entries(jsonData.agent || jsonData).map(([key, value]: [string, any]) => (
                    <div key={key} className="flex gap-3 items-start">
                      <span className="text-xs text-slate-500 font-medium min-w-[100px] capitalize">
                        {key.replace(/_/g, " ")}:
                      </span>
                      <span className="text-sm text-slate-300 break-words flex-1">
                        {typeof value === "boolean" ? (
                          <span className={`px-2 py-1 rounded text-xs ${value ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                            {value ? "Enabled" : "Disabled"}
                          </span>
                        ) : key === "id" || key === "agent_id" ? (
                          <span className="font-mono text-purple-300 text-xs bg-purple-500/10 px-2 py-1 rounded">
                            {String(value)}
                          </span>
                        ) : (
                          <span className="font-medium">{String(value || "-")}</span>
                        )}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            {/* Show JSON when expanded */}
            {isJSONExpanded && (
              <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden mt-2">
                <div className="p-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-300">Full JSON Result</span>
                  <button
                    onClick={() => copyToClipboard(JSON.stringify(jsonData, null, 2), `json-${toolName}`)}
                    className="p-1 hover:bg-slate-700 rounded transition-colors"
                    title="Copy JSON"
                  >
                    <Copy className={`w-3 h-3 ${copiedText === `json-${toolName}` ? "text-green-400" : "text-slate-400"}`} />
                  </button>
                </div>
                <pre className="p-4 text-xs overflow-x-auto max-h-96 overflow-y-auto">
                  <code className="text-slate-300">{JSON.stringify(jsonData, null, 2)}</code>
                </pre>
                <div className="p-2 border-t border-slate-700 bg-slate-800/50">
                  <button
                    onClick={() => toggleMessageExpansion(`json-${toolName}`)}
                    className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 w-full justify-center"
                  >
                    <ChevronDown className="w-3 h-3" />
                    Hide JSON
                  </button>
                </div>
              </div>
            )}
          </>
        ) : isJSON ? (
          // JSON data - only show expanded view when expanded, otherwise show nothing (button will be shown separately)
          isJSONExpanded && (
            <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden mt-2">
              <div className="p-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                <span className="text-xs font-medium text-slate-300">Full JSON Result</span>
                <button
                  onClick={() => copyToClipboard(JSON.stringify(jsonData, null, 2), `json-${toolName}`)}
                  className="p-1 hover:bg-slate-700 rounded transition-colors"
                  title="Copy JSON"
                >
                  <Copy className={`w-3 h-3 ${copiedText === `json-${toolName}` ? "text-green-400" : "text-slate-400"}`} />
                </button>
              </div>
              <pre className="p-4 text-xs overflow-x-auto max-h-96 overflow-y-auto">
                <code className="text-slate-300">{JSON.stringify(jsonData, null, 2)}</code>
              </pre>
              <div className="p-2 border-t border-slate-700 bg-slate-800/50">
                <button
                  onClick={() => toggleMessageExpansion(`json-${toolName}`)}
                  className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 w-full justify-center"
                >
                  <ChevronDown className="w-3 h-3" />
                  Hide JSON
                </button>
              </div>
            </div>
          )
        ) : (
          // Non-JSON text result - only show expanded view when expanded, otherwise show nothing
          isJSONExpanded && (
            <div className="bg-slate-900/50 rounded-lg border border-slate-700 overflow-hidden mt-2">
              <div className="p-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                <span className="text-xs font-medium text-slate-300">Full Result</span>
                <button
                  onClick={() => copyToClipboard(result, `json-${toolName}`)}
                  className="p-1 hover:bg-slate-700 rounded transition-colors"
                  title="Copy result"
                >
                  <Copy className={`w-3 h-3 ${copiedText === `json-${toolName}` ? "text-green-400" : "text-slate-400"}`} />
                </button>
              </div>
              <pre className="p-4 text-xs overflow-x-auto whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
                <code className="text-slate-300">{result}</code>
              </pre>
              <div className="p-2 border-t border-slate-700 bg-slate-800/50">
                <button
                  onClick={() => toggleMessageExpansion(`json-${toolName}`)}
                  className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 w-full justify-center"
                >
                  <ChevronDown className="w-3 h-3" />
                  Hide full result
                </button>
              </div>
            </div>
          )
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950">
      {/* Header */}
      <div className="border-b border-slate-800 p-3 sm:p-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-2">
          <div className="flex items-center gap-2 sm:gap-4 w-full sm:w-auto">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="lg:hidden p-2 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800"
            >
              <Bot className="w-5 h-5" />
            </button>
            <h1 className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent">
              AxCore
            </h1>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 w-full sm:w-auto">
            {/* Organization Selector */}
            {organizations.length > 1 && (
              <select
                value={orgId || ""}
                onChange={(e) => {
                  setCurrentOrg(e.target.value);
                  setCurrentEnv(null); // Reset environment when org changes
                  setSelectedAgent(null); // Reset agent when org changes
                  setAgentToken(null);
                }}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {organizations.map((org: any) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            )}
            {/* Environment Selector */}
            {environments.length > 0 && (
              <select
                value={envId || ""}
                onChange={(e) => {
                  setCurrentEnv(e.target.value);
                  setSelectedAgent(null); // Reset agent when env changes
                  setAgentToken(null);
                }}
                className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-200 text-xs sm:text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              >
                {environments.map((env: any) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.type})
                  </option>
                ))}
              </select>
            )}
            {selectedAgent && (
              <div className="flex items-center gap-2 text-xs sm:text-sm text-slate-400">
                <Bot className="w-4 h-4 flex-shrink-0" />
                <span className="hidden sm:inline truncate max-w-[150px]">
                  {selectedAgent.name}
                </span>
                <span className="sm:hidden truncate max-w-[100px]">
                  {selectedAgent.name}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar with Recent Threads */}
        <div
          className={`${
            showSidebar ? "translate-x-0" : "-translate-x-full"
          } lg:translate-x-0 absolute lg:static inset-y-0 left-0 z-40 w-64 border-r border-slate-800 bg-slate-950 p-3 sm:p-4 overflow-y-auto transition-transform duration-300`}
        >
          <button
            onClick={startNewThread}
            className="w-full mb-4 px-3 sm:px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 text-purple-400 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">New Thread</span>
            <span className="sm:hidden">New</span>
          </button>

          <h2 className="text-sm font-semibold text-slate-300 mb-2">Recent threads</h2>
          <div className="space-y-2">
            {threads.slice(0, 10).map((thread) => (
              <div
                key={thread.id}
                className={`group relative w-full text-left p-3 rounded-lg transition-colors ${
                  currentThreadId === thread.id
                    ? "bg-slate-800 border border-purple-500/30"
                    : "hover:bg-slate-800/50"
                }`}
              >
                <button
                  onClick={() => loadThread(thread.id)}
                  className="w-full text-left"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Bot className="w-4 h-4 text-slate-400" />
                    <span className="text-sm font-medium text-slate-300 truncate flex-1">
                      {thread.title}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    {thread.messages.length} messages •{" "}
                    {formatTimeAgo(thread.updatedAt)}
                  </div>
                </button>
                <button
                  onClick={(e) => deleteThread(thread.id, e)}
                  className="absolute top-2 right-2 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-red-500/20 text-red-400 rounded transition-all"
                  title="Delete thread"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
            {threads.length === 0 && (
              <div className="text-sm text-slate-500 text-center py-4">
                No threads yet
              </div>
            )}
          </div>
        </div>

        {/* Overlay for mobile sidebar */}
        {showSidebar && (
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-30"
            onClick={() => setShowSidebar(false)}
          />
        )}

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 space-y-3 sm:space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center px-4">
                <Bot className="w-12 h-12 sm:w-16 sm:h-16 text-slate-600 mb-4" />
                <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-slate-300 mb-2">
                  Ask anything about your systems...
                </h2>
                <p className="text-sm sm:text-base text-slate-500 mb-4 sm:mb-6">
                  I can help you manage agents, tools, connections, and more.
                </p>
                <div className="w-full max-w-2xl">
                  <h3 className="text-sm font-semibold text-slate-400 mb-3 text-left">Quick Actions</h3>
                  {systemTools.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3">
                      {systemTools.map((tool: any) => {
                        // Map tool names to user-friendly labels and messages
                        const toolConfig: Record<string, { label: string; message: string; isSpecial?: boolean }> = {
                          "agentxsuite_list_agents": {
                            label: "List Agents",
                            message: "List agents",
                          },
                          "agentxsuite_get_agent": {
                            label: "Get Agent",
                            message: "Get agent details",
                          },
                          "agentxsuite_create_agent": {
                            label: "Create Agent",
                            message: "Create agent",
                            isSpecial: true,
                          },
                          "agentxsuite_list_connections": {
                            label: "List Connections",
                            message: "List connections",
                          },
                          "agentxsuite_list_tools": {
                            label: "List Tools",
                            message: "List tools",
                          },
                          "agentxsuite_list_runs": {
                            label: "List Runs",
                            message: "List runs",
                          },
                        };
                        
                        const config = toolConfig[tool.name] || {
                          label: tool.name.replace("agentxsuite_", "").replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase()),
                          message: tool.name.replace("agentxsuite_", "").replace(/_/g, " "),
                        };
                        
                        return (
                          <button
                            key={tool.name}
                            onClick={() => {
                              if (config.isSpecial && tool.name === "agentxsuite_create_agent") {
                                // Open create agent dialog
                                if (selectedAgent && envId) {
                                  setShowCreateAgentDialog(true);
                                } else {
                                  addMessage("system", "Please select an AxCore agent and environment first.");
                                }
                              } else {
                                const message = config.message;
                                setInput(message);
                                // Auto-submit if agent is selected
                                if (selectedAgent && envId) {
                                  setTimeout(() => {
                                    if (!currentThreadId) {
                                      const thread = createNewThread();
                                      setCurrentThreadId(thread.id);
                                    }
                                    processMessage(message);
                                  }, 100);
                                } else {
                                  // Focus input field
                                  inputRef.current?.focus();
                                }
                              }
                            }}
                            className={`p-3 text-left rounded-lg border transition-colors ${
                              config.isSpecial
                                ? "bg-gradient-to-r from-purple-500/20 to-pink-500/20 hover:from-purple-500/30 hover:to-pink-500/30 border-purple-500/30"
                                : "bg-slate-800 hover:bg-slate-700 border-slate-700"
                            }`}
                          >
                            <div className={`text-sm font-medium ${
                              config.isSpecial ? "text-purple-300" : "text-slate-300"
                            }`}>
                              {config.label}
                            </div>
                            {tool.description && (
                              <div className="text-xs text-slate-500 mt-1 line-clamp-2">
                                {tool.description}
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-sm text-slate-500 text-center py-4">
                      {selectedAgent && envId ? "Loading system tools..." : "Please select an AxCore agent and environment to see available tools."}
                    </div>
                  )}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-2 sm:gap-4 ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {message.role !== "user" && (
                  <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-3 h-3 sm:w-4 sm:h-4 text-purple-400" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] sm:max-w-[75%] md:max-w-2xl rounded-lg p-3 sm:p-4 ${
                    message.role === "user"
                      ? "bg-purple-500/20 text-purple-100"
                      : "bg-slate-800 text-slate-200"
                  }`}
                >
                  {message.role === "system" && (
                    <div className="flex items-center gap-2 mb-2 pb-2 border-b border-slate-700">
                      <Info className="w-4 h-4 text-blue-400" />
                      <span className="text-xs font-medium text-blue-400">System Message</span>
                    </div>
                  )}
                  
                  {message.content && (
                    <div className="whitespace-pre-wrap text-sm sm:text-base break-words mb-3">
                      {message.content.split("**").map((part, idx) => {
                        if (idx % 2 === 1) {
                          return <strong key={idx} className="text-purple-300">{part}</strong>;
                        }
                        return <span key={idx}>{part}</span>;
                      })}
                    </div>
                  )}

                  {message.toolCalls && message.toolCalls.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-700 space-y-3">
                      <div className="flex items-center gap-2 mb-3">
                        <Zap className="w-4 h-4 text-purple-400" />
                        <span className="text-xs font-semibold text-slate-400">
                          Tool Executions ({message.toolCalls.length})
                        </span>
                      </div>
                      {message.toolCalls.map((tc, idx) => (
                        <div
                          key={idx}
                          className="bg-slate-900/70 rounded-lg border border-slate-700 p-3 space-y-2"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2 flex-1 min-w-0">
                              {tc.error ? (
                                <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                              ) : (
                                <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
                              )}
                              <div className="min-w-0 flex-1">
                                <div className="font-mono text-xs text-purple-400 break-all">
                                  {tc.tool}
                                </div>
                                {tc.input && Object.keys(tc.input).length > 0 && (
                                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                                    {Object.entries(tc.input).map(([key, value]: [string, any]) => (
                                      <span
                                        key={key}
                                        className="px-2 py-0.5 bg-slate-800/50 rounded text-xs text-slate-400 border border-slate-700"
                                      >
                                        <span className="text-slate-500">{key}:</span>{" "}
                                        <span className="text-slate-300">
                                          {typeof value === "boolean" ? (
                                            value ? "✓" : "✗"
                                          ) : typeof value === "object" ? (
                                            JSON.stringify(value)
                                          ) : (
                                            String(value)
                                          )}
                                        </span>
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                            {tc.error ? (
                              <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded text-xs font-medium flex-shrink-0">
                                Failed
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs font-medium flex-shrink-0">
                                Success
                              </span>
                            )}
                          </div>
                          
                          {tc.error ? (
                            <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded text-xs text-red-400 break-words">
                              <div className="font-semibold mb-1">Error:</div>
                              <div>{tc.error}</div>
                            </div>
                          ) : tc.result ? (
                            <>
                              {renderToolResult(tc.result, `${tc.tool}-${idx}`)}
                              {/* JSON Expand Button at the end - always show if not expanded and result exists */}
                              {tc.result && !expandedMessages.has(`json-${tc.tool}-${idx}`) && (
                                <div className="mt-3 pt-3 border-t border-slate-700">
                                  <button
                                    onClick={() => toggleMessageExpansion(`json-${tc.tool}-${idx}`)}
                                    className="w-full text-xs text-purple-400 hover:text-purple-300 flex items-center justify-center gap-2 py-2.5 hover:bg-purple-500/10 rounded-lg border border-purple-500/20 transition-all group"
                                  >
                                    <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                                    <span className="font-medium">Show full JSON result</span>
                                    <Copy className="w-3 h-3 opacity-50" />
                                  </button>
                                </div>
                              )}
                            </>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-700">
                    <div className="text-xs text-slate-500">
                      {formatTime(message.timestamp)}
                    </div>
                    {message.content && (
                      <button
                        onClick={() => copyToClipboard(message.content, message.id)}
                        className="p-1 hover:bg-slate-700 rounded transition-colors"
                        title="Copy message"
                      >
                        <Copy className={`w-3 h-3 ${copiedText === message.id ? "text-green-400" : "text-slate-500"}`} />
                      </button>
                    )}
                  </div>
                </div>
                {message.role === "user" && (
                  <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-slate-700 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs text-slate-300">U</span>
                  </div>
                )}
              </div>
            ))}

            {isProcessing && (
              <div className="flex gap-2 sm:gap-4 justify-start">
                <div className="w-6 h-6 sm:w-8 sm:h-8 rounded-full bg-purple-500/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-3 h-3 sm:w-4 sm:h-4 text-purple-400" />
                </div>
                <div className="bg-slate-800 rounded-lg p-3 sm:p-4">
                  <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Create Agent Dialog */}
          {showCreateAgentDialog && (
            <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
              <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 max-w-md w-full">
                <h2 className="text-xl font-bold text-white mb-4">Create New Agent</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Agent Name
                    </label>
                    <input
                      type="text"
                      value={newAgentName}
                      onChange={(e) => setNewAgentName(e.target.value)}
                      placeholder="Enter agent name..."
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && newAgentName.trim()) {
                          handleCreateAgent();
                        } else if (e.key === "Escape") {
                          setShowCreateAgentDialog(false);
                          setNewAgentName("");
                        }
                      }}
                      autoFocus
                    />
                  </div>
                  <div className="flex gap-3 justify-end">
                    <button
                      onClick={() => {
                        setShowCreateAgentDialog(false);
                        setNewAgentName("");
                      }}
                      className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleCreateAgent}
                      disabled={!newAgentName.trim()}
                      className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Create
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Input Area */}
          <div className="border-t border-slate-800 p-3 sm:p-4 relative">
            {toolsError && (
              <div className="mb-3 sm:mb-4 p-2 sm:p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-2 text-red-400 text-xs sm:text-sm">
                <AlertCircle className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-semibold mb-1">Connection Error</div>
                  <div className="break-words">
                    {toolsError instanceof Error
                      ? toolsError.message
                      : "Failed to connect to MCP Fabric server. Please ensure the server is running on port 8090."}
                  </div>
                </div>
              </div>
            )}
            {(!selectedAgent || !envId) && (
              <div className="mb-3 sm:mb-4 p-2 sm:p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-2 text-yellow-400 text-xs sm:text-sm">
                <AlertCircle className="w-3 h-3 sm:w-4 sm:h-4 flex-shrink-0" />
                <span className="break-words">
                  {!envId
                    ? "Please select an environment first."
                    : "Please select an AxCore agent to start chatting."}
                </span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-2 sm:space-y-3">
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <div className="relative flex-1 min-w-0">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      // Show command suggestions when typing "/"
                      if (e.target.value.startsWith("/")) {
                        setCommandQuery(e.target.value);
                        setShowCommandSuggestions(true);
                      } else {
                        setShowCommandSuggestions(false);
                        setCommandQuery("");
                      }
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        setShowCommandSuggestions(false);
                        handleSubmit(e);
                      } else if (e.key === "Escape") {
                        setShowCommandSuggestions(false);
                      } else if (e.key === "ArrowDown" && showCommandSuggestions) {
                        e.preventDefault();
                        // Could implement keyboard navigation here
                      }
                    }}
                    onFocus={() => {
                      if (input.startsWith("/")) {
                        setShowCommandSuggestions(true);
                      }
                    }}
                    onBlur={() => {
                      // Delay to allow clicking on suggestions
                      setTimeout(() => setShowCommandSuggestions(false), 200);
                    }}
                    placeholder="Ask anything about your systems... (try /list agents)"
                    className="w-full px-3 sm:px-4 py-2 sm:py-3 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none text-sm sm:text-base"
                    rows={1}
                    disabled={!selectedAgent || isProcessing}
                  />
                  {/* Command Suggestions */}
                  {showCommandSuggestions && getCommandSuggestions(commandQuery).length > 0 && (
                    <div className="absolute bottom-full left-0 right-0 mb-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl max-h-64 overflow-y-auto z-50">
                      {getCommandSuggestions(commandQuery).map((cmd, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            if (cmd.tool === "agentxsuite_create_agent") {
                              setShowCreateAgentDialog(true);
                              setInput("");
                            } else {
                              setInput(cmd.command);
                              setShowCommandSuggestions(false);
                              // Auto-submit if agent is selected
                              if (selectedAgent && envId) {
                                setTimeout(() => {
                                  if (!currentThreadId) {
                                    const thread = createNewThread();
                                    setCurrentThreadId(thread.id);
                                  }
                                  processMessage(cmd.command);
                                }, 100);
                              }
                            }
                          }}
                          className="w-full text-left px-4 py-2 hover:bg-slate-800 transition-colors border-b border-slate-700 last:border-b-0"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <div className="text-sm font-medium text-purple-400">{cmd.command}</div>
                              <div className="text-xs text-slate-400 mt-0.5">{cmd.description}</div>
                            </div>
                            <Zap className="w-4 h-4 text-purple-500/50" />
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="px-2 sm:px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg transition-colors flex items-center gap-1 sm:gap-2 text-xs sm:text-sm whitespace-nowrap"
                    onClick={() => setShowAgentSelect(!showAgentSelect)}
                  >
                    <span className="hidden sm:inline">
                      {selectedAgent ? selectedAgent.name : "Select agent"}
                    </span>
                    <span className="sm:hidden">
                      {selectedAgent ? "Agent" : "Select"}
                    </span>
                    <ChevronDown className="w-3 h-3 sm:w-4 sm:h-4" />
                  </button>
                  <button
                    type="submit"
                    disabled={!input.trim() || !selectedAgent || isProcessing}
                    className="p-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </form>

            {/* Agent Select Dropdown */}
            {showAgentSelect && (
              <div className="absolute bottom-full left-3 sm:left-4 right-3 sm:right-4 sm:left-auto sm:right-auto sm:w-64 mb-2 bg-slate-900 border border-slate-700 rounded-lg shadow-xl z-50 max-h-60 overflow-y-auto">
                {agents.map((agent: any) => (
                  <button
                    key={agent.id}
                    onClick={() => {
                      setSelectedAgent(agent);
                      setShowAgentSelect(false);
                      loadAgentToken(agent.id);
                    }}
                    className="w-full text-left px-4 py-2 hover:bg-slate-800 transition-colors flex items-center gap-2"
                  >
                    <Bot className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-slate-300">{agent.name}</span>
                    {selectedAgent?.id === agent.id && (
                      <span className="ml-auto text-xs text-purple-400">
                        ✓
                      </span>
                    )}
                  </button>
                ))}
                {agents.length === 0 && (
                  <div className="px-4 py-2 text-sm text-slate-500">
                    No AxCore agents found
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(date: Date): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
  return `${days} day${days > 1 ? "s" : ""} ago`;
}

