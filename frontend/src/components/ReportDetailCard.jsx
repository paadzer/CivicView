import React from "react";

export default function ReportDetailCard({ report, onClose }) {
  if (!report) return null;

  const likeCount = report.like_count || 0;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15,23,42,0.55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          maxWidth: 640,
          width: "100%",
          maxHeight: "80vh",
          overflow: "auto",
          background: "#ffffff",
          borderRadius: 14,
          border: "1px solid #e2e8f0",
          boxShadow: "0 24px 60px rgba(15,23,42,0.45)",
          padding: "1.5rem 1.75rem",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.75rem",
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: "1.25rem",
              fontWeight: 700,
              color: "#0f172a",
            }}
          >
            {report.title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              color: "#64748b",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 600,
            }}
          >
            ✕ Close
          </button>
        </div>
        <p style={{ margin: "0 0 0.5rem 0", fontSize: 13, color: "#64748b" }}>
          <strong style={{ color: "#0f172a" }}>{report.category}</strong>{" "}
          • {report.status_display || report.status}{" "}
          {report.created_at && (
            <>
              • Reported{" "}
              {new Date(report.created_at).toLocaleDateString()}
            </>
          )}
        </p>
        <p style={{ margin: "0 0 0.5rem 0", fontSize: 13, color: "#64748b" }}>
          Reported by{" "}
          <strong style={{ color: "#0f172a" }}>
            {report.created_by_username || "Unknown"}
          </strong>
          {report.assigned_to_username && (
            <>
              {" "}
              • Assigned to{" "}
              <strong style={{ color: "#0f172a" }}>
                {report.assigned_to_username}
              </strong>
            </>
          )}
        </p>
        <p
          style={{
            margin: "0.75rem 0 1rem 0",
            fontSize: 14,
            color: "#111827",
            lineHeight: 1.5,
          }}
        >
          {report.description}
        </p>
        {report.images && report.images.length > 0 && (
          <div style={{ marginBottom: "1rem" }}>
            <div
              style={{
                fontSize: 12,
                color: "#64748b",
                marginBottom: "0.35rem",
              }}
            >
              Photos ({report.images.length})
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "0.5rem",
              }}
            >
              {report.images.slice(0, 6).map((url, idx) => (
                <div
                  key={idx}
                  style={{
                    width: 96,
                    height: 96,
                    borderRadius: 8,
                    overflow: "hidden",
                    background: "#e5e7eb",
                  }}
                >
                  <img
                    src={url}
                    alt={`Report ${report.id} image ${idx + 1}`}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
        <div style={{ fontSize: 12, color: "#64748b", marginTop: "0.5rem" }}>
          <div>
            Priority score:{" "}
            <strong style={{ color: "#0f172a" }}>
              {report.priority_score != null
                ? report.priority_score.toFixed(1)
                : "—"}
            </strong>
          </div>
          <div style={{ marginTop: "0.25rem" }}>
            Liked by{" "}
            <strong style={{ color: "#0f172a" }}>{likeCount}</strong>{" "}
            user{likeCount === 1 ? "" : "s"}.
          </div>
        </div>
      </div>
    </div>
  );
}

