// Small fetch wrapper: adds the bearer token, parses JSON errors, and sends the user to /login on 401.
const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "plateScan.token";
const USER_KEY = "plateScan.user";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// FastAPI returns {"detail": "..."} or, for validation errors, {"detail": [{msg, loc}, ...]}.
function errorMessage(data, fallback) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ");
  return fallback;
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}`);
  }

  const data = await response.json().catch(() => null);

  // An expired/invalid token on any authenticated call ends the session.
  if (response.status === 401 && token) {
    clearSession();
    window.location.assign("/login");
  }
  if (!response.ok) {
    throw new ApiError(response.status, errorMessage(data, `Request failed (${response.status})`));
  }
  return data;
}

export const login = (username, password) =>
  api("/api/v1/auth/login", { method: "POST", body: { username, password } });
export const listCases = (status) =>
  api(`/api/v1/cases${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const getCase = (id) => api(`/api/v1/cases/${id}`);
export const getTrail = (id) => api(`/api/v1/cases/${id}/scans`);
export const claimCase = (id) => api(`/api/v1/cases/${id}/claim`, { method: "POST" });

// Platform admin only.
export const listTenants = () => api("/api/v1/admin/tenants");
export const createTenant = (name) => api("/api/v1/admin/tenants", { method: "POST", body: { name } });
export const listUsers = () => api("/api/v1/admin/users");
export const createStaffUser = (body) => api("/api/v1/admin/users", { method: "POST", body });
export const listCameras = () => api("/api/v1/admin/cameras");
export const createCamera = (body) => api("/api/v1/admin/cameras", { method: "POST", body });
