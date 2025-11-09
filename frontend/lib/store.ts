import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        set({ user, token });
        if (typeof window !== "undefined") {
          localStorage.setItem("auth_token", token);
        }
      },
      clearAuth: () => {
        set({ user: null, token: null });
        if (typeof window !== "undefined") {
          localStorage.removeItem("auth_token");
        }
      },
      isAuthenticated: () => {
        return get().token !== null && get().user !== null;
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => (typeof window !== "undefined" ? localStorage : undefined as any)),
    }
  )
);

interface AppState {
  currentOrgId: string | null;
  currentEnvId: string | null;
  setCurrentOrg: (orgId: string | null) => void;
  setCurrentEnv: (envId: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentOrgId: null,
      currentEnvId: null,
      setCurrentOrg: (orgId) => set({ currentOrgId: orgId }),
      setCurrentEnv: (envId) => set({ currentEnvId: envId }),
    }),
    {
      name: "app-storage",
      storage: createJSONStorage(() => (typeof window !== "undefined" ? localStorage : undefined as any)),
    }
  )
);

