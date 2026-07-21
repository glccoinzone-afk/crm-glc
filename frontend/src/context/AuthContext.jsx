import React, { createContext, useContext, useEffect, useState } from "react";
import api from "@/lib/glc";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("glc_user") || "null"); } catch { return null; }
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("glc_token");
    if (t) {
      api.get("/auth/me")
        .then((r) => {
          setUser(r.data);
          localStorage.setItem("glc_user", JSON.stringify(r.data));
        })
        .catch(() => {
          localStorage.removeItem("glc_token");
          localStorage.removeItem("glc_user");
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    localStorage.setItem("glc_token", r.data.token);
    localStorage.setItem("glc_user", JSON.stringify(r.data.user));
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = () => {
    localStorage.removeItem("glc_token");
    localStorage.removeItem("glc_user");
    setUser(null);
    window.location.href = "/login";
  };

  return <AuthCtx.Provider value={{ user, loading, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

const VerticalCtx = createContext(null);
export function VerticalProvider({ children }) {
  const [vertical, setVertical] = useState(() => localStorage.getItem("glc_vertical") || "ALL");
  useEffect(() => { localStorage.setItem("glc_vertical", vertical); }, [vertical]);
  return <VerticalCtx.Provider value={{ vertical, setVertical }}>{children}</VerticalCtx.Provider>;
}
export const useVertical = () => useContext(VerticalCtx);
