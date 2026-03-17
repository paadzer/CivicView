// Import React hooks for state management and side effects
import { useCallback, useEffect, useState } from "react";
import { Link, Route, Routes, useLocation, useNavigate } from "react-router-dom";
// Import API functions for communicating with Django backend
import {
  createReport,
  fetchCategories,
  fetchHotspots,
  fetchReports,
  fetchMe,
  getStoredToken,
  getStoredUser,
  login as apiLogin,
  register as apiRegister,
  setAuthToken,
} from "./api";
// Import React components
import Dashboard from "./components/Dashboard";
import MapView from "./components/MapView";
import ReportForm from "./components/ReportForm";

// Main App component: Root component of the React application
function App() {
  const [reports, setReports] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [categories, setCategories] = useState([]);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [timeRangeFilter, setTimeRangeFilter] = useState("");
  const [showReportsLayer, setShowReportsLayer] = useState(true);
  const [showHotspotsLayer, setShowHotspotsLayer] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedLocation, setSelectedLocation] = useState(null);

  const [token, setToken] = useState(getStoredToken());
  const [user, setUser] = useState(getStoredUser());
  const [userId, setUserId] = useState(null);
  const [role, setRole] = useState(null);
  const [authMode, setAuthMode] = useState("login"); // "login" | "register"
  const [authError, setAuthError] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [hotspotsRefreshedNote, setHotspotsRefreshedNote] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const loadCategories = useCallback(async () => {
    try {
      const res = await fetchCategories();
      setCategories(res.data || []);
    } catch {
      setCategories([]);
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (categoryFilter) params.category = categoryFilter;
      if (timeRangeFilter) params.period = timeRangeFilter;
      const [reportsRes, hotspotsRes] = await Promise.all([
        fetchReports(params),
        fetchHotspots(),
      ]);
      setReports(reportsRes.data);
      setHotspots(hotspotsRes.data);
    } catch (err) {
      setError("Unable to load data from the API.");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, timeRangeFilter]);

  const refreshHotspots = useCallback(async () => {
    try {
      const hotspotsRes = await fetchHotspots();
      setHotspots(hotspotsRes.data || []);
    } catch {
      // ignore; map will show previous hotspots
    }
  }, []);

  // When returning to map after regenerating hotspots, refresh hotspot layer and show a brief note
  useEffect(() => {
    if (location.pathname !== "/" || !location.state?.hotspotsRefreshed) return;
    refreshHotspots();
    setHotspotsRefreshedNote(true);
    navigate("/", { replace: true, state: {} });
    const t = setTimeout(() => setHotspotsRefreshedNote(false), 4000);
    return () => clearTimeout(t);
  }, [location.pathname, location.state?.hotspotsRefreshed, navigate, refreshHotspots]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);

  // Fetch current user (id, username, role) when we have a token
  useEffect(() => {
    if (!token) {
      setRole(null);
      return;
    }
    fetchMe()
      .then((res) => {
        setUser(res.data.username);
        setUserId(res.data.id ?? null);
        setRole(res.data.role ?? null);
      })
      .catch(() => { setRole(null); setUserId(null); });
  }, [token]);

  const handleSubmit = async (values) => {
    setError(null);
    try {
      await createReport(values);
      await loadData();
      setSelectedLocation(null);
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.error || "Unable to submit the report.";
      setError(Array.isArray(msg) ? msg.join(" ") : msg);
    }
  };

  const handleMapClick = (lat, lng) => {
    setSelectedLocation({ lat, lng });
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    const form = e.target;
    const username = form.username?.value?.trim();
    const password = form.password?.value;
    if (!username || !password) {
      setAuthError("Username and password are required.");
      return;
    }
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await apiLogin(username, password);
      const t = res.data?.token;
      setAuthToken(t, username);
      setToken(t);
      setUser(username);
      setAuthMode("login");
    } catch (err) {
      setAuthError(err.response?.data?.detail || "Login failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    const form = e.target;
    const username = form.username?.value?.trim();
    const password = form.password?.value;
    const email = form.email?.value?.trim() || "";
    if (!username || !password) {
      setAuthError("Username and password are required.");
      return;
    }
    setAuthLoading(true);
    setAuthError(null);
    try {
      const res = await apiRegister(username, password, email);
      const t = res.data?.token;
      setAuthToken(t, username);
      setToken(t);
      setUser(username);
      setRole(res.data?.role ?? null);
      setAuthMode("login");
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.detail || "Registration failed.";
      setAuthError(Array.isArray(msg) ? msg.join(" ") : msg);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    setAuthToken(null);
    setToken(null);
    setUser(null);
    setUserId(null);
    setRole(null);
  };

  const isLoggedIn = !!token;
  const isCouncilOrAdmin = role === "council" || role === "admin";
  const isDashboardUser = ["staff", "council", "manager", "admin"].includes(role);

  return (
    <>
      <nav style={{ 
        background: "rgba(255, 255, 255, 0.95)", 
        backdropFilter: "blur(10px)",
        padding: "1rem 2rem", 
        borderBottom: "1px solid rgba(0, 0, 0, 0.1)", 
        display: "flex", 
        alignItems: "center", 
        gap: "1.5rem", 
        flexWrap: "wrap",
        boxShadow: "0 2px 10px rgba(0, 0, 0, 0.05)"
      }}>
        <Link to="/" style={{ 
          fontWeight: 700, 
          fontSize: "1.25rem",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          textDecoration: "none" 
        }}>
          Civic View
        </Link>
        {isLoggedIn && isDashboardUser && (
          <Link to="/dashboard" style={{ 
            color: "#667eea", 
            textDecoration: "none",
            fontWeight: 500,
            padding: "0.5rem 1rem",
            borderRadius: "8px",
            transition: "all 0.2s"
          }}
          onMouseEnter={(e) => e.target.style.background = "rgba(102, 126, 234, 0.1)"}
          onMouseLeave={(e) => e.target.style.background = "transparent"}
          >
            Dashboard
          </Link>
        )}
        {isLoggedIn ? (
          <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "1rem" }}>
            <span style={{ color: "#64748b", fontSize: "0.9rem" }}>
              Logged in as <strong style={{ color: "#0f172a" }}>{user ?? "User"}</strong>
            </span>
            <button 
              type="button" 
              onClick={handleLogout}
              style={{
                background: "white",
                color: "#667eea",
                border: "2px solid #667eea",
                padding: "0.5rem 1rem",
                borderRadius: "8px",
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.2s"
              }}
              onMouseEnter={(e) => {
                e.target.style.background = "#667eea";
                e.target.style.color = "white";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "white";
                e.target.style.color = "#667eea";
              }}
            >
              Log out
            </button>
          </span>
        ) : null}
      </nav>

      <Routes>
        <Route path="/dashboard" element={<Dashboard role={role} userId={userId} onHotspotsRegenerated={refreshHotspots} />} />
        <Route path="/" element={
    <main className="layout">
      <section className="panel" style={{ maxWidth: "450px", minWidth: "350px" }}>
        <h1>Civic View</h1>
        <p style={{ color: "#64748b", marginBottom: "2rem", lineHeight: "1.6" }}>
          Report civic issues and see hotspots detected with DBSCAN clustering.
        </p>

        {/* Auth: Login / Register */}
        {!isLoggedIn && (
          <div style={{ marginBottom: "2rem", padding: "1.5rem", background: "#f8fafc", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
            {authMode === "login" ? (
              <form onSubmit={handleLogin} className="auth-form">
                <input name="username" placeholder="Username" required />
                <input name="password" type="password" placeholder="Password" required />
                <div className="auth-buttons">
                  <button type="submit" disabled={authLoading}>
                    {authLoading ? "Logging in..." : "Log in"}
                  </button>
                  <button 
                    type="button" 
                    className="secondary-button"
                    onClick={() => { setAuthMode("register"); setAuthError(null); }}
                  >
                    Register
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="auth-form">
                <input name="username" placeholder="Username" required />
                <input name="password" type="password" placeholder="Password" required />
                <input name="email" type="email" placeholder="Email (optional)" />
                <div className="auth-buttons">
                  <button type="submit" disabled={authLoading}>
                    {authLoading ? "Registering..." : "Register"}
                  </button>
                  <button 
                    type="button" 
                    className="secondary-button"
                    onClick={() => { setAuthMode("login"); setAuthError(null); }}
                  >
                    Back to login
                  </button>
                </div>
              </form>
            )}
            {authError && (
              <p style={{ color: "#dc2626", marginTop: "1rem", fontSize: "0.875rem", padding: "0.75rem", background: "#fee2e2", borderRadius: "8px" }}>
                {authError}
              </p>
            )}
          </div>
        )}

        {isLoggedIn && (
          <div style={{ 
            marginBottom: "2rem", 
            padding: "1rem", 
            background: "linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%)",
            borderRadius: "12px",
            border: "1px solid rgba(102, 126, 234, 0.2)"
          }}>
            <p style={{ color: "#475569", margin: 0, fontSize: "0.9rem" }}>
              👋 Welcome back, <strong>{user ?? "User"}</strong>! 
              {isCouncilOrAdmin && (
                <> Access the <strong>Dashboard</strong> for analytics and management tools.</>
              )}
            </p>
          </div>
        )}

        {error && (
          <div style={{ 
            color: "#dc2626", 
            padding: "1rem", 
            background: "#fee2e2", 
            borderRadius: "10px",
            marginBottom: "1rem",
            border: "1px solid #fecaca"
          }}>
            {error}
          </div>
        )}

        {isLoggedIn ? (
          <ReportForm
            onSubmit={handleSubmit}
            loading={loading}
            selectedLocation={selectedLocation}
            onLocationChange={setSelectedLocation}
            categories={categories}
          />
        ) : (
          <div style={{ 
            padding: "2rem", 
            textAlign: "center", 
            color: "#94a3b8",
            background: "#f8fafc",
            borderRadius: "12px",
            border: "2px dashed #cbd5e1"
          }}>
            <p style={{ margin: 0 }}>🔒 Log in to submit a report</p>
          </div>
        )}
      </section>
      
      <div className="map-wrapper">
        {/* Filter bar above map */}
        <div className="filter-bar">
          <div className="filter-group">
            <label>Category:</label>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>
          
          <div className="filter-group">
            <label>Time Range:</label>
            <select
              value={timeRangeFilter}
              onChange={(e) => setTimeRangeFilter(e.target.value)}
            >
              <option value="">All Time</option>
              <option value="last_hour">Last Hour</option>
              <option value="last_24h">Last 24 Hours</option>
              <option value="yesterday">Yesterday</option>
              <option value="last_7_days">Last 7 Days</option>
              <option value="last_30_days">Last 30 Days</option>
            </select>
          </div>

          <div className="layer-controls">
            <div className="layer-control">
              <input
                type="checkbox"
                id="show-reports"
                checked={showReportsLayer}
                onChange={(e) => setShowReportsLayer(e.target.checked)}
              />
              <label htmlFor="show-reports" style={{ margin: 0, cursor: "pointer" }}>Reports</label>
            </div>
            <div className="layer-control">
              <input
                type="checkbox"
                id="show-hotspots"
                checked={showHotspotsLayer}
                onChange={(e) => setShowHotspotsLayer(e.target.checked)}
              />
              <label htmlFor="show-hotspots" style={{ margin: 0, cursor: "pointer" }}>Hotspots</label>
            </div>
          </div>
        </div>

        {hotspotsRefreshedNote && (
          <div style={{ position: "absolute", top: 10, left: "50%", transform: "translateX(-50%)", zIndex: 1000, padding: "0.5rem 1rem", background: "#059669", color: "white", borderRadius: "8px", fontSize: "0.875rem", fontWeight: 500, boxShadow: "0 4px 12px rgba(0,0,0,0.15)" }}>
            Hotspots updated
          </div>
        )}
        <div className="map-container">
          <MapView
            reports={reports}
            hotspots={hotspots}
            selectedLocation={selectedLocation}
            onMapClick={handleMapClick}
            showReportsLayer={showReportsLayer}
            showHotspotsLayer={showHotspotsLayer}
          />
        </div>
      </div>
    </main>
        } />
      </Routes>
    </>
  );
}

export default App;
