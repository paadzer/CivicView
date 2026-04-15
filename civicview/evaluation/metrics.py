"""
Deterministic metrics for system evaluation (reporting / CI).

These functions do not mutate the database. Clustering evaluation uses sklearn
on synthetic coordinates in Web Mercator metres (same space as `generate_hotspots`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from django.contrib.gis.geos import Point
from sklearn.cluster import DBSCAN

# Match serializer / product rules (see civicview.serializers)
IRELAND_LAT_MIN, IRELAND_LAT_MAX = 51.4, 55.4
IRELAND_LON_MIN, IRELAND_LON_MAX = -11.0, -5.0
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0


def validate_wgs84_and_ireland(lat: float, lon: float) -> tuple[bool, list[str]]:
    """
    Return (ok, error_messages). Empty list means coordinates are acceptable for a report.
    """
    errors: list[str] = []
    if not (LAT_MIN <= lat <= LAT_MAX):
        errors.append("latitude_range")
    if not (LON_MIN <= lon <= LON_MAX):
        errors.append("longitude_range")
    if not (IRELAND_LAT_MIN <= lat <= IRELAND_LAT_MAX):
        errors.append("ireland_latitude")
    if not (IRELAND_LON_MIN <= lon <= IRELAND_LON_MAX):
        errors.append("ireland_longitude")
    return (len(errors) == 0, errors)


def wgs84_to_meters_xy(lon: float, lat: float) -> tuple[float, float]:
    """Transform a WGS84 point to EPSG:3857 x/y (metres)."""
    p = Point(lon, lat, srid=4326).transform(3857, clone=True)
    return (p.x, p.y)


@dataclass
class SyntheticClusterSpec:
    """Tight square grid of points in metres around an origin (epsg:3857)."""

    origin_x: float
    origin_y: float
    n_per_side: int
    spacing_m: float


def build_synthetic_cluster_points(spec: SyntheticClusterSpec) -> np.ndarray:
    """Nx2 array of [x_m, y_m] for sklearn."""
    pts = []
    for i in range(spec.n_per_side):
        for j in range(spec.n_per_side):
            pts.append(
                [
                    spec.origin_x + i * spec.spacing_m,
                    spec.origin_y + j * spec.spacing_m,
                ]
            )
    return np.array(pts, dtype=np.float64)


def evaluate_dbscan_on_points(
    coords_m: np.ndarray,
    *,
    eps_meters: float,
    min_samples: int,
) -> dict[str, Any]:
    """
    Run DBSCAN and return summary statistics (noise fraction, cluster count, sizes).
    """
    if coords_m.size == 0:
        return {
            "n_points": 0,
            "n_clusters": 0,
            "noise_count": 0,
            "noise_fraction": 0.0,
            "cluster_sizes": [],
            "labels": [],
        }
    clustering = DBSCAN(eps=eps_meters, min_samples=min_samples).fit(coords_m)
    labels = clustering.labels_
    n_noise = int((labels == -1).sum())
    unique = set(labels.tolist()) - {-1}
    sizes = []
    for lab in sorted(unique):
        sizes.append(int((labels == lab).sum()))
    return {
        "n_points": int(coords_m.shape[0]),
        "n_clusters": len(unique),
        "noise_count": n_noise,
        "noise_fraction": round(n_noise / len(labels), 4),
        "cluster_sizes": sizes,
        "labels": labels.tolist(),
    }


def run_synthetic_clustering_evaluation(
    eps_meters: float = 250,
    min_samples: int = 5,
) -> dict[str, Any]:
    """
    Default scenario: 5x5 grid at 40m spacing (~160m extent) should form one cluster
    under eps=250m and min_samples=5.
    """
    # Origin near Dublin in Web Mercator (approximate)
    ox, oy = wgs84_to_meters_xy(-6.2603, 53.3498)
    spec = SyntheticClusterSpec(origin_x=ox, origin_y=oy, n_per_side=5, spacing_m=40.0)
    coords = build_synthetic_cluster_points(spec)
    result = evaluate_dbscan_on_points(coords, eps_meters=eps_meters, min_samples=min_samples)
    result["scenario"] = "5x5_grid_40m_spacing"
    result["eps_meters"] = eps_meters
    result["min_samples"] = min_samples
    return result


def coordinate_validation_matrix() -> list[dict[str, Any]]:
    """
    Fixed edge cases for documentation and regression (evaluation report table).
    """
    cases = [
        {"name": "dublin_centre", "lat": 53.3498, "lon": -6.2603, "expect_ok": True},
        {"name": "malin_head_north", "lat": 55.38, "lon": -7.37, "expect_ok": True},
        {"name": "mizen_head_south", "lat": 51.45, "lon": -9.82, "expect_ok": True},
        {"name": "edinburgh_outside_lat", "lat": 55.95, "lon": -3.18, "expect_ok": False},
        {"name": "london_outside", "lat": 51.5, "lon": -0.12, "expect_ok": False},
        {"name": "new_york_outside", "lat": 40.71, "lon": -74.01, "expect_ok": False},
        {"name": "invalid_lat", "lat": 100.0, "lon": -6.26, "expect_ok": False},
    ]
    out = []
    for c in cases:
        ok, errs = validate_wgs84_and_ireland(c["lat"], c["lon"])
        out.append(
            {
                **c,
                "ok": ok,
                "errors": errs,
                "matches_expectation": ok == c["expect_ok"],
            }
        )
    return out
