/**
 * CivicView mobile API client.
 * Defaults to the production API on Railway.
 * You can override by setting global.__API_BASE_URL__ in development.
 */

const getBaseUrl = () => {
  if (typeof global !== "undefined" && global.__API_BASE_URL__) {
    return global.__API_BASE_URL__.replace(/\/$/, "");
  }
  // Default: production backend
  return "https://civicview-production.up.railway.app/api";
};

const baseURL = getBaseUrl();

let _token = null;
export const setApiToken = (t) => {
  _token = t;
};
const getToken = () => _token;

const headers = (withAuth = true) => {
  const h = { "Content-Type": "application/json" };
  const token = withAuth && getToken();
  if (token) h["Authorization"] = `Token ${token}`;
  return h;
};

export const api = {
  get: (path) =>
    fetch(`${baseURL}${path.startsWith("/") ? path : `/${path}`}`, {
      method: "GET",
      headers: headers(),
    }).then(async (r) => {
      const ct = r.headers.get("content-type") || "";
      const isJson = ct.includes("application/json");
      const data = isJson ? await r.json() : null;
      if (!r.ok) {
        const err = data || {
          detail: `HTTP ${r.status} ${r.statusText || ""}`.trim(),
        };
        // Attach status for easier debugging
        err.status = r.status;
        return Promise.reject(err);
      }
      return data;
    }),

  post: (path, body) =>
    fetch(`${baseURL}${path.startsWith("/") ? path : `/${path}`}`, {
      method: "POST",
      headers: headers(),
      body: body ? JSON.stringify(body) : undefined,
    }).then(async (r) => {
      const ct = r.headers.get("content-type") || "";
      const isJson = ct.includes("application/json");
      const data = isJson ? await r.json() : null;
      if (!r.ok) {
        const err = data || {
          detail: `HTTP ${r.status} ${r.statusText || ""}`.trim(),
        };
        err.status = r.status;
        return Promise.reject(err);
      }
      return data;
    }),

  postMultipart: (path, formData) =>
    fetch(`${baseURL}${path.startsWith("/") ? path : `/${path}`}`, {
      method: "POST",
      headers: { Authorization: getToken() ? `Token ${getToken()}` : "" },
      body: formData,
    }).then((r) => {
      const ct = r.headers.get("content-type");
      const isJson = ct && ct.includes("application/json");
      if (!r.ok) {
        return isJson ? r.json().then((d) => Promise.reject(d)) : Promise.reject(new Error(r.statusText));
      }
      return isJson ? r.json() : r.text().then(() => ({}));
    }),
};

export const login = (username, password) =>
  api.post("/auth/login/", { username, password });

export const register = (username, password, email = "") =>
  api.post("/auth/register/", { username, password, email });

export const fetchMe = () => api.get("/auth/me/");

export const fetchCategories = () => api.get("/reports/categories/");

export const fetchReports = (params = {}) => {
  const q = new URLSearchParams(params).toString();
  return api.get(q ? `reports/?${q}` : "reports/");
};

export const createReport = (data) => api.post("/reports/", data);

export const uploadReportImages = (reportId, imageUris) => {
  const formData = new FormData();
  imageUris.forEach((uri, i) => {
    formData.append("images", {
      uri,
      name: `photo_${i}.jpg`,
      type: "image/jpeg",
    });
  });
  return api.postMultipart(`/reports/${reportId}/images/`, formData);
};

export default api;
