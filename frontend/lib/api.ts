import axios from "axios";
import type { Resource, Prompt } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("auth_token");
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// Resources API
export const resourcesApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/resources/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/resources/${id}/`),
  create: (orgId: string, data: Partial<Resource>) =>
    api.post(`/orgs/${orgId}/resources/`, data),
  update: (orgId: string, id: string, data: Partial<Resource>) =>
    api.put(`/orgs/${orgId}/resources/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/resources/${id}/`),
};

// Prompts API
export const promptsApi = {
  list: (orgId: string) => api.get(`/orgs/${orgId}/prompts/`),
  get: (orgId: string, id: string) => api.get(`/orgs/${orgId}/prompts/${id}/`),
  create: (orgId: string, data: Partial<Prompt>) =>
    api.post(`/orgs/${orgId}/prompts/`, data),
  update: (orgId: string, id: string, data: Partial<Prompt>) =>
    api.put(`/orgs/${orgId}/prompts/${id}/`, data),
  delete: (orgId: string, id: string) =>
    api.delete(`/orgs/${orgId}/prompts/${id}/`),
};

export default api;

