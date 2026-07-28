/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export interface AdminUser {
  authenticated: boolean;
  name: string;
  email: string;
  role: string;
}

interface AuthContextType {
  user: AdminUser | null;
  loading: boolean;
  sessionExpired: boolean;
  login: (user: AdminUser) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    // Check session on mount
    fetch('/api/auth/admin/session', { credentials: 'include' })
      .then(async (res) => {
        if (res.ok) return res.json();
        const payload = (await res.json().catch(() => null)) as { error?: { code?: string } } | null;
        if (payload?.error?.code === 'SESSION_EXPIRED') setSessionExpired(true);
        return Promise.reject(res);
      })
      .then((data) => {
        if (data.authenticated) {
          setUser(data);
          setSessionExpired(false);
        }
      })
      .catch(() => {
        // Not authenticated
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const login = (newUser: AdminUser) => {
    setUser(newUser);
    setSessionExpired(false);
  };

  const logout = async () => {
    try {
      await fetch('/api/auth/admin/logout', { method: 'POST', credentials: 'include' });
    } catch {
      // Ignore error on logout
    }
    setUser(null);
    setSessionExpired(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, sessionExpired, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
