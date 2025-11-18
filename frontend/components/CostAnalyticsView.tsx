"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api, costsApi } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Bot,
  Settings,
  Brain,
  Wrench,
  Calendar,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
} from "lucide-react";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";

const COLORS = [
  "#10b981", // emerald-500
  "#3b82f6", // blue-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
];

type TimeRange = 7 | 30 | 90;

export function CostAnalyticsView() {
  const t = useTranslations();
  const { currentOrgId: orgId, setCurrentOrg } = useAppStore();
  const [timeRange, setTimeRange] = useState<TimeRange>(30);
  const [selectedView, setSelectedView] = useState<
    "agents" | "environments" | "models" | "tools"
  >("agents");

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

  // Fetch cost summary
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["costs-summary", orgId, timeRange],
    queryFn: async () => {
      if (!orgId) return null;
      const response = await costsApi.summary(orgId, { days: timeRange });
      return response.data;
    },
    enabled: !!orgId,
  });

  // Fetch cost breakdown by agent
  const { data: agentCosts, isLoading: agentsLoading } = useQuery({
    queryKey: ["costs-by-agent", orgId, timeRange],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await costsApi.byAgent(orgId, { days: timeRange });
      return response.data;
    },
    enabled: !!orgId,
  });

  // Fetch cost breakdown by environment
  const { data: envCosts, isLoading: envsLoading } = useQuery({
    queryKey: ["costs-by-environment", orgId, timeRange],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await costsApi.byEnvironment(orgId, { days: timeRange });
      return response.data;
    },
    enabled: !!orgId,
  });

  // Fetch cost breakdown by model
  const { data: modelCosts, isLoading: modelsLoading } = useQuery({
    queryKey: ["costs-by-model", orgId, timeRange],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await costsApi.byModel(orgId, { days: timeRange });
      return response.data;
    },
    enabled: !!orgId,
  });

  // Fetch cost breakdown by tool
  const { data: toolCosts, isLoading: toolsLoading } = useQuery({
    queryKey: ["costs-by-tool", orgId, timeRange],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await costsApi.byTool(orgId, { days: timeRange });
      return response.data;
    },
    enabled: !!orgId,
  });

  if (!orgId) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-slate-400">Please select an organization</p>
      </div>
    );
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 6,
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("en-US").format(value);
  };

  const successRate = summary
    ? (summary.successful_runs / summary.total_runs) * 100
    : 0;

  const avgCostPerRun =
    summary && summary.total_runs > 0
      ? summary.total_cost / summary.total_runs
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-emerald-500 to-teal-500 rounded-lg">
              <DollarSign className="h-7 w-7 text-white" />
            </div>
            Cost Analytics
          </h1>
          <p className="text-slate-400">
            Track and analyze your AI agent costs and token usage
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex gap-2 bg-slate-800/50 border border-slate-700 rounded-lg p-1">
          {[7, 30, 90].map((days) => (
            <button
              key={days}
              onClick={() => setTimeRange(days as TimeRange)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                timeRange === days
                  ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              {days} Days
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      {summaryLoading ? (
        <div className="text-center py-12">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-500 border-r-transparent"></div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Total Cost Card */}
            <div className="bg-gradient-to-br from-slate-800/90 to-slate-800/50 border border-slate-700/50 rounded-xl p-6 shadow-xl backdrop-blur-sm hover:border-emerald-500/30 transition-all duration-300 hover:shadow-emerald-500/10 hover:shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="p-3 bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/20 rounded-lg">
                  <DollarSign className="h-6 w-6 text-emerald-400" />
                </div>
                <div className="flex items-center gap-1 text-emerald-400 text-sm font-medium">
                  <TrendingUp className="h-4 w-4" />
                  <span>Total</span>
                </div>
              </div>
              <h3 className="text-slate-400 text-sm font-medium mb-1">
                Total Cost
              </h3>
              <p className="text-3xl font-bold text-white mb-2">
                {formatCurrency(summary?.total_cost || 0)}
              </p>
              <div className="flex gap-2 text-xs text-slate-500">
                <span>Input: {formatCurrency(summary?.total_cost_input || 0)}</span>
                <span>•</span>
                <span>Output: {formatCurrency(summary?.total_cost_output || 0)}</span>
              </div>
            </div>

            {/* Total Runs Card */}
            <div className="bg-gradient-to-br from-slate-800/90 to-slate-800/50 border border-slate-700/50 rounded-xl p-6 shadow-xl backdrop-blur-sm hover:border-blue-500/30 transition-all duration-300 hover:shadow-blue-500/10 hover:shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="p-3 bg-gradient-to-br from-blue-500/20 to-indigo-500/20 border border-blue-500/20 rounded-lg">
                  <Activity className="h-6 w-6 text-blue-400" />
                </div>
                <div className="text-blue-400 text-sm font-medium">
                  {successRate.toFixed(1)}% success
                </div>
              </div>
              <h3 className="text-slate-400 text-sm font-medium mb-1">
                Total Runs
              </h3>
              <p className="text-3xl font-bold text-white mb-2">
                {formatNumber(summary?.total_runs || 0)}
              </p>
              <div className="flex gap-2 text-xs text-slate-500">
                <span className="text-emerald-400">
                  {formatNumber(summary?.successful_runs || 0)} success
                </span>
                <span>•</span>
                <span className="text-red-400">
                  {formatNumber(summary?.failed_runs || 0)} failed
                </span>
              </div>
            </div>

            {/* Total Tokens Card */}
            <div className="bg-gradient-to-br from-slate-800/90 to-slate-800/50 border border-slate-700/50 rounded-xl p-6 shadow-xl backdrop-blur-sm hover:border-violet-500/30 transition-all duration-300 hover:shadow-violet-500/10 hover:shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="p-3 bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/20 rounded-lg">
                  <Zap className="h-6 w-6 text-violet-400" />
                </div>
                <div className="text-violet-400 text-sm font-medium">
                  Tokens
                </div>
              </div>
              <h3 className="text-slate-400 text-sm font-medium mb-1">
                Total Tokens
              </h3>
              <p className="text-3xl font-bold text-white mb-2">
                {formatNumber(summary?.total_tokens || 0)}
              </p>
              <div className="flex gap-2 text-xs text-slate-500">
                <span>
                  In: {formatNumber(summary?.total_input_tokens || 0)}
                </span>
                <span>•</span>
                <span>
                  Out: {formatNumber(summary?.total_output_tokens || 0)}
                </span>
              </div>
            </div>

            {/* Avg Cost per Run Card */}
            <div className="bg-gradient-to-br from-slate-800/90 to-slate-800/50 border border-slate-700/50 rounded-xl p-6 shadow-xl backdrop-blur-sm hover:border-amber-500/30 transition-all duration-300 hover:shadow-amber-500/10 hover:shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="p-3 bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/20 rounded-lg">
                  <Sparkles className="h-6 w-6 text-amber-400" />
                </div>
                <div className="text-amber-400 text-sm font-medium">
                  Average
                </div>
              </div>
              <h3 className="text-slate-400 text-sm font-medium mb-1">
                Avg Cost / Run
              </h3>
              <p className="text-3xl font-bold text-white mb-2">
                {formatCurrency(avgCostPerRun)}
              </p>
              <div className="text-xs text-slate-500">
                Per execution
              </div>
            </div>
          </div>

          {/* View Selector */}
          <div className="flex gap-3 bg-slate-800/50 border border-slate-700 rounded-lg p-1.5">
            <button
              onClick={() => setSelectedView("agents")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                selectedView === "agents"
                  ? "bg-gradient-to-r from-emerald-500 to-teal-500 text-white shadow-lg shadow-emerald-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              <Bot className="h-4 w-4" />
              By Agent
            </button>
            <button
              onClick={() => setSelectedView("environments")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                selectedView === "environments"
                  ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              <Settings className="h-4 w-4" />
              By Environment
            </button>
            <button
              onClick={() => setSelectedView("models")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                selectedView === "models"
                  ? "bg-gradient-to-r from-violet-500 to-purple-500 text-white shadow-lg shadow-violet-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              <Brain className="h-4 w-4" />
              By Model
            </button>
            <button
              onClick={() => setSelectedView("tools")}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all ${
                selectedView === "tools"
                  ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-lg shadow-amber-500/20"
                  : "text-slate-400 hover:text-white hover:bg-slate-700/50"
              }`}
            >
              <Wrench className="h-4 w-4" />
              By Tool
            </button>
          </div>

          {/* Agent Cards - Fancy Layout */}
          {selectedView === "agents" && (
            <div>
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Bot className="h-5 w-5 text-emerald-400" />
                Cost by Agent
              </h2>
              {agentsLoading ? (
                <div className="text-center py-12">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-500 border-r-transparent"></div>
                </div>
              ) : agentCosts && agentCosts.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {agentCosts.map((agent, index) => {
                    const tokenEfficiency =
                      agent.total_tokens > 0
                        ? (agent.total_cost / agent.total_tokens) * 1000
                        : 0;
                    const avgCost =
                      agent.total_runs > 0
                        ? agent.total_cost / agent.total_runs
                        : 0;

                    return (
                      <div
                        key={agent.agent_id}
                        className="group bg-gradient-to-br from-slate-800/90 to-slate-800/50 border border-slate-700/50 rounded-xl p-6 shadow-xl backdrop-blur-sm hover:border-emerald-500/50 transition-all duration-300 hover:shadow-emerald-500/20 hover:shadow-2xl hover:-translate-y-1 hover:scale-[1.02]"
                      >
                        <div className="flex items-start justify-between mb-4">
                          <div className="flex items-center gap-3">
                            <div
                              className={`p-3 rounded-lg bg-gradient-to-br ${
                                index % 3 === 0
                                  ? "from-emerald-500/20 to-teal-500/20 border border-emerald-500/20"
                                  : index % 3 === 1
                                  ? "from-blue-500/20 to-indigo-500/20 border border-blue-500/20"
                                  : "from-violet-500/20 to-purple-500/20 border border-violet-500/20"
                              }`}
                            >
                              <Bot
                                className={`h-6 w-6 ${
                                  index % 3 === 0
                                    ? "text-emerald-400"
                                    : index % 3 === 1
                                    ? "text-blue-400"
                                    : "text-violet-400"
                                }`}
                              />
                            </div>
                            <div>
                              <h3 className="text-white font-semibold text-lg group-hover:text-emerald-400 transition-colors">
                                {agent.agent_name}
                              </h3>
                              <p className="text-slate-500 text-xs">
                                {formatNumber(agent.total_runs)} runs
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-2xl font-bold text-white mb-1">
                              {formatCurrency(agent.total_cost)}
                            </div>
                          </div>
                        </div>

                        <div className="space-y-3 pt-4 border-t border-slate-700/50">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">
                              Tokens Used
                            </span>
                            <span className="text-white font-medium">
                              {formatNumber(agent.total_tokens)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">
                              Avg / Run
                            </span>
                            <span className="text-emerald-400 font-medium">
                              {formatCurrency(avgCost)}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">
                              Cost / 1K Tokens
                            </span>
                            <span className="text-violet-400 font-medium">
                              {formatCurrency(tokenEfficiency)}
                            </span>
                          </div>
                        </div>

                        {/* Progress bar for relative cost */}
                        <div className="mt-4 pt-4 border-t border-slate-700/50">
                          <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                            <span>Share of total costs</span>
                            <span>
                              {(
                                (agent.total_cost / (summary?.total_cost || 1)) *
                                100
                              ).toFixed(1)}
                              %
                            </span>
                          </div>
                          <div className="w-full bg-slate-700/30 rounded-full h-2 overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-500"
                              style={{
                                width: `${
                                  (agent.total_cost / (summary?.total_cost || 1)) *
                                  100
                                }%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-12 bg-slate-800/50 border border-slate-700 rounded-xl">
                  <Bot className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400">No agent cost data available</p>
                </div>
              )}
            </div>
          )}

          {/* Environment View */}
          {selectedView === "environments" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Settings className="h-5 w-5 text-blue-400" />
                  Cost by Environment
                </h3>
                {envsLoading ? (
                  <div className="text-center py-12">
                    <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-500 border-r-transparent"></div>
                  </div>
                ) : envCosts && envCosts.length > 0 ? (
                  <div className="space-y-4">
                    {envCosts.map((env, index) => (
                      <div
                        key={env.environment_id}
                        className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4 hover:border-blue-500/50 transition-all"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-white font-medium">
                            {env.environment_name}
                          </span>
                          <span className="text-xl font-bold text-blue-400">
                            {formatCurrency(env.total_cost)}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-400">
                          <span>{formatNumber(env.total_runs)} runs</span>
                          <span>•</span>
                          <span>{formatNumber(env.total_tokens)} tokens</span>
                        </div>
                        <div className="mt-3">
                          <div className="w-full bg-slate-700/30 rounded-full h-2">
                            <div
                              className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"
                              style={{
                                width: `${
                                  (env.total_cost / (summary?.total_cost || 1)) *
                                  100
                                }%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-400 text-center py-8">
                    No environment data available
                  </p>
                )}
              </div>

              {/* Pie Chart */}
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Distribution
                </h3>
                {envCosts && envCosts.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={envCosts.map((env) => ({
                          name: env.environment_name,
                          value: env.total_cost,
                        }))}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry: any) =>
                          `${entry.name} ${(entry.percent * 100).toFixed(0)}%`
                        }
                        outerRadius={100}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {envCosts.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value: number) => formatCurrency(value)}
                        contentStyle={{
                          backgroundColor: "#1e293b",
                          border: "1px solid #334155",
                          borderRadius: "8px",
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-[300px]">
                    <p className="text-slate-400">No data to display</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Model View */}
          {selectedView === "models" && (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <Brain className="h-5 w-5 text-violet-400" />
                Cost by Model
              </h3>
              {modelsLoading ? (
                <div className="text-center py-12">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-violet-500 border-r-transparent"></div>
                </div>
              ) : modelCosts && modelCosts.length > 0 ? (
                <div className="space-y-4">
                  {modelCosts.map((model, index) => (
                    <div
                      key={model.model_name}
                      className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-5 hover:border-violet-500/50 transition-all"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-violet-500/20 border border-violet-500/20 rounded-lg">
                            <Brain className="h-5 w-5 text-violet-400" />
                          </div>
                          <div>
                            <span className="text-white font-semibold text-lg">
                              {model.model_name}
                            </span>
                            <p className="text-slate-500 text-sm">
                              {formatNumber(model.total_runs)} runs •{" "}
                              {formatNumber(model.total_tokens)} tokens
                            </p>
                          </div>
                        </div>
                        <span className="text-2xl font-bold text-violet-400">
                          {formatCurrency(model.total_cost)}
                        </span>
                      </div>
                      <div className="w-full bg-slate-700/30 rounded-full h-2.5">
                        <div
                          className="h-full bg-gradient-to-r from-violet-500 to-purple-500 rounded-full"
                          style={{
                            width: `${
                              (model.total_cost / (summary?.total_cost || 1)) * 100
                            }%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Brain className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400">No model cost data available</p>
                </div>
              )}
            </div>
          )}

          {/* Tool View */}
          {selectedView === "tools" && (
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <Wrench className="h-5 w-5 text-amber-400" />
                Cost by Tool
              </h3>
              {toolsLoading ? (
                <div className="text-center py-12">
                  <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-amber-500 border-r-transparent"></div>
                </div>
              ) : toolCosts && toolCosts.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {toolCosts.map((tool, index) => (
                    <div
                      key={tool.tool_id}
                      className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4 hover:border-amber-500/50 transition-all"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Wrench className="h-4 w-4 text-amber-400" />
                          <span className="text-white font-medium">
                            {tool.tool_name}
                          </span>
                        </div>
                        <span className="text-lg font-bold text-amber-400">
                          {formatCurrency(tool.total_cost)}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>{formatNumber(tool.total_runs)} runs</span>
                        <span>•</span>
                        <span>{formatNumber(tool.total_tokens)} tokens</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <Wrench className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400">No tool cost data available</p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

