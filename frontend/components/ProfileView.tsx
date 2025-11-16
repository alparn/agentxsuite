"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { User, Mail, Building2, Plus, Check } from "lucide-react";

export function ProfileView() {
  const t = useTranslations();
  const queryClient = useQueryClient();
  const { user, setAuth } = useAuthStore();
  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
  });
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showAddOrg, setShowAddOrg] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgId, setNewOrgId] = useState("");
  const [orgOption, setOrgOption] = useState<"new" | "existing">("new");

  // Fetch current user data
  const { data: userData, isLoading } = useQuery({
    queryKey: ["current-user"],
    queryFn: async () => {
      const response = await authApi.me();
      return response.data;
    },
  });

  // Fetch user's organizations
  const { data: orgsData } = useQuery({
    queryKey: ["my-organizations"],
    queryFn: async () => {
      const response = await authApi.myOrganizations();
      return Array.isArray(response.data)
        ? response.data
        : response.data?.organizations || [];
    },
  });

  const organizations = Array.isArray(orgsData) ? orgsData : [];

  // Update form data when userData changes
  useEffect(() => {
    if (userData) {
      setFormData({
        first_name: userData.first_name || "",
        last_name: userData.last_name || "",
        email: userData.email || "",
      });
    }
  }, [userData]);

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: async (data: { first_name?: string; last_name?: string; email?: string }) => {
      return authApi.patchMe(data);
    },
    onSuccess: (response) => {
      setSuccess("Profile updated successfully");
      setError("");
      setIsEditing(false);
      // Update auth store
      if (user) {
        setAuth(
          {
            ...user,
            ...response.data,
          },
          localStorage.getItem("auth_token") || ""
        );
      }
      queryClient.invalidateQueries({ queryKey: ["current-user"] });
    },
    onError: (err: any) => {
      setError(
        err.response?.data?.error ||
          Object.values(err.response?.data || {}).flat().join(", ") ||
          "Failed to update profile"
      );
      setSuccess("");
    },
  });

  // Add organization mutation
  const addOrgMutation = useMutation({
    mutationFn: async (data: { organization_id?: string; organization_name?: string }) => {
      return authApi.addOrganization(data);
    },
    onSuccess: () => {
      setSuccess("Organization added successfully");
      setError("");
      setShowAddOrg(false);
      setNewOrgName("");
      setNewOrgId("");
      queryClient.invalidateQueries({ queryKey: ["my-organizations"] });
      queryClient.invalidateQueries({ queryKey: ["current-user"] });
    },
    onError: (err: any) => {
      setError(
        err.response?.data?.error ||
          Object.values(err.response?.data || {}).flat().join(", ") ||
          "Failed to add organization"
      );
      setSuccess("");
    },
  });

  const handleSave = () => {
    setError("");
    setSuccess("");
    updateProfileMutation.mutate(formData);
  };

  const handleAddOrg = () => {
    setError("");
    setSuccess("");
    if (orgOption === "new" && newOrgName.trim()) {
      addOrgMutation.mutate({ organization_name: newOrgName.trim() });
    } else if (orgOption === "existing" && newOrgId.trim()) {
      addOrgMutation.mutate({ organization_id: newOrgId.trim() });
    } else {
      setError("Please provide organization name or ID");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-slate-400">{t("common.loading")}</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Profile</h1>
        <p className="text-slate-400">Manage your profile information and organizations</p>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-500/10 border border-green-500/20 text-green-400 px-4 py-3 rounded-lg text-sm">
          {success}
        </div>
      )}

      {/* Profile Information */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <User className="w-5 h-5 text-purple-400" />
            Profile Information
          </h2>
          {!isEditing && (
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              {t("common.edit")}
            </button>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {t("common.firstName")}
            </label>
            <input
              type="text"
              value={formData.first_name}
              onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              {t("common.lastName")}
            </label>
            <input
              type="text"
              value={formData.last_name}
              onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
              <Mail className="w-4 h-4" />
              {t("common.email")}
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              disabled={!isEditing}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {isEditing && (
            <div className="flex gap-3 pt-2">
              <button
                onClick={handleSave}
                disabled={updateProfileMutation.isPending}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {updateProfileMutation.isPending ? t("common.loading") : t("common.save")}
              </button>
              <button
                onClick={() => {
                  setIsEditing(false);
                  setError("");
                  setSuccess("");
                  if (userData) {
                    setFormData({
                      first_name: userData.first_name || "",
                      last_name: userData.last_name || "",
                      email: userData.email || "",
                    });
                  }
                }}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                {t("common.cancel")}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Current Organization */}
      {userData?.organization && (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
            <Building2 className="w-5 h-5 text-purple-400" />
            Current Organization
          </h2>
          <div className="bg-slate-800 rounded-lg p-4">
            <div className="text-white font-medium">{userData.organization.name}</div>
            <div className="text-slate-400 text-sm mt-1">ID: {userData.organization.id}</div>
          </div>
        </div>
      )}

      {/* Organizations */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Building2 className="w-5 h-5 text-purple-400" />
            Organizations
          </h2>
          <button
            onClick={() => setShowAddOrg(!showAddOrg)}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            {t("common.add")}
          </button>
        </div>

        {showAddOrg && (
          <div className="bg-slate-800 rounded-lg p-4 mb-4 space-y-4">
            <div className="space-y-2">
              <div className="flex gap-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="orgOption"
                    value="new"
                    checked={orgOption === "new"}
                    onChange={(e) => {
                      setOrgOption("new");
                      setNewOrgId("");
                    }}
                    className="w-4 h-4 text-purple-500 bg-slate-700 border-slate-600 focus:ring-purple-500"
                  />
                  <span className="text-slate-300 text-sm">{t("auth.createOrganization")}</span>
                </label>
              </div>
              <div className="flex gap-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="orgOption"
                    value="existing"
                    checked={orgOption === "existing"}
                    onChange={(e) => {
                      setOrgOption("existing");
                      setNewOrgName("");
                    }}
                    className="w-4 h-4 text-purple-500 bg-slate-700 border-slate-600 focus:ring-purple-500"
                  />
                  <span className="text-slate-300 text-sm">{t("auth.joinOrganization")}</span>
                </label>
              </div>
            </div>
            {orgOption === "new" && (
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder={t("auth.organizationNamePlaceholder")}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            )}
            {orgOption === "existing" && (
              <input
                type="text"
                value={newOrgId}
                onChange={(e) => setNewOrgId(e.target.value)}
                placeholder={t("auth.organizationIdPlaceholder")}
                className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            )}
            <div className="flex gap-3">
              <button
                onClick={handleAddOrg}
                disabled={addOrgMutation.isPending}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addOrgMutation.isPending ? t("common.loading") : t("common.add")}
              </button>
              <button
                onClick={() => {
                  setShowAddOrg(false);
                  setNewOrgName("");
                  setNewOrgId("");
                  setError("");
                }}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
              >
                {t("common.cancel")}
              </button>
            </div>
          </div>
        )}

        {organizations.length === 0 ? (
          <div className="text-slate-400 text-sm">
            {userData?.organization
              ? "You are currently in one organization"
              : "No organizations found. Add one to get started."}
          </div>
        ) : (
          <div className="space-y-2">
            {organizations.map((org: any) => (
              <div
                key={org.id}
                className={`bg-slate-800 rounded-lg p-4 flex items-center justify-between ${
                  userData?.organization_id === org.id ? "ring-2 ring-purple-500" : ""
                }`}
              >
                <div>
                  <div className="text-white font-medium flex items-center gap-2">
                    {org.name}
                    {userData?.organization_id === org.id && (
                      <Check className="w-4 h-4 text-green-400" />
                    )}
                  </div>
                  <div className="text-slate-400 text-sm mt-1">ID: {org.id}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

