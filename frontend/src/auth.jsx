import { createContext, useContext, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { clearSession, getStoredUser, getToken, login as apiLogin, saveSession } from "./api.js";

const AuthContext = createContext(null);

// Platform admins manage tenants; staff work cases. Each lands on their own home page.
export const homeFor = (user) => (user?.role === "admin" ? "/admin" : "/cases");

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => (getToken() ? getStoredUser() : null));

  async function login(username, password) {
    const result = await apiLogin(username, password);
    saveSession(result.access_token, result.user);
    setUser(result.user);
    return result.user;
  }

  function logout() {
    clearSession();
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

// UX only - the API enforces roles on every request.
export function RequireAuth({ role, children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (role && user.role !== role) return <Navigate to={homeFor(user)} replace />;
  return children;
}
