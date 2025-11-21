"use client";

import Link from "next/link";
import { usePathname, useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  Bot,
  Plug,
  Wrench,
  Play,
  Shield,
  Globe,
  FileText,
  Settings,
  LogOut as LogOutIcon,
  X,
  Database,
  MessageSquare,
  Wifi,
  Zap,
  Network,
  DollarSign,
  Package,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, key: "overview" },
  { href: "/axcore", icon: Zap, key: "axcore" },
  { href: "/canvas", icon: Network, key: "agentDesigner" },
  { href: "/agents", icon: Bot, key: "agents" },
  { href: "/connections", icon: Plug, key: "connections" },
  { href: "/tools", icon: Wrench, key: "tools" },
  { href: "/resources", icon: Database, key: "resources" },
  { href: "/prompts", icon: MessageSquare, key: "prompts" },
  { href: "/runs", icon: Play, key: "runs" },
  { href: "/cost-analytics", icon: DollarSign, key: "costAnalytics" },
  { href: "/policies", icon: Shield, key: "policies" },
  { href: "/environments", icon: Globe, key: "environments" },
  { href: "/mcp-connect", icon: Wifi, key: "mcpConnect" },
  { href: "/mcp-hub", icon: Package, key: "mcpHub" },
  { href: "/audit", icon: FileText, key: "audit" },
  { href: "/settings", icon: Settings, key: "settings" },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = true, onClose }: SidebarProps) {
  const t = useTranslations("nav");
  const tCommon = useTranslations("common");
  const pathname = usePathname();
  const params = useParams();
  const locale = (params?.locale as string) || "en";
  const clearAuth = useAuthStore((state) => state.clearAuth);

  const handleLogout = () => {
    clearAuth();
    window.location.href = "/login";
  };

  const handleLinkClick = () => {
    if (onClose) {
      onClose();
    }
  };

  return (
    <div
      className={cn(
        "fixed lg:static h-screen w-64 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col transition-transform duration-300 z-50",
        isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}
    >
      {/* Logo */}
      <div className="p-4 sm:p-6 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2 sm:gap-3">
          <img src="/logo.svg" alt="AgentxSuite Logo" className="w-6 h-6 sm:w-8 sm:h-8" />
          <h1 className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-cyan-400 to-teal-400 bg-clip-text text-transparent">
            AgentxSuite
          </h1>
        </div>
        <button
          onClick={onClose}
          className="lg:hidden p-2 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 sm:p-4 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          // Remove locale prefix from pathname for comparison
          // Handle cases like "/de" or "/de/" -> "/"
          let pathnameWithoutLocale = pathname.replace(new RegExp(`^/${locale}(/|$)`), "/");
          if (pathnameWithoutLocale === "") {
            pathnameWithoutLocale = "/";
          }
          
          // Normalize paths: ensure they start with /
          const normalizedPathname = pathnameWithoutLocale;
          const normalizedHref = item.href;
          
          // Check if active: exact match or pathname starts with href + "/"
          // Special case: if pathname is "/" and href is "/dashboard", consider dashboard active
          const isActive = 
            normalizedPathname === normalizedHref || 
            (normalizedHref !== "/" && normalizedPathname.startsWith(normalizedHref + "/")) ||
            (normalizedPathname === "/" && normalizedHref === "/dashboard");
          
          const isAxCore = item.href === "/axcore";
          const hrefWithLocale = `/${locale}${item.href}`;
          
          return (
            <Link
              key={item.href}
              href={hrefWithLocale}
              onClick={handleLinkClick}
              className={cn(
                "flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2 sm:py-3 rounded-lg transition-colors text-sm sm:text-base",
                isActive
                  ? isAxCore
                    ? "bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-purple-400 border border-purple-500/30"
                    : "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                  : isAxCore
                    ? "text-purple-400/70 hover:text-purple-400 hover:bg-purple-500/10"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
              )}
            >
              <Icon className={cn(
                "w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0",
                isAxCore && isActive && "text-purple-400"
              )} />
              <span className="font-medium truncate">{t(item.key)}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logout */}
      <div className="p-2 sm:p-4 border-t border-slate-800">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2 sm:py-3 w-full rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors text-sm sm:text-base"
        >
          <LogOutIcon className="w-4 h-4 sm:w-5 sm:h-5 flex-shrink-0" />
          <span className="font-medium">{tCommon("logout")}</span>
        </button>
      </div>
    </div>
  );
}

