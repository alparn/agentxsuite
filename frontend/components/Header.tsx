"use client";

import { useTranslations } from "next-intl";
import { Globe, Moon, Sun } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { useState, useEffect } from "react";

export function Header() {
  const t = useTranslations();
  const user = useAuthStore((state) => state.user);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setDarkMode(isDark);
  }, []);

  const toggleDarkMode = () => {
    document.documentElement.classList.toggle("dark");
    setDarkMode(!darkMode);
  };

  return (
    <header className="h-16 bg-slate-900 border-b border-slate-800 flex items-center justify-between px-6">
      <div className="flex items-center gap-4">
        {/* Environment Switcher could go here */}
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={toggleDarkMode}
          className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
        >
          {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>

        <div className="flex items-center gap-3 px-4 py-2 rounded-lg bg-slate-800">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm font-semibold">
            {user?.first_name?.[0]}{user?.last_name?.[0]}
          </div>
          <div className="text-sm">
            <div className="text-slate-200 font-medium">
              {user?.first_name} {user?.last_name}
            </div>
            <div className="text-slate-400 text-xs">{user?.email}</div>
          </div>
        </div>
      </div>
    </header>
  );
}

