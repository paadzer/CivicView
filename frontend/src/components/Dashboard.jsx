// Analytics dashboard for council/admin: summary stats and charts
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  LineChart,
  Line,
  AreaChart,
  Area,
} from "recharts";

import { fetchAnalyticsDashboard, fetchAnalyticsSummary, fetchReports, regenerateHotspots, updateReport, fetchCounties, fetchConstituencies, fetchCountyComparison, fetchConstituencyComparison, fetchAssignableUsers, fetchNotifications, markNotificationRead } from "../api";

const COLORS = ["#2563eb", "#ea580c", "#059669", "#7c3aed", "#dc2626", "#ca8a04", "#0891b2", "#db2777", "#4b5563", "#65a30d"];

// Priority bands for traffic-light: high >= 20, medium >= 10, low < 10 (or null/undefined)
function getPriorityBand(score) {
  if (score == null || typeof score !== "number") return null;
  if (score >= 20) return "high";
  if (score >= 10) return "medium";
  return "low";
}
function getPriorityColor(score) {
  const band = getPriorityBand(score);
  if (band === "high") return "#dc2626";
  if (band === "medium") return "#d97706";
  if (band === "low") return "#16a34a";
  return "#94a3b8";
}

export default function Dashboard({ role, userId, onHotspotsRegenerated }) {
  const [summary, setSummary] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [managementReports, setManagementReports] = useState([]);
  const [visibleManagementCount, setVisibleManagementCount] = useState(10);
  const [assignableUsers, setAssignableUsers] = useState([]);
  const [assignedToMeOnly, setAssignedToMeOnly] = useState(false);
  const [createdByMeOnly, setCreatedByMeOnly] = useState(false);
  const [assignmentError, setAssignmentError] = useState(null);
  const [managementSortBy, setManagementSortBy] = useState("newest"); // newest | oldest | priority
  const [managementStatusFilter, setManagementStatusFilter] = useState(""); // "" | open | in_progress | resolved | dismissed
  const [managementPriorityFilter, setManagementPriorityFilter] = useState(""); // "" | high | medium | low
  const [labConfig, setLabConfig] = useState({ days_back: 30, eps_meters: 250, min_samples: 5 });
  const [labResult, setLabResult] = useState(null);
  const [labLoading, setLabLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("overview"); // "overview" | "management" | "geographic" | "lab" | "export"
  const [myAreaType, setMyAreaType] = useState(""); // "" | "county" | "constituency"
  const [myAreaId, setMyAreaId] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [exportCategory, setExportCategory] = useState("");
  const [exportPeriod, setExportPeriod] = useState("");
  
  // Geographic analysis state
  const [counties, setCounties] = useState([]);
  const [constituencies, setConstituencies] = useState([]);
  const [selectedCounties, setSelectedCounties] = useState([]);
  const [selectedConstituencies, setSelectedConstituencies] = useState([]);
  const [comparisonType, setComparisonType] = useState("county"); // "county" | "constituency"
  const [comparisonData, setComparisonData] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [boundariesLoading, setBoundariesLoading] = useState(false);
  const [boundariesError, setBoundariesError] = useState(null);

  const isDashboardUser = ["staff", "council", "manager", "admin"].includes(role);
  const isManagerOrAdmin = role === "manager" || role === "admin";

  useEffect(() => {
    if (!isDashboardUser) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = { ordering: "-created_at" };
    if (myAreaType === "county" && myAreaId) params.in_county = myAreaId;
    if (myAreaType === "constituency" && myAreaId) params.in_constituency = myAreaId;
    Promise.all([fetchAnalyticsSummary(), fetchAnalyticsDashboard(), fetchReports(params)])
      .then(([summaryRes, dashboardRes, reportsRes]) => {
        if (!cancelled) {
          setSummary(summaryRes.data);
          setDashboard(dashboardRes.data);
          setManagementReports(reportsRes.data || []);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.response?.status === 403 ? "Access denied. Staff, Manager or Admin role required." : "Failed to load analytics.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [isDashboardUser, myAreaType, myAreaId]);

  // Load notifications for dashboard user
  useEffect(() => {
    if (!isDashboardUser) return;
    let cancelled = false;
    fetchNotifications()
      .then((res) => { if (!cancelled) setNotifications(res.data || []); })
      .catch(() => { if (!cancelled) setNotifications([]); });
    return () => { cancelled = true; };
  }, [isDashboardUser, activeTab]);

  // Load assignable users when management tab is open (manager/admin only)
  useEffect(() => {
    if (!isManagerOrAdmin || activeTab !== "management") return;
    let cancelled = false;
    fetchAssignableUsers()
      .then((res) => { if (!cancelled) setAssignableUsers(res.data || []); })
      .catch(() => { if (!cancelled) setAssignableUsers([]); });
    return () => { cancelled = true; };
  }, [isManagerOrAdmin, activeTab]);

  // Load counties and constituencies when geographic or management tab is accessed (for geographic comparison and "My area" filter)
  useEffect(() => {
    if (!isDashboardUser || (activeTab !== "geographic" && activeTab !== "management")) return;
    let cancelled = false;
    setBoundariesLoading(true);
    setBoundariesError(null);
    Promise.all([fetchCounties({ minimal: 1 }), fetchConstituencies({ minimal: 1 })])
      .then(([countiesRes, constituenciesRes]) => {
        if (!cancelled) {
          setCounties(countiesRes.data || []);
          setConstituencies(constituenciesRes.data || []);
          setBoundariesError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load boundaries:", err);
          setBoundariesError(err.response?.data?.error || "Failed to load boundaries. Make sure boundaries have been imported.");
        }
      })
      .finally(() => {
        if (!cancelled) setBoundariesLoading(false);
      });
    return () => { cancelled = true; };
  }, [isDashboardUser, activeTab]);

  // Run comparison when selections change
  useEffect(() => {
    if (!isDashboardUser || activeTab !== "geographic") return;
    if (comparisonType === "county" && selectedCounties.length > 0) {
      setGeoLoading(true);
      fetchCountyComparison(selectedCounties)
        .then((res) => {
          setComparisonData(res.data);
        })
        .catch((err) => {
          console.error("Failed to fetch comparison:", err);
        })
        .finally(() => {
          setGeoLoading(false);
        });
    } else if (comparisonType === "constituency" && selectedConstituencies.length > 0) {
      setGeoLoading(true);
      fetchConstituencyComparison(selectedConstituencies)
        .then((res) => {
          setComparisonData(res.data);
        })
        .catch((err) => {
          console.error("Failed to fetch comparison:", err);
        })
        .finally(() => {
          setGeoLoading(false);
        });
    } else {
      setComparisonData(null);
    }
  }, [isDashboardUser, activeTab, comparisonType, selectedCounties, selectedConstituencies]);

  if (!isDashboardUser) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Analytics Dashboard</h1>
        <p style={{ color: "#dc2626" }}>Access denied. Staff, Manager or Admin role required.</p>
        <Link to="/">Back to map</Link>
      </div>
    );
  }

  if (loading) return <div style={{ padding: "2rem" }}>Loading analytics…</div>;
  if (error) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Analytics Dashboard</h1>
        <p style={{ color: "#dc2626" }}>{error}</p>
        <Link to="/">Back to map</Link>
      </div>
    );
  }

  const allCategories = Array.from(
    new Set((dashboard?.top_categories ?? []).map((c) => c.category))
  ).sort();

  return (
    <div style={{ 
      padding: "2rem", 
      maxWidth: "1400px", 
      margin: "0 auto",
      background: "#ffffff",
      minHeight: "calc(100vh - 70px)",
      borderRadius: "0"
    }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ 
          fontSize: "2rem", 
          fontWeight: 700, 
          margin: "0 0 0.5rem 0",
          color: "#0f172a",
          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text"
        }}>
          Analytics Dashboard
        </h1>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
          <Link 
            to="/" 
            style={{ 
              color: "#667eea", 
              textDecoration: "none",
              fontWeight: 500,
              fontSize: "0.95rem"
            }}
          >
            ← Back to map
          </Link>
          <div style={{ position: "relative" }}>
            <button
              type="button"
              onClick={() => {
                if (!notificationsOpen) {
                  fetchNotifications().then((res) => setNotifications(res.data || [])).catch(() => setNotifications([]));
                }
                setNotificationsOpen((o) => !o);
              }}
              style={{
                padding: "0.35rem 0.75rem",
                background: notifications.filter((n) => !n.read_at).length > 0 ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#f1f5f9",
                color: notifications.filter((n) => !n.read_at).length > 0 ? "white" : "#475569",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: "pointer"
              }}
            >
              Notifications {notifications.filter((n) => !n.read_at).length > 0 ? `(${notifications.filter((n) => !n.read_at).length})` : ""}
            </button>
            {notificationsOpen && (
              <div style={{ position: "absolute", top: "100%", left: 0, marginTop: "0.25rem", minWidth: 320, maxWidth: 400, maxHeight: 360, overflow: "auto", background: "white", border: "1px solid #e2e8f0", borderRadius: "8px", boxShadow: "0 10px 25px rgba(0,0,0,0.1)", zIndex: 50 }}>
                {(notifications || []).length === 0 ? (
                  <div style={{ padding: "1rem", color: "#64748b", fontSize: "0.875rem" }}>No notifications</div>
                ) : (
                  (notifications || []).map((n) => (
                    <div
                      key={n.id}
                      style={{
                        padding: "0.75rem 1rem",
                        borderBottom: "1px solid #f1f5f9",
                        background: n.read_at ? "white" : "#f8fafc",
                        fontSize: "0.875rem"
                      }}
                    >
                      <p style={{ margin: "0 0 0.25rem 0", color: "#0f172a" }}>{n.message}</p>
                      {n.report_title && <p style={{ margin: 0, color: "#64748b", fontSize: "0.8rem" }}>Report: {n.report_title}</p>}
                      <button
                        type="button"
                        onClick={() => {
                          markNotificationRead(n.id).then(() => {
                            setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
                          });
                        }}
                        style={{ marginTop: "0.35rem", background: "none", border: "none", color: "#667eea", cursor: "pointer", fontSize: "0.8rem", padding: 0 }}
                      >
                        {n.read_at ? "Read" : "Mark read"}
                      </button>
                    </div>
                  ))
                )}
                <button type="button" onClick={() => setNotificationsOpen(false)} style={{ display: "block", width: "100%", padding: "0.5rem", background: "#f1f5f9", border: "none", fontSize: "0.8rem", cursor: "pointer", borderBottomLeftRadius: "8px", borderBottomRightRadius: "8px" }}>Close</button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tabs for splitting content into two shorter pages */}
      <div style={{ marginBottom: "2rem", display: "flex", gap: "0.75rem" }}>
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 999,
            border: "2px solid " + (activeTab === "overview" ? "#667eea" : "#e5e7eb"),
            background: activeTab === "overview" ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#ffffff",
            color: activeTab === "overview" ? "#ffffff" : "#475569",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          Overview
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("management")}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 999,
            border: "2px solid " + (activeTab === "management" ? "#667eea" : "#e5e7eb"),
            background: activeTab === "management" ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#ffffff",
            color: activeTab === "management" ? "#ffffff" : "#475569",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          Workflow
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("lab")}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 999,
            border: "2px solid " + (activeTab === "lab" ? "#667eea" : "#e5e7eb"),
            background: activeTab === "lab" ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#ffffff",
            color: activeTab === "lab" ? "#ffffff" : "#475569",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          Hotspots lab
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("geographic")}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 999,
            border: "2px solid " + (activeTab === "geographic" ? "#667eea" : "#e5e7eb"),
            background: activeTab === "geographic" ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#ffffff",
            color: activeTab === "geographic" ? "#ffffff" : "#475569",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s"
          }}
        >
          Geographic Analysis
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("export")}
          style={{
            padding: "0.5rem 1.25rem",
            borderRadius: 999,
            border: "2px solid " + (activeTab === "export" ? "#667eea" : "#e5e7eb"),
            background: activeTab === "export" ? "linear-gradient(135deg, #667eea 0%, #764ba2 100%)" : "#ffffff",
            color: activeTab === "export" ? "#ffffff" : "#475569",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          Export CSV
        </button>
      </div>

      {activeTab === "overview" && (
        <>
          {/* Summary cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
            <div style={{ background: "#f8fafc", padding: "1.25rem", borderRadius: 10, border: "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)" }}>
              <div style={{ fontSize: "0.875rem", color: "#475569", fontWeight: 500, marginBottom: "0.5rem" }}>Total reports</div>
              <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a" }}>{summary?.total_reports ?? 0}</div>
            </div>
            <div style={{ background: "#f8fafc", padding: "1.25rem", borderRadius: 10, border: "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)" }}>
              <div style={{ fontSize: "0.875rem", color: "#475569", fontWeight: 500, marginBottom: "0.5rem" }}>Last 7 days</div>
              <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a" }}>{summary?.last_7_days ?? 0}</div>
            </div>
            <div style={{ background: "#f8fafc", padding: "1.25rem", borderRadius: 10, border: "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)" }}>
              <div style={{ fontSize: "0.875rem", color: "#475569", fontWeight: 500, marginBottom: "0.5rem" }}>Last 30 days</div>
              <div style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a" }}>{summary?.last_30_days ?? 0}</div>
            </div>
            <div style={{ background: "#f8fafc", padding: "1.25rem", borderRadius: 10, border: "1px solid #e2e8f0", boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)" }}>
              <div style={{ fontSize: "0.875rem", color: "#475569", fontWeight: 500, marginBottom: "0.5rem" }}>Average resolution time</div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a" }}>
                {summary?.average_resolution_time_days != null
                  ? `${summary.average_resolution_time_days.toFixed(1)} days`
                  : "—"}
              </div>
            </div>
          </div>

          {/* Status breakdown */}
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>Reports by status</h2>
            <div style={{ height: 260, background: "#f8fafc", padding: "1rem", borderRadius: 8 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary?.by_status ?? []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="status" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#059669" name="Reports" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

            {/* Reports per day (last 30 days) */}
            <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>Reports per day (last 30 days)</h2>
            <div style={{ height: 280, background: "#f8fafc", padding: "1rem", borderRadius: 8 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dashboard?.reports_per_day ?? []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} name="Reports" dot={{ fill: "#2563eb", r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Top categories + workflow status over time */}
          <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1.1fr)", gap: "1.5rem", alignItems: "stretch" }}>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>Top categories</h2>
              <div style={{ height: 320, background: "#f8fafc", padding: "1rem", borderRadius: 8 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={dashboard?.top_categories ?? []}
                      dataKey="count"
                      nameKey="category"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={({ category, count }) => `${category}: ${count}`}
                    >
                      {(dashboard?.top_categories ?? []).map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>Status over time</h2>
              <div style={{ height: 320, background: "#f8fafc", padding: "1rem", borderRadius: 8 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={dashboard?.reports_by_status_per_day ?? []} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="open" stackId="status" fill="#2563eb" name="Open" />
                    <Bar dataKey="in_progress" stackId="status" fill="#ca8a04" name="In progress" />
                    <Bar dataKey="resolved" stackId="status" fill="#16a34a" name="Resolved" />
                    <Bar dataKey="dismissed" stackId="status" fill="#dc2626" name="Dismissed" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === "management" && (
        <>
          {/* Workflow management */}
          <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem", color: "#0f172a" }}>
              Recent reports (workflow management)
            </h2>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.75rem", lineHeight: "1.5" }}>
              Change status, assign reports, and see priority scores. Staff and above can update workflow; only managers and admins can assign reports to others.
            </p>
            {userId != null && (
              <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem", color: "#475569", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={assignedToMeOnly}
                    onChange={(e) => setAssignedToMeOnly(e.target.checked)}
                    style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "#667eea" }}
                  />
                  Assigned to me only
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem", color: "#475569", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={createdByMeOnly}
                    onChange={(e) => setCreatedByMeOnly(e.target.checked)}
                    style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "#667eea" }}
                  />
                  Created by me only
                </label>
              </div>
            )}
            <label style={{ fontSize: "0.9rem", color: "#475569", display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
              My area
              <select
                value={myAreaType && myAreaId ? `${myAreaType}-${myAreaId}` : ""}
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) {
                    setMyAreaType("");
                    setMyAreaId(null);
                    return;
                  }
                  const [t, id] = v.split("-");
                  setMyAreaType(t || "");
                  setMyAreaId(id ? parseInt(id, 10) : null);
                }}
                style={{ padding: "0.35rem 0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.875rem", background: "white", minWidth: 180 }}
              >
                <option value="">All areas</option>
                {counties?.length > 0 && (
                  <optgroup label="Counties">
                    {counties.map((c) => (
                      <option key={`county-${c.id}`} value={`county-${c.id}`}>{c.name}</option>
                    ))}
                  </optgroup>
                )}
                {constituencies?.length > 0 && (
                  <optgroup label="Constituencies">
                    {constituencies.map((c) => (
                      <option key={`constituency-${c.id}`} value={`constituency-${c.id}`}>{c.name}</option>
                    ))}
                  </optgroup>
                )}
              </select>
            </label>
            {assignmentError && (
              <div style={{ padding: "0.5rem 0.75rem", marginBottom: "0.5rem", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "6px", fontSize: "0.875rem", color: "#b91c1c" }}>
                {typeof assignmentError === "string" ? assignmentError : (assignmentError.assigned_to ? (Array.isArray(assignmentError.assigned_to) ? assignmentError.assigned_to.join(" ") : assignmentError.assigned_to) : "Assignment failed.")}
                <button type="button" onClick={() => setAssignmentError(null)} style={{ marginLeft: "0.5rem", background: "none", border: "none", color: "#b91c1c", cursor: "pointer", textDecoration: "underline" }}>Dismiss</button>
              </div>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0.75rem", marginBottom: "0.75rem" }}>
              <label style={{ fontSize: "0.875rem", color: "#475569", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                Sort by
                <select
                  value={managementSortBy}
                  onChange={(e) => setManagementSortBy(e.target.value)}
                  style={{ padding: "0.35rem 0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.875rem", background: "white" }}
                >
                  <option value="newest">Newest first</option>
                  <option value="oldest">Oldest first</option>
                  <option value="priority">Priority (high first)</option>
                </select>
              </label>
              <label style={{ fontSize: "0.875rem", color: "#475569", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                Status
                <select
                  value={managementStatusFilter}
                  onChange={(e) => setManagementStatusFilter(e.target.value)}
                  style={{ padding: "0.35rem 0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.875rem", background: "white" }}
                >
                  <option value="">All</option>
                  <option value="open">Open</option>
                  <option value="in_progress">In progress</option>
                  <option value="resolved">Resolved</option>
                  <option value="dismissed">Dismissed</option>
                </select>
              </label>
              <label style={{ fontSize: "0.875rem", color: "#475569", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                Priority
                <select
                  value={managementPriorityFilter}
                  onChange={(e) => setManagementPriorityFilter(e.target.value)}
                  style={{ padding: "0.35rem 0.6rem", border: "1px solid #cbd5e1", borderRadius: "6px", fontSize: "0.875rem", background: "white" }}
                >
                  <option value="">All</option>
                  <option value="high">High (≥20)</option>
                  <option value="medium">Medium (10–19)</option>
                  <option value="low">Low (&lt;10)</option>
                </select>
              </label>
            </div>
            <div style={{ overflowX: "auto", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
              {(() => {
                const baseFiltered = (managementReports ?? []).filter((r) => {
                  if (!assignedToMeOnly && !createdByMeOnly) return true;
                  if (userId == null) return true;
                  const assigned = assignedToMeOnly && r.assigned_to === userId;
                  const created = createdByMeOnly && r.created_by === userId;
                  return assigned || created;
                });
                const statusFiltered = managementStatusFilter
                  ? baseFiltered.filter((r) => r.status === managementStatusFilter)
                  : baseFiltered;
                const priorityFiltered = managementPriorityFilter
                  ? statusFiltered.filter((r) => getPriorityBand(r.priority_score) === managementPriorityFilter)
                  : statusFiltered;
                const sorted =
                  managementSortBy === "oldest"
                    ? [...priorityFiltered].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
                    : managementSortBy === "priority"
                    ? [...priorityFiltered].sort((a, b) => (b.priority_score ?? -1) - (a.priority_score ?? -1))
                    : [...priorityFiltered].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
                const filteredManagementReports = sorted;
                const visibleReports = filteredManagementReports.slice(0, visibleManagementCount);
                return (
                  <>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
                <thead>
                  <tr style={{ background: "#e5e7eb" }}>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Title</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Category</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Status</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Assigned to</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Target date</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Created</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Priority</th>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Valid?</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleReports.map((r) => (
                    <tr key={r.id} style={{ borderTop: "1px solid #e5e7eb", background: "white" }}>
                      <td style={{ padding: "0.75rem", fontSize: 13, maxWidth: 220, whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden", color: "#0f172a" }}>
                        {r.title}
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13, color: "#475569" }}>{r.category}</td>
                      <td style={{ padding: "0.5rem 0.75rem", fontSize: 13 }}>
                        <select
                          value={r.status}
                          onChange={async (e) => {
                            const newStatus = e.target.value;
                            try {
                              await updateReport(r.id, { status: newStatus });
                              setManagementReports((prev) =>
                                prev.map((item) =>
                                  item.id === r.id ? { ...item, status: newStatus, status_display: undefined } : item
                                )
                              );
                            } catch {
                              // Ignore errors here; overall error banner will show if needed
                            }
                          }}
                          style={{
                            padding: "0.4rem 0.6rem",
                            border: "1px solid #cbd5e1",
                            borderRadius: "6px",
                            fontSize: "0.875rem",
                            background: "white",
                            color: "#0f172a",
                            cursor: "pointer"
                          }}
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In progress</option>
                          <option value="resolved">Resolved</option>
                          <option value="dismissed">Dismissed</option>
                        </select>
                      </td>
                      <td style={{ padding: "0.5rem 0.75rem", fontSize: 13 }}>
                        {isManagerOrAdmin ? (
                          <select
                            value={r.assigned_to != null ? String(r.assigned_to) : ""}
                            onChange={async (e) => {
                              const raw = e.target.value;
                              const newId = raw === "" ? null : parseInt(raw, 10);
                              setAssignmentError(null);
                              try {
                                const res = await updateReport(r.id, { assigned_to: newId });
                                const updated = res?.data;
                                const username = updated?.assigned_to_username ?? (newId == null ? null : (assignableUsers.find((u) => u.id === newId)?.username ?? null));
                                const assignedId = updated?.assigned_to ?? newId;
                                setManagementReports((prev) =>
                                  prev.map((item) =>
                                    item.id === r.id
                                      ? { ...item, assigned_to: assignedId, assigned_to_username: username }
                                      : item
                                  )
                                );
                              } catch (err) {
                                const data = err.response?.data;
                                setAssignmentError(data?.assigned_to ?? data?.detail ?? (typeof data === "string" ? data : "Failed to update assignment."));
                              }
                            }}
                            style={{
                              padding: "0.4rem 0.6rem",
                              border: "1px solid #cbd5e1",
                              borderRadius: "6px",
                              fontSize: "0.875rem",
                              background: "white",
                              color: "#0f172a",
                              cursor: "pointer",
                              minWidth: 140
                            }}
                          >
                            <option value="">Unassigned</option>
                            {(assignableUsers || []).map((u) => (
                              <option key={u.id} value={String(u.id)}>{u.username} ({u.role})</option>
                            ))}
                          </select>
                        ) : (
                          <span style={{ color: "#475569" }}>{r.assigned_to_username || "Unassigned"}</span>
                        )}
                      </td>
                      <td style={{ padding: "0.5rem 0.75rem", fontSize: 13 }}>
                        <input
                          type="date"
                          value={r.target_resolution_date || ""}
                          onChange={async (e) => {
                            const value = e.target.value || null;
                            try {
                              await updateReport(r.id, { target_resolution_date: value });
                              setManagementReports((prev) =>
                                prev.map((item) =>
                                  item.id === r.id ? { ...item, target_resolution_date: value } : item
                                )
                              );
                            } catch {
                              // ignore
                            }
                          }}
                          style={{
                            padding: "0.4rem 0.6rem",
                            border: "1px solid #cbd5e1",
                            borderRadius: "6px",
                            fontSize: "0.875rem",
                            background: "white",
                            color: "#0f172a"
                          }}
                        />
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13, color: "#475569" }}>
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13, color: "#0f172a", fontWeight: 600 }}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}>
                          {r.priority_score != null && (
                            <span
                              style={{
                                width: 10,
                                height: 10,
                                borderRadius: "50%",
                                background: getPriorityColor(r.priority_score),
                                flexShrink: 0
                              }}
                              title={getPriorityBand(r.priority_score) ? `Priority: ${getPriorityBand(r.priority_score)}` : ""}
                            />
                          )}
                          {r.priority_score != null ? r.priority_score.toFixed(1) : "—"}
                        </span>
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13 }}>
                        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer", color: "#475569" }}>
                          <input
                            type="checkbox"
                            checked={r.is_valid !== false}
                            onChange={async (e) => {
                              const newVal = e.target.checked;
                              try {
                                await updateReport(r.id, { is_valid: newVal });
                                setManagementReports((prev) =>
                                  prev.map((item) =>
                                    item.id === r.id ? { ...item, is_valid: newVal } : item
                                  )
                                );
                              } catch {
                                // ignore errors, backend enforces permissions
                              }
                            }}
                            style={{ width: "18px", height: "18px", cursor: "pointer", accentColor: "#667eea" }}
                          />
                          <span style={{ fontWeight: 500 }}>{r.is_valid !== false ? "Valid" : "Invalid"}</span>
                        </label>
                      </td>
                    </tr>
                  ))}
                  {filteredManagementReports.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ padding: "0.75rem", fontSize: 13, color: "#6b7280" }}>
                        {managementReports.length === 0 ? "No reports available yet." : "No reports match your filters."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              {filteredManagementReports.length > 0 && (
                <div style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  background: "#f8fafc",
                  borderRadius: "8px"
                }}>
                  <span style={{ fontSize: 13, color: "#475569", marginRight: "auto", fontWeight: 500 }}>
                    Showing {Math.min(visibleManagementCount, filteredManagementReports.length)} of {filteredManagementReports.length} reports
                  </span>
                  {visibleManagementCount > 10 && (
                    <button
                      type="button"
                      style={{
                        fontSize: 13,
                        padding: "0.4rem 0.8rem",
                        background: "white",
                        border: "1px solid #cbd5e1",
                        borderRadius: "6px",
                        color: "#475569",
                        cursor: "pointer",
                        fontWeight: 500
                      }}
                      onClick={() => setVisibleManagementCount(10)}
                    >
                      Show first 10
                    </button>
                  )}
                  {visibleManagementCount < filteredManagementReports.length && (
                    <button
                      type="button"
                      style={{
                        fontSize: 13,
                        padding: "0.4rem 0.8rem",
                        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                        border: "none",
                        borderRadius: "6px",
                        color: "white",
                        cursor: "pointer",
                        fontWeight: 500
                      }}
                      onClick={() =>
                        setVisibleManagementCount((prev) =>
                          Math.min(prev + 10, filteredManagementReports.length)
                        )
                      }
                    >
                      Show more
                    </button>
                  )}
                </div>
              )}
                </>
                );
              })()}
            </div>
          </div>

          {/* Reporter quality table */}
          <div style={{ marginTop: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem", color: "#0f172a" }}>
              Reporter quality
            </h2>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.75rem", lineHeight: "1.5" }}>
              Overview of top reporters, resolution performance, and invalid report rates. Trusted reporters have at least 3 reports and low invalid rates.
            </p>
            <div style={{ overflowX: "auto", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 720 }}>
                <thead>
                  <tr style={{ background: "#e5e7eb" }}>
                    <th style={{ textAlign: "left", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>User</th>
                    <th style={{ textAlign: "right", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Total</th>
                    <th style={{ textAlign: "right", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Resolved</th>
                    <th style={{ textAlign: "right", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Invalid</th>
                    <th style={{ textAlign: "right", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Resolution rate</th>
                    <th style={{ textAlign: "right", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Invalid rate</th>
                    <th style={{ textAlign: "center", padding: "0.75rem", fontSize: 13, fontWeight: 600, color: "#0f172a" }}>Trusted?</th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.reporter_stats ?? []).map((u, idx) => (
                    <tr key={u.username + idx} style={{ borderTop: "1px solid #e5e7eb", background: "white" }}>
                      <td style={{ padding: "0.75rem", fontSize: 13, color: "#0f172a", fontWeight: 500 }}>{u.username}</td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "right", color: "#475569" }}>{u.total_reports}</td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "right", color: "#475569" }}>{u.resolved_reports}</td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "right", color: "#475569" }}>{u.invalid_reports}</td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "right", color: "#0f172a", fontWeight: 500 }}>
                        {(u.resolution_rate * 100).toFixed(0)}%
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "right", color: "#0f172a", fontWeight: 500 }}>
                        {(u.invalid_rate * 100).toFixed(0)}%
                      </td>
                      <td style={{ padding: "0.75rem", fontSize: 13, textAlign: "center", color: "#0f172a", fontWeight: 600 }}>
                        {u.trusted ? "Yes" : "No"}
                      </td>
                    </tr>
                  ))}
                  {(summary?.reporter_stats ?? []).length === 0 && (
                    <tr>
                      <td colSpan={7} style={{ padding: "0.75rem", fontSize: 13, color: "#6b7280" }}>
                        No reporter statistics available yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {activeTab === "lab" && (
        <>
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.5rem", color: "#0f172a" }}>
              Hotspot clustering lab
            </h2>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.75rem", lineHeight: "1.5" }}>
              Experiment with different DBSCAN parameters and see how many hotspots and noise points are produced.
              This calls the <code style={{ 
                background: "#f1f5f9", 
                padding: "0.2rem 0.4rem", 
                borderRadius: "4px",
                fontSize: "0.85rem",
                color: "#667eea",
                fontFamily: "monospace"
              }}>/api/hotspots/regenerate/</code> endpoint and replaces current hotspots.
            </p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setLabLoading(true);
                setLabResult(null);
                try {
                  const params = {
                    days_back: labConfig.days_back,
                    eps: labConfig.eps_meters,
                    min_samples: labConfig.min_samples,
                  };
                  const res = await regenerateHotspots(params);
                  setLabResult(res.data);
                  onHotspotsRegenerated?.();
                } catch {
                  setLabResult({ error: "Failed to regenerate hotspots. Check backend logs." });
                } finally {
                  setLabLoading(false);
                }
              }}
              style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "flex-end", marginBottom: "1rem", padding: "1rem", background: "#f8fafc", borderRadius: "10px" }}
            >
              <label style={{ fontSize: 13, fontWeight: 500, color: "#334155", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                Days back
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={labConfig.days_back}
                  onChange={(e) =>
                    setLabConfig((prev) => ({ ...prev, days_back: Number(e.target.value) || 30 }))
                  }
                  style={{ 
                    padding: "0.5rem 0.75rem",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    background: "white",
                    color: "#0f172a",
                    width: "100px"
                  }}
                />
              </label>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#334155", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                Eps (meters)
                <input
                  type="number"
                  min="50"
                  max="2000"
                  step="10"
                  value={labConfig.eps_meters}
                  onChange={(e) =>
                    setLabConfig((prev) => ({ ...prev, eps_meters: Number(e.target.value) || 250 }))
                  }
                  style={{ 
                    padding: "0.5rem 0.75rem",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    background: "white",
                    color: "#0f172a",
                    width: "100px"
                  }}
                />
              </label>
              <label style={{ fontSize: 13, fontWeight: 500, color: "#334155", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                Min samples
                <input
                  type="number"
                  min="2"
                  max="50"
                  value={labConfig.min_samples}
                  onChange={(e) =>
                    setLabConfig((prev) => ({ ...prev, min_samples: Number(e.target.value) || 5 }))
                  }
                  style={{ 
                    padding: "0.5rem 0.75rem",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    background: "white",
                    color: "#0f172a",
                    width: "100px"
                  }}
                />
              </label>
              <button
                type="submit"
                disabled={labLoading}
                style={{ 
                  padding: "0.5rem 1.25rem", 
                  fontSize: 14,
                  fontWeight: 600,
                  background: labLoading ? "#94a3b8" : "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: labLoading ? "not-allowed" : "pointer",
                  boxShadow: labLoading ? "none" : "0 4px 15px rgba(102, 126, 234, 0.4)"
                }}
              >
                {labLoading ? "Running…" : "Run clustering"}
              </button>
            </form>

            {labResult && (
              <div style={{ background: "#f8fafc", borderRadius: 10, border: "1px solid #e2e8f0", padding: "1rem 1.25rem" }}>
                <h3 style={{ fontSize: 15, marginBottom: "0.75rem", fontWeight: 600, color: "#0f172a" }}>Last run results</h3>
                {!labResult.error && (
                  <p style={{ fontSize: 12, color: "#059669", marginBottom: "0.75rem" }}>
                    Map data updated. <Link to="/" state={{ hotspotsRefreshed: true }} style={{ color: "#059669", fontWeight: 600, textDecoration: "underline" }}>View map</Link> to see the new hotspots.
                  </p>
                )}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "1.5rem", fontSize: 13 }}>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Hotspots created</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.hotspots_created ?? "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Clusters found</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.clusters_found ?? "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Total reports</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.total_reports ?? "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Noise points</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.noise_points ?? "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Eps (m)</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.eps_meters ?? labConfig.eps_meters}</div>
                  </div>
                  <div>
                    <div style={{ color: "#475569", fontSize: "0.8rem", marginBottom: "0.25rem" }}>Min samples</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", color: "#0f172a" }}>{labResult.min_samples ?? labConfig.min_samples}</div>
                  </div>
                </div>
                {labResult.error && (
                  <div style={{ marginTop: "0.75rem", padding: "0.75rem", background: "#fee2e2", borderRadius: "6px", border: "1px solid #fecaca" }}>
                    <p style={{ margin: 0, color: "#dc2626", fontSize: "0.875rem" }}>{labResult.error}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {activeTab === "geographic" && (
        <>
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>
              Geographic Comparison
            </h2>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "1rem", lineHeight: "1.5" }}>
              Compare reports across counties or Dáil constituencies. Select areas below to see detailed statistics.
            </p>

            {/* Comparison type selector */}
            <div style={{ marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
              <label style={{ fontSize: 14, fontWeight: 600, color: "#0f172a" }}>Compare by:</label>
              <select
                value={comparisonType}
                onChange={(e) => {
                  setComparisonType(e.target.value);
                  setSelectedCounties([]);
                  setSelectedConstituencies([]);
                  setComparisonData(null);
                }}
                style={{
                  padding: "0.5rem 1rem",
                  borderRadius: "6px",
                  border: "1px solid #cbd5e1",
                  fontSize: 14,
                  background: "white",
                  color: "#0f172a",
                  cursor: "pointer"
                }}
              >
                <option value="county">County</option>
                <option value="constituency">Dáil Constituency</option>
              </select>
            </div>

            {/* Loading state for boundaries */}
            {boundariesLoading && (
              <div style={{ padding: "2rem", textAlign: "center", color: "#475569" }}>
                Loading boundaries...
              </div>
            )}

            {/* Error state for boundaries */}
            {boundariesError && (
              <div style={{ 
                padding: "1rem", 
                background: "#fee2e2", 
                borderRadius: "8px", 
                border: "1px solid #fecaca",
                marginBottom: "1.5rem"
              }}>
                <p style={{ margin: 0, color: "#dc2626", fontSize: "0.875rem" }}>
                  {boundariesError}
                </p>
                <p style={{ margin: "0.5rem 0 0 0", color: "#991b1b", fontSize: "0.8rem" }}>
                  To import boundaries, run: <code style={{ background: "#fecaca", padding: "0.2rem 0.4rem", borderRadius: "3px" }}>python manage.py import_boundaries</code>
                </p>
              </div>
            )}

            {/* County/Constituency selectors */}
            {!boundariesLoading && !boundariesError && (
              <>
                {comparisonType === "county" ? (
                  <div style={{ marginBottom: "1.5rem" }}>
                    <label style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", display: "block", marginBottom: "0.5rem" }}>
                      Select counties to compare:
                    </label>
                    {counties.length === 0 ? (
                      <div style={{ padding: "1.5rem", textAlign: "center", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                        <p style={{ margin: 0, color: "#475569", fontSize: "0.875rem" }}>
                          No counties found. Please import boundaries first.
                        </p>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                        {counties.map((county) => (
                          <label
                            key={county.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              padding: "0.5rem 0.75rem",
                              borderRadius: "6px",
                              border: selectedCounties.includes(county.name) ? "2px solid #667eea" : "1px solid #cbd5e1",
                              background: selectedCounties.includes(county.name) ? "#eef2ff" : "white",
                              cursor: "pointer",
                              fontSize: 13,
                              color: "#0f172a"
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selectedCounties.includes(county.name)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedCounties([...selectedCounties, county.name]);
                                } else {
                                  setSelectedCounties(selectedCounties.filter((n) => n !== county.name));
                                }
                              }}
                              style={{ marginRight: "0.5rem", cursor: "pointer" }}
                            />
                            {county.name} ({county.report_count || 0})
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ marginBottom: "1.5rem" }}>
                    <label style={{ fontSize: 14, fontWeight: 600, color: "#0f172a", display: "block", marginBottom: "0.5rem" }}>
                      Select constituencies to compare:
                    </label>
                    {constituencies.length === 0 ? (
                      <div style={{ padding: "1.5rem", textAlign: "center", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                        <p style={{ margin: 0, color: "#475569", fontSize: "0.875rem" }}>
                          No constituencies found. Please import boundaries first.
                        </p>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", maxHeight: "300px", overflowY: "auto", padding: "0.5rem", border: "1px solid #e2e8f0", borderRadius: "8px", background: "#f8fafc" }}>
                        {constituencies.map((constituency) => (
                          <label
                            key={constituency.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              padding: "0.5rem 0.75rem",
                              borderRadius: "6px",
                              border: selectedConstituencies.includes(constituency.name) ? "2px solid #667eea" : "1px solid #cbd5e1",
                              background: selectedConstituencies.includes(constituency.name) ? "#eef2ff" : "white",
                              cursor: "pointer",
                              fontSize: 13,
                              color: "#0f172a",
                              whiteSpace: "nowrap"
                            }}
                          >
                            <input
                              type="checkbox"
                              checked={selectedConstituencies.includes(constituency.name)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedConstituencies([...selectedConstituencies, constituency.name]);
                                } else {
                                  setSelectedConstituencies(selectedConstituencies.filter((n) => n !== constituency.name));
                                }
                              }}
                              style={{ marginRight: "0.5rem", cursor: "pointer" }}
                            />
                            {constituency.name} ({constituency.report_count || 0})
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}

            {/* Comparison results */}
            {geoLoading && (
              <div style={{ padding: "2rem", textAlign: "center", color: "#475569" }}>Loading comparison...</div>
            )}

            {comparisonData && comparisonData.comparison && comparisonData.comparison.length > 0 && (
              <div style={{ marginTop: "2rem" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "1rem", color: "#0f172a" }}>
                  Comparison Results
                </h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
                  {comparisonData.comparison.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: "#f8fafc",
                        padding: "1.25rem",
                        borderRadius: "10px",
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)"
                      }}
                    >
                      <h4 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.75rem", color: "#0f172a" }}>
                        {item.name}
                      </h4>
                      {item.error ? (
                        <p style={{ color: "#dc2626", fontSize: "0.875rem" }}>{item.error}</p>
                      ) : (
                        <>
                          <div style={{ marginBottom: "0.75rem" }}>
                            <div style={{ fontSize: "0.875rem", color: "#475569", marginBottom: "0.25rem" }}>Total Reports</div>
                            <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a" }}>
                              {item.total_reports || 0}
                            </div>
                          </div>
                          {item.average_resolution_time_days != null && (
                            <div style={{ marginBottom: "0.75rem" }}>
                              <div style={{ fontSize: "0.875rem", color: "#475569", marginBottom: "0.25rem" }}>
                                Avg Resolution Time
                              </div>
                              <div style={{ fontSize: "1.1rem", fontWeight: 600, color: "#0f172a" }}>
                                {item.average_resolution_time_days.toFixed(1)} days
                              </div>
                            </div>
                          )}
                          {item.by_status && item.by_status.length > 0 && (
                            <div style={{ marginBottom: "0.75rem" }}>
                              <div style={{ fontSize: "0.875rem", color: "#475569", marginBottom: "0.5rem" }}>By Status</div>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                                {item.by_status.map((status, sIdx) => (
                                  <div
                                    key={sIdx}
                                    style={{
                                      padding: "0.25rem 0.5rem",
                                      background: "#e2e8f0",
                                      borderRadius: "4px",
                                      fontSize: "0.75rem",
                                      color: "#0f172a"
                                    }}
                                  >
                                    {status.status}: {status.count}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {item.top_categories && item.top_categories.length > 0 && (
                            <div>
                              <div style={{ fontSize: "0.875rem", color: "#475569", marginBottom: "0.5rem" }}>Top Categories</div>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                                {item.top_categories.map((cat, cIdx) => (
                                  <div
                                    key={cIdx}
                                    style={{
                                      padding: "0.25rem 0.5rem",
                                      background: "#dbeafe",
                                      borderRadius: "4px",
                                      fontSize: "0.75rem",
                                      color: "#0f172a"
                                    }}
                                  >
                                    {cat.category}: {cat.count}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

                {/* Comparison Charts */}
                {comparisonData && comparisonData.comparison && comparisonData.comparison.length > 0 && (
                  <div style={{ marginTop: "2rem" }}>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "1rem", color: "#0f172a" }}>
                      Trend Comparison
                    </h3>
                    <div style={{ height: 300, background: "#f8fafc", padding: "1rem", borderRadius: 8, marginBottom: "1.5rem" }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart 
                          data={(() => {
                            // Combine all time-series data into a single dataset
                            const dateMap = {};
                            comparisonData.comparison.forEach((item) => {
                              if (item.reports_over_time) {
                                item.reports_over_time.forEach((point) => {
                                  if (!dateMap[point.date]) {
                                    dateMap[point.date] = { date: point.date };
                                  }
                                  dateMap[point.date][item.name] = point.count;
                                });
                              }
                            });
                            return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
                          })()}
                          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Legend />
                          {comparisonData.comparison.map((item, idx) => {
                            if (!item.reports_over_time) return null;
                            return (
                              <Line
                                key={idx}
                                type="monotone"
                                dataKey={item.name}
                                name={item.name}
                                stroke={COLORS[idx % COLORS.length]}
                                strokeWidth={2}
                                dot={{ r: 3 }}
                              />
                            );
                          })}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Category Comparison */}
                    <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "1rem", color: "#0f172a" }}>
                      Category Breakdown Comparison
                    </h3>
                    <div style={{ display: "grid", gridTemplateColumns: `repeat(${comparisonData.comparison.length}, 1fr)`, gap: "1rem" }}>
                      {comparisonData.comparison.map((item, idx) => (
                        <div key={idx} style={{ height: 300, background: "#f8fafc", padding: "1rem", borderRadius: 8 }}>
                          <h4 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.5rem", color: "#0f172a", textAlign: "center" }}>
                            {item.name}
                          </h4>
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={item.top_categories || []} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                              <XAxis dataKey="category" tick={{ fontSize: 9 }} angle={-45} textAnchor="end" height={60} />
                              <YAxis tick={{ fontSize: 10 }} />
                              <Tooltip />
                              <Bar dataKey="count" fill={COLORS[idx % COLORS.length]} radius={[4, 4, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
          </div>
        </>
      )}

      {activeTab === "export" && (
        <>
          <div style={{ marginBottom: "2rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: 600, marginBottom: "0.75rem", color: "#0f172a" }}>
              Export reports to CSV
            </h2>
            <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "1rem", lineHeight: "1.5" }}>
              Choose optional filters and then download a CSV of reports directly from the backend.
            </p>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "1rem",
                alignItems: "flex-end",
                background: "#f8fafc",
                borderRadius: "10px",
                border: "1px solid #e2e8f0",
                padding: "1rem 1.25rem",
                marginBottom: "1.5rem",
              }}
            >
              {/* Category filter */}
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#334155",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.4rem",
                  minWidth: 200,
                }}
              >
                Category
                <select
                  value={exportCategory}
                  onChange={(e) => setExportCategory(e.target.value)}
                  style={{
                    padding: "0.5rem 0.75rem",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    background: "white",
                    color: "#0f172a",
                  }}
                >
                  <option value="">All categories</option>
                  {allCategories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
              </label>

              {/* Period filter */}
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#334155",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.4rem",
                  minWidth: 200,
                }}
              >
                Time period
                <select
                  value={exportPeriod}
                  onChange={(e) => setExportPeriod(e.target.value)}
                  style={{
                    padding: "0.5rem 0.75rem",
                    border: "1px solid #cbd5e1",
                    borderRadius: "6px",
                    fontSize: "0.875rem",
                    background: "white",
                    color: "#0f172a",
                  }}
                >
                  <option value="">All time</option>
                  <option value="last_hour">Last hour</option>
                  <option value="last_24h">Last 24 hours</option>
                  <option value="yesterday">Yesterday</option>
                  <option value="last_7_days">Last 7 days</option>
                  <option value="last_30_days">Last 30 days</option>
                </select>
              </label>

              {/* Download button */}
              <div style={{ marginLeft: "auto" }}>
                {(() => {
                  const params = [];
                  if (exportCategory) params.push(`category=${encodeURIComponent(exportCategory)}`);
                  if (exportPeriod) params.push(`period=${exportPeriod}`);
                  const query = params.length ? `?${params.join("&")}` : "";
                  const href = `https://civicview-production.up.railway.app/api/reports/export/${query}`;
                  return (
                    <a
                      href={href}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        padding: "0.6rem 1.4rem",
                        borderRadius: "999px",
                        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                        color: "white",
                        fontSize: 14,
                        fontWeight: 600,
                        textDecoration: "none",
                        boxShadow: "0 4px 15px rgba(102, 126, 234, 0.45)",
                      }}
                    >
                      Download CSV
                    </a>
                  );
                })()}
              </div>
            </div>

            <p style={{ fontSize: "0.8rem", color: "#64748b" }}>
              The CSV is generated by the backend at{" "}
              <code
                style={{
                  background: "#f1f5f9",
                  padding: "0.2rem 0.4rem",
                  borderRadius: "4px",
                  fontFamily: "monospace",
                }}
              >
                /api/reports/export/
              </code>{" "}
              and uses the same filters as the main reports API (category and period).
            </p>
          </div>
        </>
      )}
    </div>
  );
}
