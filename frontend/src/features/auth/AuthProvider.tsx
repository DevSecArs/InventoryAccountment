import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getCurrentUser, login as loginRequest, logout as logoutRequest, register as registerRequest, type Credentials, type Registration, type User } from "../../api/auth";
import { ApiError, setCsrfToken } from "../../api/client";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (credentials: Credentials) => Promise<void>;
  register: (payload: Registration) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentUser()
      .then((result) => { setUser(result.user); setCsrfToken(result.csrf_token); })
      .catch((error: unknown) => { if (!(error instanceof ApiError) || error.status !== 401) throw error; })
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    login: async (credentials) => { const result = await loginRequest(credentials); setCsrfToken(result.csrf_token); setUser(result.user); },
    register: async (payload) => { const result = await registerRequest(payload); setCsrfToken(result.csrf_token); setUser(result.user); },
    logout: async () => { await logoutRequest(); setCsrfToken(undefined); setUser(null); },
    updateUser: setUser,
  }), [loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth должен использоваться внутри AuthProvider");
  return value;
}
