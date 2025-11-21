"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";
import { mcpHubApi, type MCPHubServer } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import {
  Search,
  Github,
  Star,
  GitFork,
  ExternalLink,
  Loader2,
  AlertCircle,
  Package,
  Code,
  Globe,
  Filter,
  X,
  ArrowUpDown,
} from "lucide-react";

// Using MCPHubServer type from api.ts

type SortOption = "stargazers_count" | "forks_count" | "updated_at_github" | "name";

export function MCPHubView() {
  const t = useTranslations();
  const { currentOrgId: orgId } = useAppStore();
  const [searchQuery, setSearchQuery] = useState("");
  const [filteredServers, setFilteredServers] = useState<MCPHubServer[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  
  // Filter states
  const [selectedLanguage, setSelectedLanguage] = useState<string>("");
  const [minStars, setMinStars] = useState<string>("");
  const [maxStars, setMaxStars] = useState<string>("");
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState<SortOption>("stargazers_count");

  // Fetch all servers for filter options (no filters applied)
  const { data: allServersForFilters } = useQuery({
    queryKey: ["mcp-hub-servers-all"],
    queryFn: async () => {
      const response = await mcpHubApi.list({});
      // Handle paginated response
      return Array.isArray(response.data) ? response.data : (response.data?.results || []);
    },
    staleTime: 1000 * 60 * 10, // Cache for 10 minutes
  });

  // Fetch MCP servers from database (synced from GitHub) with filters
  const { data: mcpServers, isLoading, error } = useQuery({
    queryKey: ["mcp-hub-servers", selectedLanguage, minStars, maxStars, selectedTopics, sortBy, searchQuery],
    queryFn: async () => {
      const response = await mcpHubApi.list({
        language: selectedLanguage || undefined,
        min_stars: minStars ? parseInt(minStars) : undefined,
        max_stars: maxStars ? parseInt(maxStars) : undefined,
        topic: selectedTopics.length > 0 ? selectedTopics : undefined,
        search: searchQuery || undefined,
        sort: sortBy,
      });
      // Handle paginated response
      return Array.isArray(response.data) ? response.data : (response.data?.results || []);
    },
    staleTime: 1000 * 60 * 5, // Cache for 5 minutes (data is synced periodically)
    retry: 2,
  });

  // Get unique languages and topics from all servers (for filter options)
  const availableLanguages = allServersForFilters
    ? Array.from(new Set(allServersForFilters.map((s) => s.language).filter(Boolean))).sort()
    : [];
  
  const availableTopics = allServersForFilters
    ? Array.from(
        new Set(allServersForFilters.flatMap((s) => s.topics || []))
      ).sort()
    : [];

  // Update filtered servers when data changes (filtering is done server-side)
  useEffect(() => {
    if (!mcpServers) {
      setFilteredServers([]);
      return;
    }
    setFilteredServers(mcpServers);
  }, [mcpServers]);

  const toggleTopic = (topic: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic]
    );
  };

  const clearFilters = () => {
    setSelectedLanguage("");
    setMinStars("");
    setMaxStars("");
    setSelectedTopics([]);
    setSortBy("stargazers_count");
    setSearchQuery("");
  };

  const hasActiveFilters =
    selectedLanguage || minStars || maxStars || selectedTopics.length > 0 || sortBy !== "stargazers_count";

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg">
            <Package className="h-7 w-7 text-white" />
          </div>
          MCP Hub
        </h1>
        <p className="text-slate-400">
          Discover and explore MCP (Model Context Protocol) servers from GitHub
        </p>
      </div>

      {/* Search and Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-4">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-5 h-5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search MCP servers by name, description, or topic..."
              className="w-full pl-10 pr-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white hover:bg-slate-700 transition-colors flex items-center gap-2 ${
              showFilters || hasActiveFilters
                ? "border-purple-500 bg-purple-500/10"
                : ""
            }`}
          >
            <Filter className="w-5 h-5" />
            Filters
            {hasActiveFilters && (
              <span className="px-2 py-0.5 bg-purple-500 text-white text-xs rounded-full">
                {[
                  selectedLanguage && 1,
                  minStars && 1,
                  maxStars && 1,
                  selectedTopics.length,
                ].filter(Boolean).reduce((a, b) => (a || 0) + (b || 0), 0)}
              </span>
            )}
          </button>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="border-t border-slate-800 pt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Language Filter */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Language
                </label>
                <select
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">All Languages</option>
                  {availableLanguages.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </div>

              {/* Stars Range */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Stars (Min)
                </label>
                <input
                  type="number"
                  value={minStars}
                  onChange={(e) => setMinStars(e.target.value)}
                  placeholder="0"
                  min="0"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Stars (Max)
                </label>
                <input
                  type="number"
                  value={maxStars}
                  onChange={(e) => setMaxStars(e.target.value)}
                  placeholder="∞"
                  min="0"
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              {/* Sort */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                  <ArrowUpDown className="w-4 h-4" />
                  Sort By
                </label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as SortOption)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="stargazers_count">Most Stars</option>
                  <option value="forks_count">Most Forks</option>
                  <option value="updated_at_github">Recently Updated</option>
                  <option value="name">Name (A-Z)</option>
                </select>
              </div>
            </div>

            {/* Topics Filter */}
            {availableTopics.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Topics ({selectedTopics.length} selected)
                </label>
                <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto p-2 bg-slate-800/50 rounded-lg border border-slate-700">
                  {availableTopics.slice(0, 30).map((topic) => (
                    <button
                      key={topic}
                      onClick={() => toggleTopic(topic)}
                      className={`px-3 py-1 rounded-md text-xs transition-colors ${
                        selectedTopics.includes(topic)
                          ? "bg-purple-500 text-white"
                          : "bg-slate-700 text-slate-300 hover:bg-slate-600"
                      }`}
                    >
                      {topic}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Clear Filters */}
            {hasActiveFilters && (
              <div className="flex justify-end">
                <button
                  onClick={clearFilters}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-white flex items-center gap-2 transition-colors"
                >
                  <X className="w-4 h-4" />
                  Clear All Filters
                </button>
              </div>
            )}
          </div>
        )}

        {/* Results Count */}
        {mcpServers && (
          <p className="text-sm text-slate-400">
            Showing {filteredServers.length} of {mcpServers.length} MCP server
            {mcpServers.length !== 1 ? "s" : ""}
            {hasActiveFilters && " (filtered)"}
          </p>
        )}
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          <span className="ml-3 text-slate-400">Discovering MCP servers...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400" />
            <div>
              <h3 className="text-red-400 font-semibold">Failed to load MCP servers</h3>
              <p className="text-slate-400 text-sm mt-1">
                {error instanceof Error ? error.message : "Unknown error occurred"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Server Grid */}
      {!isLoading && !error && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredServers.map((server) => (
            <div
              key={server.id}
              className="bg-slate-900 border border-slate-800 rounded-xl p-6 hover:border-purple-500/50 transition-all duration-300 hover:shadow-lg hover:shadow-purple-500/10 group"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <img
                    src={server.owner_avatar_url}
                    alt={server.owner_login}
                    className="w-10 h-10 rounded-full flex-shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="text-white font-semibold text-lg truncate group-hover:text-purple-400 transition-colors">
                      {server.name}
                    </h3>
                    <p className="text-slate-500 text-sm truncate">{server.owner_login}</p>
                  </div>
                </div>
                <a
                  href={server.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 text-slate-400 hover:text-purple-400 transition-colors flex-shrink-0"
                  title="View on GitHub"
                >
                  <ExternalLink className="w-5 h-5" />
                </a>
              </div>

              {/* Description */}
              {server.description && (
                <p className="text-slate-400 text-sm mb-4 line-clamp-2">
                  {server.description}
                </p>
              )}

              {/* Stats */}
              <div className="flex items-center gap-4 mb-4 text-sm text-slate-500">
                <div className="flex items-center gap-1">
                  <Star className="w-4 h-4" />
                  <span>{server.stargazers_count.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-1">
                  <GitFork className="w-4 h-4" />
                  <span>{server.forks_count.toLocaleString()}</span>
                </div>
                {server.language && (
                  <div className="flex items-center gap-1">
                    <Code className="w-4 h-4" />
                    <span>{server.language}</span>
                  </div>
                )}
              </div>

              {/* Topics */}
              {server.topics && server.topics.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {server.topics.slice(0, 5).map((topic) => (
                    <span
                      key={topic}
                      className="px-2 py-1 bg-slate-800 text-slate-300 text-xs rounded-md"
                    >
                      {topic}
                    </span>
                  ))}
                  {server.topics.length > 5 && (
                    <span className="px-2 py-1 text-slate-500 text-xs">
                      +{server.topics.length - 5}
                    </span>
                  )}
                </div>
              )}

              {/* Footer */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                <span className="text-xs text-slate-500">
                  Updated {formatDate(server.updated_at_github)}
                </span>
                <a
                  href={server.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1 transition-colors"
                >
                  <Github className="w-4 h-4" />
                  View Repo
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredServers.length === 0 && (
        <div className="text-center py-12 bg-slate-900 border border-slate-800 rounded-xl">
          <Package className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">
            {searchQuery
              ? "No MCP servers found matching your search"
              : "No MCP servers found"}
          </p>
        </div>
      )}
    </div>
  );
}

