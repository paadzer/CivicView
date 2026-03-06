// Import Axios for making HTTP requests to the Django API
import axios from "axios";

// Create Axios instance with base URL for all API requests
const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/",
});

// Auth token: add to requests when present (for create report, etc.)
const AUTH_TOKEN_KEY = "civicview_token";

const AUTH_USER_KEY = "civicview_user";

export const getStoredToken = () => localStorage.getItem(AUTH_TOKEN_KEY);
export const getStoredUser = () => localStorage.getItem(AUTH_USER_KEY);
export const setAuthToken = (token, username = null) => {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
    if (username) localStorage.setItem(AUTH_USER_KEY, username);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
  }
};

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

// Reports: optional params e.g. { category: "Lighting" }
export const fetchReports = (params = {}) => api.get("reports/", { params });

// Update a report (partial update, requires appropriate role/ownership)
export const updateReport = (id, payload) => api.patch(`reports/${id}/`, payload);

// Distinct categories for filter dropdown
export const fetchCategories = () => api.get("reports/categories/");

// Hotspots
export const fetchHotspots = () => api.get("hotspots/");
export const regenerateHotspots = (params = {}) =>
  api.post("hotspots/regenerate/", null, { params });

// Create report (requires auth token)
export const createReport = (payload) => api.post("reports/", payload);

// Auth: login returns { token }, register returns { token, username, role }
export const login = (username, password) =>
  api.post("auth/login/", { username, password });
export const register = (username, password, email = "") =>
  api.post("auth/register/", { username, password, email });

// Current user (id, username, role) - requires auth
export const fetchMe = () => api.get("auth/me/");

// Users that can be assigned to reports (manager/admin only)
export const fetchAssignableUsers = () => api.get("auth/assignable-users/");

// In-app notifications (authenticated user)
export const fetchNotifications = () => api.get("notifications/");
export const markNotificationRead = (id) => api.patch(`notifications/${id}/read/`);

// Analytics (council/admin only)
export const fetchAnalyticsSummary = () => api.get("analytics/summary/");
export const fetchAnalyticsDashboard = () => api.get("analytics/dashboard/");
export const fetchCountyComparison = (countyNames) =>
  api.get("analytics/county-comparison/", {
    params: { counties: countyNames.join(",") },
  });
export const fetchConstituencyComparison = (constituencyNames) =>
  api.get("analytics/constituency-comparison/", {
    params: { constituencies: constituencyNames.join(",") },
  });
export const fetchGeographicReports = (type, name) =>
  api.get("analytics/geographic-reports/", {
    params: { type, name },
  });

// Boundaries (council/admin only). Use minimal=1 for fast list (id, name, report_count) without geometry.
export const fetchCounties = (params = {}) => api.get("counties/", { params });
export const fetchConstituencies = (params = {}) => api.get("constituencies/", { params });

export default api;
