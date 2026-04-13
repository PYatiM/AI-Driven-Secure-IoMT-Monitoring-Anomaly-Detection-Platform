import { startTransition, useEffect, useState } from "react";

import API, { AUTH_TOKEN_STORAGE_KEY, setAuthToken } from "../services/api";
import { AuthContext } from "./auth-context";

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_STORAGE_KEY));
  const [user, setUser] = useState(() => {
    const storedUser = localStorage.getItem("iomt_user_profile");
    if (!storedUser) {
      return null;
    }

    try {
      return JSON.parse(storedUser);
    } catch {
      return null;
    }
  });
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  useEffect(() => {
    let cancelled = false;

    const bootstrapSession = async () => {
      if (!token) {
        if (!cancelled) {
          setIsReady(true);
        }
        return;
      }

      try {
        const response = await API.get("/api/v1/auth/me");
        if (!cancelled) {
          startTransition(() => {
            setUser(response.data);
            localStorage.setItem("iomt_user_profile", JSON.stringify(response.data));
            setIsReady(true);
          });
        }
      } catch {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        localStorage.removeItem("iomt_user_profile");
        setAuthToken(null);
        if (!cancelled) {
          startTransition(() => {
            setToken(null);
            setUser(null);
            setIsReady(true);
          });
        }
      }
    };

    bootstrapSession();

    return () => {
      cancelled = true;
    };
  }, [token]);

  const login = async ({ email, password }) => {
    const response = await API.post("/api/v1/auth/login", { email, password });
    const nextToken = response.data?.access_token;
    const nextUser = response.data?.user;

    if (!nextToken) {
      throw new Error("Login response did not contain an access token.");
    }

    localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, nextToken);
    if (nextUser) {
      localStorage.setItem("iomt_user_profile", JSON.stringify(nextUser));
    }
    setAuthToken(nextToken);
    setToken(nextToken);
    setUser(nextUser ?? null);

    return nextUser;
  };

  const logout = () => {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    localStorage.removeItem("iomt_user_profile");
    setAuthToken(null);
    setToken(null);
    setUser(null);
  };

  const value = {
    token,
    user,
    isReady,
    isAuthenticated: Boolean(token),
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
