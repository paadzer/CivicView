import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  fetchAnalyticsAdvanced,
  fetchAnalyticsDashboard,
  fetchConstituencies,
  fetchCounties,
  fetchCouncils,
  fetchGeographicReports,
} from "../api";

const COLORS = {
  open: "#2563eb",
  in_progress: "#ca8a04",
  resolved: "#16a34a",
  dismissed: "#dc2626",
};

const cardStyle = {
  background: "#f8fafc",
  padding: "1.25rem",
  borderRadius: 10,
  border: "1px solid #e2e8f0",
  boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)",
};

const sectionTitle = {
  fontSize: "1.15rem",
  fontWeight: 600,
  marginBottom: "0.75rem",
  color: "#0f172a",
};

export default function AdvancedAnalyticsWrapper({ role }) {
  const isDashboardUser = ["staff", "council", "manager", "admin"].includes(role);
  const [advanced, setAdvanced] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [geoType, setGeoType] = useState("county");
  const [geoOptions, setGeoOptions] = useState([]);
  const [geoName, setGeoName] = useState("");
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoInsight, setGeoInsight] = useState(null);

  useEffect(() => {
    if (!isDashboardUser) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([fetchAnalyticsAdvanced(), fetchAnalyticsDashboard()])
      .then(([advRes, dashRes]) => {
        if (!cancelled) {
          setAdvanced(advRes.data);
          setDashboard(dashRes.data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err.response?.status === 403
              ? "Access denied."
              : "Failed to load advanced analytics."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isDashboardUser]);

  useEffect(() => {
    if (!isDashboardUser) return;
    let cancelled = false;
    const loader =
      geoType === "county"
        ? fetchCounties({ minimal: 1 })
        : geoType === "constituency"
          ? fetchConstituencies({ minimal: 1 })
          : fetchCouncils({ minimal: 1 });
    loader
      .then((res) => {
        if (!cancelled) setGeoOptions(res.data || []);
      })
      .catch(() => {
        if (!cancelled) setGeoOptions([]);
      });
    setGeoName("");
    setGeoInsight(null);
    return () => {
      cancelled = true;
    };
  }, [isDashboardUser, geoType]);

  const topCategoriesForStack = useMemo(() => {
    const rows = advanced?.category_by_status ?? [];
    return rows.slice(0, 12);
  }, [advanced]);

  const runGeoInsight = async () => {
    if (!geoName.trim()) return;
    setGeoLoading(true);
    setGeoInsight(null);
    try {
      const res = await fetchGeographicReports(geoType, geoName.trim());
      setGeoInsight(res.data);
    } catch (e) {
      setGeoInsight({
        error: e.response?.data?.error || "Could not load area reports.",
      });
    } finally {
      setGeoLoading(false);
    }
  };

  if (!isDashboardUser) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Advanced Analytics</h1>
        <p style={{ color: "#dc2626" }}>
          Access denied. Staff, Council, Manager or Admin role required.
        </p>
        <Link to="/">Back to map</Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div style={{ padding: "2rem" }}>
        <p>Loading advanced analytics…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1>Advanced Analytics</h1>
        <p style={{ color: "#dc2626" }}>{error}</p>
        <Link to="/">Back to map</Link>
      </div>
    );
  }

  const hs = advanced?.hotspot_summary;

  return (
    <div style={{ padding: "2rem", maxWidth: 1400, margin: "0 auto", minHeight: "calc(100vh - 70px)" }}>
      <div
        style={{
          marginBottom: "1.75rem",
          background: "linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #312e81 100%)",
          borderRadius: 14,
          padding: "1.35rem 1.75rem",
          color: "white",
          boxShadow: "0 18px 40px rgba(15,23,42,0.35)",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem" }}>
          <div>
            <h1 style={{ margin: 0, fontSize: "1.85rem", fontWeight: 700 }}>Advanced Analytics</h1>
            <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.92rem", opacity: 0.92, maxWidth: 640, lineHeight: 1.5 }}>
              Deeper operational intelligence: category × workflow mix, weekly intake, assignee load, reporter quality,
              and geographic drill-down. Use the{" "}
              <Link to="/dashboard" style={{ color: "#a5b4fc", fontWeight: 600 }}>
                Dashboard
              </Link>{" "}
              for day-to-day overview and workflow.
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
            <Link
              to="/dashboard"
              style={{
                color: "#e0e7ff",
                textDecoration: "none",
                fontWeight: 600,
                fontSize: "0.875rem",
                padding: "0.4rem 0.85rem",
                borderRadius: 999,
                border: "1px solid rgba(165,180,252,0.5)",
                background: "rgba(15,23,42,0.35)",
              }}
            >
              Quick dashboard
            </Link>
            <Link
              to="/dashboard?tab=lab"
              style={{
                color: "#e0e7ff",
                textDecoration: "none",
                fontWeight: 600,
                fontSize: "0.875rem",
                padding: "0.4rem 0.85rem",
                borderRadius: 999,
                border: "1px solid rgba(165,180,252,0.5)",
                background: "rgba(15,23,42,0.35)",
              }}
            >
              Hotspot lab
            </Link>
            <Link
              to="/"
              style={{
                color: "#e0e7ff",
                textDecoration: "none",
                fontWeight: 600,
                fontSize: "0.875rem",
                padding: "0.4rem 0.85rem",
                borderRadius: 999,
                border: "1px solid rgba(165,180,252,0.5)",
                background: "rgba(15,23,42,0.35)",
              }}
            >
              Map
            </Link>
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>Total reports</div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0f172a" }}>{advanced?.total_reports ?? 0}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>Backlog (open + in progress)</div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#b45309" }}>{advanced?.backlog_open_or_in_progress ?? 0}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>Last 30 days</div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0f172a" }}>{advanced?.last_30_days ?? 0}</div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>Avg resolution (days)</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a" }}>
            {advanced?.average_resolution_time_days != null
              ? advanced.average_resolution_time_days.toFixed(1)
              : "—"}
          </div>
        </div>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.8rem", color: "#64748b", fontWeight: 600 }}>Active hotspots</div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#4f46e5" }}>{hs?.count ?? 0}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)", gap: "1.5rem", marginBottom: "2rem" }}>
        <div style={cardStyle}>
          <h2 style={sectionTitle}>Category × workflow status (top 12)</h2>
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "0.75rem" }}>
            Where workload concentrates by category — stacked by open, in progress, resolved, dismissed.
          </p>
          <div style={{ height: 360 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topCategoriesForStack} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="category" tick={{ fontSize: 10 }} angle={-35} textAnchor="end" height={70} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="open" stackId="s" fill={COLORS.open} name="Open" />
                <Bar dataKey="in_progress" stackId="s" fill={COLORS.in_progress} name="In progress" />
                <Bar dataKey="resolved" stackId="s" fill={COLORS.resolved} name="Resolved" />
                <Bar dataKey="dismissed" stackId="s" fill={COLORS.dismissed} name="Dismissed" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div style={cardStyle}>
          <h2 style={sectionTitle}>Weekly intake</h2>
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "0.75rem" }}>
            Report volume by week (recent window) — complements the dashboard’s 30-day daily view.
          </p>
          <div style={{ height: 360 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={advanced?.reports_per_week ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="week_start" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Area type="monotone" dataKey="count" stroke="#6366f1" fill="#a5b4fc" fillOpacity={0.35} name="Reports" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: "2rem", ...cardStyle }}>
        <h2 style={sectionTitle}>30-day daily trend & status composition</h2>
        <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "0.75rem" }}>
          Same window as the overview dashboard, shown here for side-by-side analysis with weekly buckets above.
        </p>
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={dashboard?.reports_per_day ?? []} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 9 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#059669" strokeWidth={2} name="New reports / day" dot={{ r: 2 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ marginBottom: "2rem", ...cardStyle }}>
        <h2 style={sectionTitle}>Category quality & share</h2>
        <div style={{ overflowX: "auto", maxHeight: 320, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#e2e8f0", textAlign: "left" }}>
                <th style={{ padding: "0.6rem" }}>Category</th>
                <th style={{ padding: "0.6rem" }}>Total</th>
                <th style={{ padding: "0.6rem" }}>Share</th>
                <th style={{ padding: "0.6rem" }}>Resolved</th>
                <th style={{ padding: "0.6rem" }}>Invalid</th>
                <th style={{ padding: "0.6rem" }}>Resolution rate</th>
                <th style={{ padding: "0.6rem" }}>Invalid rate</th>
              </tr>
            </thead>
            <tbody>
              {(advanced?.category_quality ?? []).map((row) => (
                <tr key={row.category} style={{ borderTop: "1px solid #e5e7eb" }}>
                  <td style={{ padding: "0.55rem", fontWeight: 600 }}>{row.category}</td>
                  <td style={{ padding: "0.55rem" }}>{row.total}</td>
                  <td style={{ padding: "0.55rem" }}>{(row.share_of_all * 100).toFixed(1)}%</td>
                  <td style={{ padding: "0.55rem" }}>{row.resolved}</td>
                  <td style={{ padding: "0.55rem" }}>{row.invalid}</td>
                  <td style={{ padding: "0.55rem" }}>{(row.resolution_rate * 100).toFixed(0)}%</td>
                  <td style={{ padding: "0.55rem" }}>{(row.invalid_rate * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", gap: "1.5rem", marginBottom: "2rem" }}>
        <div style={cardStyle}>
          <h2 style={sectionTitle}>Assignee load</h2>
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "0.75rem" }}>
            Count of reports currently assigned (all statuses) — top 25.
          </p>
          <div style={{ height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={(advanced?.assignee_load ?? []).slice(0, 12)}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="username" width={100} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="assigned_reports" fill="#7c3aed" name="Assigned reports" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div style={cardStyle}>
          <h2 style={sectionTitle}>Reporter intelligence</h2>
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "0.75rem" }}>
            Volume, resolution outcomes, and invalid rates by reporter (top 30).
          </p>
          <div style={{ maxHeight: 320, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr style={{ background: "#e2e8f0", textAlign: "left" }}>
                  <th style={{ padding: "0.5rem" }}>User</th>
                  <th style={{ padding: "0.5rem" }}>Total</th>
                  <th style={{ padding: "0.5rem" }}>Res %</th>
                  <th style={{ padding: "0.5rem" }}>Inv %</th>
                  <th style={{ padding: "0.5rem" }}>Trusted</th>
                </tr>
              </thead>
              <tbody>
                {(advanced?.reporter_stats ?? []).map((u, i) => (
                  <tr key={u.username + i} style={{ borderTop: "1px solid #e5e7eb" }}>
                    <td style={{ padding: "0.45rem", fontWeight: 500 }}>{u.username}</td>
                    <td style={{ padding: "0.45rem" }}>{u.total_reports}</td>
                    <td style={{ padding: "0.45rem" }}>{(u.resolution_rate * 100).toFixed(0)}%</td>
                    <td style={{ padding: "0.45rem" }}>{(u.invalid_rate * 100).toFixed(0)}%</td>
                    <td style={{ padding: "0.45rem" }}>{u.trusted ? "Yes" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div style={{ ...cardStyle, marginBottom: "2rem" }}>
        <h2 style={sectionTitle}>Geographic drill-down</h2>
        <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: "-0.5rem", marginBottom: "1rem" }}>
          Pull report counts and a sample of recent titles for a county, constituency, or local council boundary.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end", marginBottom: "1rem" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600, color: "#334155" }}>
            Area type
            <select
              value={geoType}
              onChange={(e) => setGeoType(e.target.value)}
              style={{ padding: "0.45rem 0.65rem", borderRadius: 8, border: "1px solid #cbd5e1", minWidth: 160 }}
            >
              <option value="county">County</option>
              <option value="constituency">Dáil constituency</option>
              <option value="council">Local council</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600, color: "#334155", flex: "1 1 220px" }}>
            Boundary
            <select
              value={geoName}
              onChange={(e) => setGeoName(e.target.value)}
              style={{ padding: "0.45rem 0.65rem", borderRadius: 8, border: "1px solid #cbd5e1", width: "100%" }}
            >
              <option value="">Select…</option>
              {geoOptions.map((o) => (
                <option key={o.id} value={geoType === "county" ? o.name.toUpperCase() : o.name}>
                  {o.name} ({o.report_count ?? 0})
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={runGeoInsight}
            disabled={geoLoading || !geoName}
            style={{
              padding: "0.55rem 1.1rem",
              borderRadius: 8,
              border: "none",
              fontWeight: 600,
              cursor: geoLoading || !geoName ? "not-allowed" : "pointer",
              background: geoLoading || !geoName ? "#94a3b8" : "linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)",
              color: "white",
            }}
          >
            {geoLoading ? "Loading…" : "Load insight"}
          </button>
        </div>
        {geoInsight?.error && (
          <p style={{ color: "#dc2626", fontSize: "0.9rem" }}>{geoInsight.error}</p>
        )}
        {geoInsight && !geoInsight.error && (
          <div style={{ background: "white", borderRadius: 8, border: "1px solid #e2e8f0", padding: "1rem" }}>
            <p style={{ margin: 0, fontWeight: 700, color: "#0f172a" }}>
              {geoInsight.name} <span style={{ fontWeight: 500, color: "#64748b" }}>({geoInsight.total_count} reports)</span>
            </p>
            <p style={{ fontSize: "0.85rem", color: "#64748b", margin: "0.5rem 0 0 0" }}>Recent sample:</p>
            <ul style={{ margin: "0.5rem 0 0 1rem", padding: 0, fontSize: "0.9rem", color: "#334155" }}>
              {(geoInsight.reports ?? []).slice(0, 8).map((r) => (
                <li key={r.id} style={{ marginBottom: "0.25rem" }}>
                  {r.title} <span style={{ color: "#94a3b8" }}>({r.category})</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div style={{ ...cardStyle, marginBottom: "1rem" }}>
        <h2 style={sectionTitle}>Hotspot pipeline</h2>
        <p style={{ fontSize: "0.9rem", color: "#475569", marginBottom: "0.75rem" }}>
          Current cluster polygons: <strong>{hs?.count ?? 0}</strong>
          {hs?.latest_created_at && (
            <>
              {" "}
              · Last generated: <strong>{new Date(hs.latest_created_at).toLocaleString()}</strong>
            </>
          )}
        </p>
        <Link
          to="/dashboard?tab=lab"
          style={{
            display: "inline-block",
            padding: "0.45rem 0.9rem",
            borderRadius: 8,
            background: "#0f172a",
            color: "white",
            textDecoration: "none",
            fontWeight: 600,
            fontSize: "0.875rem",
          }}
        >
          Open hotspot lab (DBSCAN parameters)
        </Link>
      </div>

      <Link to="/" style={{ textDecoration: "none", color: "#475569", fontWeight: 600 }}>
        ← Back to map
      </Link>
    </div>
  );
}
