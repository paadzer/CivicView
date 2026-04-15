import { Link } from "react-router-dom";

const WRAPPER_CARDS = [
  {
    title: "Summary Dashboard",
    description: "Quick aggregate view of totals, statuses, and reporting trends.",
    route: "/dashboard?tab=overview",
    cta: "Open Summary",
  },
  {
    title: "Geographic Comparison",
    description: "Compare counties, constituencies, and councils in two clicks.",
    route: "/dashboard?tab=geographic",
    cta: "Compare Areas",
  },
  {
    title: "Hotspot Tuning",
    description: "Run DBSCAN experiments and instantly refresh hotspot outputs.",
    route: "/dashboard?tab=lab",
    cta: "Tune Hotspots",
  },
  {
    title: "Workflow + Export",
    description: "Manage report workflows, then export filtered data.",
    route: "/dashboard?tab=management",
    cta: "Manage Reports",
  },
];

export default function AdvancedAnalyticsWrapper({ role }) {
  const isDashboardUser = ["staff", "council", "manager", "admin"].includes(role);

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

  return (
    <div style={{ padding: "2rem", maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ marginBottom: "0.5rem" }}>Advanced Analytics</h1>
        <p style={{ color: "#475569", margin: 0 }}>
          Click-click-done access to in-depth analytics workflows and visual breakdowns.
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "1rem",
        }}
      >
        {WRAPPER_CARDS.map((card) => (
          <div
            key={card.title}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: 12,
              padding: "1rem",
              background: "#f8fafc",
              boxShadow: "0 4px 12px rgba(15,23,42,0.08)",
            }}
          >
            <h2 style={{ fontSize: "1.05rem", marginTop: 0, marginBottom: "0.5rem" }}>
              {card.title}
            </h2>
            <p style={{ color: "#475569", fontSize: "0.9rem", minHeight: 44 }}>
              {card.description}
            </p>
            <Link
              to={card.route}
              style={{
                display: "inline-block",
                marginTop: "0.5rem",
                textDecoration: "none",
                color: "white",
                background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                padding: "0.45rem 0.9rem",
                borderRadius: 8,
                fontWeight: 600,
                fontSize: "0.875rem",
              }}
            >
              {card.cta}
            </Link>
          </div>
        ))}
      </div>

      <div style={{ marginTop: "1.5rem" }}>
        <Link to="/" style={{ textDecoration: "none", color: "#334155", fontWeight: 600 }}>
          ← Back to map
        </Link>
      </div>
    </div>
  );
}
