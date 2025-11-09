"use client";

import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  Bot,
  Plug,
  Wrench,
  Play,
  TrendingUp,
  Activity,
} from "lucide-react";
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const COLORS = ["#10b981", "#f59e0b", "#ef4444"];

export function Dashboard() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);

  // Mock data for now - replace with actual API calls
  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats", orgId],
    queryFn: async () => {
      // TODO: Replace with actual API calls
      return {
        activeAgents: 12,
        activeConnections: 5,
        toolsSynced: 48,
        runsLast24h: 234,
      };
    },
  });

  const runsData = [
    { name: "00:00", runs: 4 },
    { name: "04:00", runs: 3 },
    { name: "08:00", runs: 7 },
    { name: "12:00", runs: 12 },
    { name: "16:00", runs: 8 },
    { name: "20:00", runs: 6 },
  ];

  const healthData = [
    { name: "Healthy", value: 8 },
    { name: "Degraded", value: 3 },
    { name: "Offline", value: 1 },
  ];

  const lastRuns = [
    { id: "1", tool: "db.query", agent: "invoice-agent", duration: "1.2s", status: "success" },
    { id: "2", tool: "s3.read", agent: "data-processor", duration: "0.8s", status: "success" },
    { id: "3", tool: "api.call", agent: "webhook-handler", duration: "2.1s", status: "failed" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">
          {t("dashboard.title")}
        </h1>
        <p className="text-slate-400">Overview of your AI agents and system</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Bot}
          label={t("dashboard.activeAgents")}
          value={stats?.activeAgents || 0}
          color="purple"
        />
        <StatCard
          icon={Plug}
          label={t("dashboard.activeConnections")}
          value={stats?.activeConnections || 0}
          color="blue"
        />
        <StatCard
          icon={Wrench}
          label={t("dashboard.toolsSynced")}
          value={stats?.toolsSynced || 0}
          color="green"
        />
        <StatCard
          icon={Play}
          label={t("dashboard.runsLast24h")}
          value={stats?.runsLast24h || 0}
          color="pink"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            {t("dashboard.runsOverTime")}
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={runsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                }}
              />
              <Line
                type="monotone"
                dataKey="runs"
                stroke="#a855f7"
                strokeWidth={2}
                dot={{ fill: "#a855f7" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">
            {t("dashboard.agentHealth")}
          </h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={healthData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={(entry: any) =>
                  `${entry.name} ${((entry.percent || 0) * 100).toFixed(0)}%`
                }
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {healthData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Last Runs Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="p-6 border-b border-slate-800">
          <h3 className="text-lg font-semibold text-white">
            {t("dashboard.lastRuns")}
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-slate-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {t("runs.runId")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {t("runs.tool")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {t("runs.agent")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {t("runs.duration")}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                  {t("common.status")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {lastRuns.map((run) => (
                <tr key={run.id} className="hover:bg-slate-800/50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                    {run.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                    {run.tool}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                    {run.agent}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                    {run.duration}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        run.status === "success"
                          ? "bg-green-500/20 text-green-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: any;
  label: string;
  value: number;
  color: string;
}) {
  const colorClasses = {
    purple: "from-purple-500 to-pink-500",
    blue: "from-blue-500 to-cyan-500",
    green: "from-green-500 to-emerald-500",
    pink: "from-pink-500 to-rose-500",
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-400 text-sm mb-1">{label}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
        </div>
        <div
          className={`w-12 h-12 rounded-lg bg-gradient-to-br ${colorClasses[color as keyof typeof colorClasses]} flex items-center justify-center`}
        >
          <Icon className="w-6 h-6 text-white" />
        </div>
      </div>
    </div>
  );
}

