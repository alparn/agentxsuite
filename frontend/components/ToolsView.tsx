"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { Plus, Play, CheckCircle2, XCircle, Edit } from "lucide-react";
import { ToolDialog } from "./ToolDialog";

export function ToolsView() {
  const t = useTranslations();
  const orgId = useAppStore((state) => state.currentOrgId);
  const [selectedTool, setSelectedTool] = useState<any>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<any>(null);

  const { data: tools, isLoading } = useQuery({
    queryKey: ["tools", orgId],
    queryFn: async () => {
      if (!orgId) return [];
      const response = await api.get(`/orgs/${orgId}/tools/`);
      return response.data;
    },
    enabled: !!orgId,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">
            {t("tools.title")}
          </h1>
          <p className="text-slate-400">Manage and test your tools</p>
        </div>
        <button
          onClick={() => {
            setEditingTool(null);
            setIsDialogOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all"
        >
          <Plus className="w-5 h-5" />
          {t("tools.defineTool")}
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-slate-400">{t("common.loading")}</div>
      ) : (
        <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-800">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.name")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("tools.version")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("tools.origin")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.status")}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                    {t("common.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {tools?.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                      {t("common.noData")}
                    </td>
                  </tr>
                ) : (
                  tools?.map((tool: any) => (
                    <tr key={tool.id} className="hover:bg-slate-800/50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-medium">
                        {tool.name}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {tool.version}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-300">
                        {tool.connection ? "Connection" : "Manual"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-2 py-1 text-xs rounded-full flex items-center gap-1 ${
                            tool.enabled
                              ? "bg-green-500/20 text-green-400"
                              : "bg-slate-500/20 text-slate-400"
                          }`}
                        >
                          {tool.enabled ? (
                            <CheckCircle2 className="w-3 h-3" />
                          ) : (
                            <XCircle className="w-3 h-3" />
                          )}
                          {tool.enabled ? "Enabled" : "Disabled"}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingTool(tool);
                              setIsDialogOpen(true);
                            }}
                            className="p-2 text-slate-400 hover:text-purple-400 hover:bg-purple-500/10 rounded transition-colors"
                            title={t("common.edit")}
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setSelectedTool(tool)}
                            className="p-2 text-slate-400 hover:text-green-400 hover:bg-green-500/10 rounded transition-colors"
                            title={t("tools.testRun")}
                          >
                            <Play className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedTool && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg w-full max-w-2xl p-6 space-y-4">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
              {selectedTool.name}
            </h2>
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-medium text-slate-400 dark:text-slate-500 mb-2">
                  Schema JSON
                </h3>
                <pre className="bg-slate-100 dark:bg-slate-800 p-4 rounded-lg text-sm text-slate-900 dark:text-slate-300 overflow-x-auto font-mono">
                  {JSON.stringify(selectedTool.schema_json || {}, null, 2)}
                </pre>
              </div>
              <button
                onClick={() => setSelectedTool(null)}
                className="w-full px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        </div>
      )}

      <ToolDialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setEditingTool(null);
        }}
        tool={editingTool}
        orgId={orgId}
      />
    </div>
  );
}

