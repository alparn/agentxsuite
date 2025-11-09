"use client";

import { useTranslations } from "next-intl";
import { Key, Globe } from "lucide-react";

export function SettingsView() {
  const t = useTranslations();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">
          {t("nav.settings")}
        </h1>
        <p className="text-slate-400">Manage your settings and preferences</p>
      </div>

      <div className="space-y-4">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Key className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">API Keys</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Manage your API keys and tokens
          </p>
          <button className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors">
            Generate New Key
          </button>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <Globe className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Language</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Change your preferred language
          </p>
          <select className="px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500">
            <option value="en">English</option>
            <option value="de">Deutsch</option>
          </select>
        </div>
      </div>
    </div>
  );
}

