# Analytics API for council/admin: summary stats and dashboard data
from collections import Counter, OrderedDict, defaultdict
from datetime import timedelta
import itertools
import math
import statistics

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import County, DailConstituency, Hotspot, LocalCouncil, Report
from .permissions import IsCouncilOrAdmin


def get_reports_within_boundary(boundary, buffer_meters=2000):
    """
    Get reports within a boundary using PostGIS ST_DWithin for fast distance-based query.
    Uses a buffer to catch reports near boundary edges.
    """
    if not boundary:
        return Report.objects.none()
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id 
                FROM civicview_report 
                WHERE ST_DWithin(
                    geom::geography, 
                    %s::geography, 
                    %s
                )
            """, [boundary.ewkb, buffer_meters])
            report_ids = [row[0] for row in cursor.fetchall()]
            return Report.objects.filter(id__in=report_ids)
    except Exception:
        # Fallback to simple intersection query
        return Report.objects.filter(geom__intersects=boundary)


class AnalyticsSummaryView(APIView):
    """GET /api/analytics/summary/ - Totals, category/status breakdown, and basic resolution stats (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        now = timezone.now()
        total = Report.objects.count()
        by_category = (
            Report.objects.values("category")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_status = (
            Report.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        last_7 = Report.objects.filter(
            created_at__gte=now - timedelta(days=7)
        ).count()
        last_30 = Report.objects.filter(
            created_at__gte=now - timedelta(days=30)
        ).count()

        # Average resolution time for resolved reports (in days, may be null if no resolved reports)
        resolved_qs = Report.objects.filter(
            status=Report.STATUS_RESOLVED,
            resolved_at__isnull=False,
        )
        avg_resolution = resolved_qs.annotate(
            resolution_time=F("resolved_at") - F("created_at")
        ).aggregate(avg_resolution=Avg("resolution_time"))["avg_resolution"]
        avg_resolution_days = (
            avg_resolution.total_seconds() / 86400.0 if avg_resolution else None
        )

        # Reporter quality metrics (top reporters)
        reporter_stats_qs = Report.objects.values("created_by__username").annotate(
            total_reports=Count("id"),
            resolved_reports=Count("id", filter=Q(status=Report.STATUS_RESOLVED)),
            invalid_reports=Count("id", filter=Q(is_valid=False)),
        ).order_by("-total_reports")[:20]
        reporter_stats = []
        for row in reporter_stats_qs:
            username = row["created_by__username"] or "Anonymous"
            total_reports = row["total_reports"] or 0
            resolved_reports = row["resolved_reports"] or 0
            invalid_reports = row["invalid_reports"] or 0
            resolution_rate = (resolved_reports / total_reports) if total_reports else 0.0
            invalid_rate = (invalid_reports / total_reports) if total_reports else 0.0
            trusted = total_reports >= 3 and invalid_rate < 0.25
            reporter_stats.append(
                {
                    "username": username,
                    "total_reports": total_reports,
                    "resolved_reports": resolved_reports,
                    "invalid_reports": invalid_reports,
                    "resolution_rate": resolution_rate,
                    "invalid_rate": invalid_rate,
                    "trusted": trusted,
                }
            )

        return Response({
            "total_reports": total,
            "by_category": list(by_category),
            "by_status": list(by_status),
            "last_7_days": last_7,
            "last_30_days": last_30,
            "average_resolution_time_days": avg_resolution_days,
            "reporter_stats": reporter_stats,
        })


class AnalyticsDashboardView(APIView):
    """GET /api/analytics/dashboard/ - Time series and breakdowns for charts (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        now = timezone.now()
        # Reports per day for last 30 days (for line/bar chart)
        start = now - timedelta(days=30)
        per_day = (
            Report.objects.filter(created_at__gte=start)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        # Fill missing days with 0 so chart has continuous series
        date_counts = OrderedDict()
        for i in range(31):
            d = (now - timedelta(days=30 - i)).date()
            date_counts[str(d)] = 0
        for row in per_day:
            date_counts[str(row["date"])] = row["count"]
        reports_per_day = [{"date": k, "count": v} for k, v in date_counts.items()]

        # Top categories (for pie/bar)
        by_category = (
            Report.objects.values("category")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Status over time (last 30 days): open vs in_progress vs resolved vs dismissed
        status_series_qs = (
            Report.objects.filter(created_at__gte=start)
            .annotate(date=TruncDate("created_at"))
            .values("date", "status")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        # Initialize structure with zero counts for each status per day
        status_per_day = OrderedDict()
        for i in range(31):
            d = (now - timedelta(days=30 - i)).date()
            status_per_day[str(d)] = {
                "date": str(d),
                "open": 0,
                "in_progress": 0,
                "resolved": 0,
                "dismissed": 0,
            }
        for row in status_series_qs:
            date_key = str(row["date"])
            status = row["status"] or "open"
            if date_key not in status_per_day:
                continue
            if status in status_per_day[date_key]:
                status_per_day[date_key][status] = row["count"]
        reports_by_status_per_day = list(status_per_day.values())

        return Response({
            "reports_per_day": reports_per_day,
            "top_categories": list(by_category),
            "reports_by_status_per_day": reports_by_status_per_day,
        })


class AnalyticsAdvancedView(APIView):
    """
    GET /api/analytics/advanced/ — Deeper aggregates for the Advanced Analytics UI
    (category × status, weekly series, per-category quality, assignee load, hotspots).
    """

    permission_classes = [IsCouncilOrAdmin]

    def _poisson_confidence_bands(self, weekly_rows):
        bands = []
        for row in weekly_rows:
            c = float(row.get("count") or 0)
            # Poisson approximation: mean +/- 1.96 * sqrt(mean)
            margin = 1.96 * math.sqrt(c) if c > 0 else 0.0
            bands.append({
                "week_start": row.get("week_start"),
                "count": c,
                "ci_low": max(0.0, c - margin),
                "ci_high": c + margin,
            })
        return bands

    def _predictive_risk(self, now):
        """
        Predict likely high-risk areas for next 7/14 days.
        Uses recent trend + weekly seasonality + category concentration.
        """
        reports_42 = Report.objects.filter(created_at__gte=now - timedelta(days=42))
        total_42 = reports_42.count()
        if total_42 == 0:
            return {
                "model_notes": "Insufficient recent history for prediction.",
                "horizon_days": [7, 14],
                "top_risk_areas": [],
                "risk_heatmap_layer": [],
            }

        last_14 = reports_42.filter(created_at__gte=now - timedelta(days=14)).count()
        prev_14 = reports_42.filter(
            created_at__gte=now - timedelta(days=28),
            created_at__lt=now - timedelta(days=14),
        ).count()
        trend_factor = (last_14 + 1) / (prev_14 + 1)

        dow_counts = Counter()
        for r in reports_42.only("created_at"):
            dow_counts[r.created_at.weekday()] += 1
        avg_dow = sum(dow_counts.values()) / 7.0 if dow_counts else 0.0
        target_dows = [((now + timedelta(days=i)).weekday()) for i in range(1, 15)]
        seasonality = (
            sum((dow_counts.get(d, 0) / (avg_dow or 1.0)) for d in target_dows) / len(target_dows)
            if target_dows else 1.0
        )
        seasonality = max(0.5, min(1.8, seasonality))

        cat_weights = {
            "pothole": 1.2, "road": 1.15, "lighting": 1.1, "water": 1.15,
            "waste": 1.05, "graffiti": 0.95, "noise": 0.9,
        }

        top_risk_areas = []
        heatmap = []
        councils = LocalCouncil.objects.all().order_by("name")
        for council in councils:
            rows = list(
                get_reports_within_boundary(council.boundary, buffer_meters=2000)
                .filter(created_at__gte=now - timedelta(days=42))
                .values("created_at", "category")
            )
            n42 = len(rows)
            if not rows:
                continue
            n14 = 0
            n_prev14 = 0
            by_cat_counter = Counter()
            for row in rows:
                created_at = row["created_at"]
                if created_at >= now - timedelta(days=14):
                    n14 += 1
                elif created_at >= now - timedelta(days=28):
                    n_prev14 += 1
                by_cat_counter[row["category"] or "Unknown"] += 1
            local_trend = (n14 + 1) / (n_prev14 + 1)
            weighted_mix = 0.0
            for cat_name, c in by_cat_counter.items():
                cat = (cat_name or "").lower()
                weight = 1.0
                for k, v in cat_weights.items():
                    if k in cat:
                        weight = v
                        break
                weighted_mix += c * weight
            weighted_mix /= max(1, n42)

            # Base expected rate from recent 14-day average then scaled.
            baseline_daily = n14 / 14.0
            pred_7 = baseline_daily * 7 * local_trend * seasonality * weighted_mix
            pred_14 = baseline_daily * 14 * local_trend * seasonality * weighted_mix
            uncertainty = 1.0 / math.sqrt(max(1, n42))
            confidence = max(0.05, min(0.98, 1.0 - uncertainty))
            risk_score = pred_14 * (0.6 + 0.4 * trend_factor)

            centroid = council.boundary.centroid if council.boundary else None
            center = None
            if centroid is not None:
                center = {"lat": centroid.y, "lng": centroid.x}

            row = {
                "type": "council",
                "name": council.name,
                "predicted_reports_7d": round(pred_7, 2),
                "predicted_reports_14d": round(pred_14, 2),
                "risk_score": round(risk_score, 3),
                "confidence": round(confidence, 3),
                "center": center,
            }
            top_risk_areas.append(row)
            heatmap.append({
                "name": council.name,
                "risk_score": round(risk_score, 3),
                "confidence": round(confidence, 3),
                "lat": center["lat"] if center else None,
                "lng": center["lng"] if center else None,
            })

        top_risk_areas.sort(key=lambda x: -x["risk_score"])
        heatmap.sort(key=lambda x: -(x["risk_score"] or 0))
        return {
            "model_notes": "Heuristic spatiotemporal forecast using local trend, weekly seasonality, and category-weighted mix.",
            "horizon_days": [7, 14],
            "top_risk_areas": top_risk_areas[:15],
            "risk_heatmap_layer": heatmap[:80],
        }

    def _reporter_reliability_lookup(self):
        stats = {}
        rows = Report.objects.values("created_by_id").annotate(
            total=Count("id"),
            invalid=Count("id", filter=Q(is_valid=False)),
            resolved=Count("id", filter=Q(status=Report.STATUS_RESOLVED)),
        )
        for r in rows:
            uid = r["created_by_id"]
            if not uid:
                continue
            total = r["total"] or 0
            inv_rate = (r["invalid"] or 0) / total if total else 0.0
            res_rate = (r["resolved"] or 0) / total if total else 0.0
            stats[uid] = {
                "invalid_rate": inv_rate,
                "resolution_rate": res_rate,
                "reliability": max(0.0, min(1.0, 1.0 - inv_rate * 0.8 + res_rate * 0.2)),
            }
        return stats

    def _priority_optimization(self, now):
        """
        Explainable priority score for open/in-progress reports.
        """
        open_qs = Report.objects.filter(
            status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS)
        ).select_related("created_by", "assigned_to").order_by("-created_at")[:80]

        category_weights = {
            "pothole": 0.95,
            "road": 0.9,
            "lighting": 0.85,
            "water": 0.9,
            "flood": 1.0,
            "safety": 1.0,
            "waste": 0.75,
            "graffiti": 0.5,
            "noise": 0.45,
        }

        # Optional "critical infrastructure points" can be added later; default is empty.
        critical_points = []
        reporter_lookup = self._reporter_reliability_lookup()
        ranked = []

        for r in open_qs:
            age_days = max(0.0, (now - r.created_at).total_seconds() / 86400.0)
            age_factor = min(1.0, age_days / 30.0)

            cat = (r.category or "").lower()
            severity = 0.6
            for k, v in category_weights.items():
                if k in cat:
                    severity = v
                    break

            # Repeat incidents: same category within 500m in last 30 days
            repeat_count = Report.objects.filter(
                category=r.category,
                created_at__gte=now - timedelta(days=30),
                geom__distance_lte=(r.geom, 0.005),
            ).exclude(id=r.id).count()
            repeat_factor = min(1.0, repeat_count / 12.0)

            # Cluster intensity proxy using hotspot intersection
            cluster_intensity = 1.0 if Hotspot.objects.filter(geom__intersects=r.geom).exists() else 0.0

            rel = reporter_lookup.get(r.created_by_id, {"reliability": 0.6})
            reporter_factor = rel["reliability"]

            # Placeholder until infra layer exists; factor still surfaced transparently.
            infra_factor = 0.0
            if critical_points:
                infra_factor = 0.0

            components = {
                "severity_proxy": round(severity, 4),
                "age_days": round(age_days, 2),
                "age_factor": round(age_factor, 4),
                "cluster_intensity": round(cluster_intensity, 4),
                "repeat_incidents": repeat_count,
                "repeat_factor": round(repeat_factor, 4),
                "reporter_reliability": round(reporter_factor, 4),
                "near_critical_infrastructure": round(infra_factor, 4),
            }

            score = (
                0.25 * severity
                + 0.25 * age_factor
                + 0.20 * cluster_intensity
                + 0.15 * repeat_factor
                + 0.10 * infra_factor
                + 0.05 * (1.0 - reporter_factor)
            ) * 100.0

            ranked.append({
                "report_id": r.id,
                "title": r.title,
                "category": r.category,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "priority_score": round(score, 2),
                "score_breakdown": components,
            })

        ranked.sort(key=lambda x: -x["priority_score"])
        return {
            "model_notes": "Weighted explainable score (severity, age, hotspot intensity, repeat local incidents, reporter reliability).",
            "top_priority_reports": ranked[:30],
        }

    def _kaplan_meier_curve(self, resolved_days, censored_days, checkpoints=(7, 14, 30, 60)):
        if not resolved_days and not censored_days:
            return {"curve": [], "checkpoints": [], "median_days": None}
        events = defaultdict(lambda: {"d": 0, "c": 0})
        for d in resolved_days:
            events[int(max(0, round(d)))]["d"] += 1
        for c in censored_days:
            events[int(max(0, round(c)))]["c"] += 1

        times = sorted(events.keys())
        n_at_risk = len(resolved_days) + len(censored_days)
        s = 1.0
        curve = []
        median_days = None
        for t in times:
            d = events[t]["d"]
            c = events[t]["c"]
            if n_at_risk <= 0:
                break
            if d > 0:
                s *= (1.0 - d / n_at_risk)
            curve.append({"day": t, "survival_prob_unresolved": round(max(0.0, s), 6)})
            if median_days is None and s <= 0.5:
                median_days = t
            n_at_risk -= (d + c)

        checkpoint_rows = []
        for cp in checkpoints:
            candidates = [row for row in curve if row["day"] <= cp]
            val = candidates[-1]["survival_prob_unresolved"] if candidates else 1.0
            checkpoint_rows.append({"day": cp, "probability_unresolved": round(val, 6)})
        return {"curve": curve, "checkpoints": checkpoint_rows, "median_days": median_days}

    def _sla_survival(self, now):
        resolved = Report.objects.filter(
            status=Report.STATUS_RESOLVED,
            resolved_at__isnull=False,
        ).only("id", "created_at", "resolved_at", "category", "assigned_to__username")
        unresolved = Report.objects.filter(
            status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS)
        ).only("id", "created_at", "category", "assigned_to__username")

        resolved_days_all = [
            max(0.0, (r.resolved_at - r.created_at).total_seconds() / 86400.0)
            for r in resolved if r.created_at and r.resolved_at
        ]
        censored_all = [
            max(0.0, (now - r.created_at).total_seconds() / 86400.0)
            for r in unresolved if r.created_at
        ]
        overall = self._kaplan_meier_curve(resolved_days_all, censored_all)

        per_category = []
        top_categories = (
            Report.objects.values("category")
            .annotate(c=Count("id"))
            .order_by("-c")[:8]
        )
        for row in top_categories:
            cat = row["category"] or "Unknown"
            r_days = [
                max(0.0, (r.resolved_at - r.created_at).total_seconds() / 86400.0)
                for r in resolved if (r.category or "Unknown") == cat and r.created_at and r.resolved_at
            ]
            c_days = [
                max(0.0, (now - r.created_at).total_seconds() / 86400.0)
                for r in unresolved if (r.category or "Unknown") == cat and r.created_at
            ]
            km = self._kaplan_meier_curve(r_days, c_days)
            per_category.append({
                "category": cat,
                "median_days": km["median_days"],
                "checkpoints": km["checkpoints"],
            })

        assignee_summary = []
        assignee_rows = Report.objects.filter(assigned_to__isnull=False).values("assigned_to__username").annotate(c=Count("id")).order_by("-c")[:10]
        for row in assignee_rows:
            name = row["assigned_to__username"] or "Unknown"
            rs = Report.objects.filter(
                assigned_to__username=name,
                status=Report.STATUS_RESOLVED,
                resolved_at__isnull=False,
            )
            avg_days = rs.annotate(
                rt=F("resolved_at") - F("created_at")
            ).aggregate(v=Avg("rt"))["v"]
            avg_days = (avg_days.total_seconds() / 86400.0) if avg_days else None
            open_count = Report.objects.filter(
                assigned_to__username=name,
                status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS),
            ).count()
            assignee_summary.append({
                "username": name,
                "open_count": open_count,
                "average_resolution_days": round(avg_days, 3) if avg_days is not None else None,
            })

        return {
            "overall": overall,
            "by_category": per_category,
            "by_assignee": assignee_summary,
        }

    def _anomaly_alerts(self, now):
        start = now - timedelta(days=45)
        per_day = (
            Report.objects.filter(created_at__gte=start)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("date")
        )
        day_counts = OrderedDict()
        for i in range(46):
            d = (now - timedelta(days=45 - i)).date()
            day_counts[str(d)] = 0
        for row in per_day:
            day_counts[str(row["date"])] = row["count"]
        vals = list(day_counts.values())
        if len(vals) < 10:
            return {"alerts": [], "series": [{"date": k, "count": v} for k, v in day_counts.items()]}

        baseline = vals[-29:-1]
        mean = statistics.mean(baseline) if baseline else 0.0
        stdev = statistics.pstdev(baseline) if len(baseline) > 1 else 0.0
        today = vals[-1]
        z = (today - mean) / stdev if stdev > 0 else 0.0
        ewma = []
        alpha = 0.25
        running = vals[0]
        for v in vals:
            running = alpha * v + (1 - alpha) * running
            ewma.append(running)

        alerts = []
        if z >= 2.0 and today >= 3:
            alerts.append({
                "level": "high" if z >= 3 else "medium",
                "type": "overall_spike",
                "message": f"Daily intake spike detected (z={z:.2f}, today={today}, baseline={mean:.1f}).",
                "z_score": round(z, 3),
                "today_count": today,
                "baseline_mean": round(mean, 3),
            })

        cat_rows = (
            Report.objects.filter(created_at__gte=now - timedelta(days=2))
            .values("category")
            .annotate(c=Count("id"))
            .order_by("-c")[:6]
        )
        for row in cat_rows:
            cat = row["category"] or "Unknown"
            today_cat = row["c"]
            prev_cat = Report.objects.filter(
                category=cat,
                created_at__gte=now - timedelta(days=30),
                created_at__lt=now - timedelta(days=2),
            ).count() / 28.0
            if today_cat >= 3 and today_cat > prev_cat * 2.0:
                alerts.append({
                    "level": "medium",
                    "type": "category_spike",
                    "category": cat,
                    "message": f"{cat}: unusually high short-term volume ({today_cat} recent vs baseline {prev_cat:.2f}/day).",
                    "recent_count": today_cat,
                    "baseline_daily": round(prev_cat, 3),
                })

        return {
            "alerts": alerts[:20],
            "series": [
                {"date": d, "count": c, "ewma": round(ewma[i], 3)}
                for i, (d, c) in enumerate(day_counts.items())
            ],
        }

    def _category_network(self):
        hotspots = Hotspot.objects.order_by("-created_at")[:150]
        pair_counts = Counter()
        node_counts = Counter()

        for hs in hotspots:
            cats = list(
                Report.objects.filter(geom__intersects=hs.geom)
                .values_list("category", flat=True)
                .distinct()
            )
            cats = [c or "Unknown" for c in cats]
            for c in cats:
                node_counts[c] += 1
            for a, b in itertools.combinations(sorted(cats), 2):
                pair_counts[(a, b)] += 1

        edges = [
            {"source": a, "target": b, "weight": w}
            for (a, b), w in pair_counts.items()
            if w >= 2
        ]
        edges.sort(key=lambda e: -e["weight"])
        nodes = [{"id": k, "weight": v} for k, v in node_counts.items()]
        nodes.sort(key=lambda n: -n["weight"])

        # Simple community detection via connected components over threshold edges.
        adj = defaultdict(set)
        for e in edges:
            adj[e["source"]].add(e["target"])
            adj[e["target"]].add(e["source"])
        seen = set()
        communities = []
        for node in adj.keys():
            if node in seen:
                continue
            stack = [node]
            comp = []
            seen.add(node)
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for nb in adj[cur]:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            if len(comp) >= 2:
                communities.append(sorted(comp))
        communities.sort(key=lambda c: (-len(c), c[0] if c else ""))

        return {
            "nodes": nodes[:40],
            "edges": edges[:120],
            "communities": communities[:12],
            "model_notes": "Categories co-occurring inside hotspot polygons; communities are connected components.",
        }

    def _spatial_autocorrelation(self):
        councils = list(LocalCouncil.objects.all().order_by("name"))
        if len(councils) < 3:
            return {"error": "Not enough areas for Moran's I."}

        coords = []
        values = []
        names = []
        for c in councils:
            if not c.boundary:
                continue
            ctr = c.boundary.centroid
            coords.append((ctr.x, ctr.y))
            names.append(c.name)
            values.append(get_reports_within_boundary(c.boundary, buffer_meters=2000).count())
        n = len(values)
        if n < 3:
            return {"error": "Not enough area observations for Moran's I."}
        x_bar = sum(values) / n
        denom = sum((x - x_bar) ** 2 for x in values) or 1e-9
        threshold_deg = 0.6  # ~60km rough threshold for neighboring centroids
        w = [[0.0] * n for _ in range(n)]
        s0 = 0.0
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                dx = coords[i][0] - coords[j][0]
                dy = coords[i][1] - coords[j][1]
                d = math.sqrt(dx * dx + dy * dy)
                wij = 1.0 if d <= threshold_deg else 0.0
                w[i][j] = wij
                s0 += wij
        if s0 <= 0:
            return {"error": "No spatial neighbors for Moran's I at configured threshold."}

        num = 0.0
        for i in range(n):
            for j in range(n):
                num += w[i][j] * (values[i] - x_bar) * (values[j] - x_bar)
        morans_i = (n / s0) * (num / denom)

        # Permutation test for a lightweight significance signal.
        permutations = 99
        greater = 0
        for k in range(permutations):
            perm = values[k % n:] + values[:k % n]
            p_bar = sum(perm) / n
            p_denom = sum((x - p_bar) ** 2 for x in perm) or 1e-9
            p_num = 0.0
            for i in range(n):
                for j in range(n):
                    p_num += w[i][j] * (perm[i] - p_bar) * (perm[j] - p_bar)
            p_i = (n / s0) * (p_num / p_denom)
            if abs(p_i) >= abs(morans_i):
                greater += 1
        p_value = (greater + 1) / (permutations + 1)

        sorted_rows = sorted(zip(names, values), key=lambda x: -x[1])[:12]
        return {
            "moran_i": round(morans_i, 6),
            "p_value": round(p_value, 4),
            "neighbor_threshold_degrees": threshold_deg,
            "top_areas": [{"name": n_, "count": v} for n_, v in sorted_rows],
        }

    def _drilldown_funnel(self):
        total = Report.objects.count()
        top_councils = []
        for c in LocalCouncil.objects.all():
            top_councils.append({
                "name": c.name,
                "count": get_reports_within_boundary(c.boundary, buffer_meters=2000).count(),
            })
        top_councils.sort(key=lambda x: -x["count"])
        return {
            "national_total": total,
            "top_councils": top_councils[:12],
            "top_constituencies": [],
            "notes": "Constituency funnel counts can be enabled later via pre-aggregated table to avoid heavy per-request spatial scans.",
        }

    def _reporter_cohorts(self):
        first_rows = (
            Report.objects.exclude(created_by__isnull=True)
            .values("created_by_id")
            .annotate(first_month=TruncMonth("created_at"))
            .order_by("created_by_id")
        )
        user_to_first = {}
        for row in first_rows:
            user_to_first[row["created_by_id"]] = row["first_month"]
        if not user_to_first:
            return []

        cohort_map = defaultdict(lambda: {"users": set(), "resolved": 0, "invalid": 0, "total": 0})
        qs = Report.objects.exclude(created_by__isnull=True).values(
            "created_by_id", "status", "is_valid", "created_at"
        )
        for r in qs:
            uid = r["created_by_id"]
            fm = user_to_first.get(uid)
            if fm is None:
                continue
            key = fm.date().isoformat() if hasattr(fm, "date") else str(fm)[:10]
            cohort_map[key]["users"].add(uid)
            cohort_map[key]["total"] += 1
            if r["status"] == Report.STATUS_RESOLVED:
                cohort_map[key]["resolved"] += 1
            if r["is_valid"] is False:
                cohort_map[key]["invalid"] += 1

        out = []
        for k, v in sorted(cohort_map.items()):
            total = v["total"] or 1
            out.append({
                "cohort_month": k,
                "users": len(v["users"]),
                "total_reports": v["total"],
                "resolution_rate": round(v["resolved"] / total, 4),
                "invalid_rate": round(v["invalid"] / total, 4),
            })
        return out[-18:]

    def _assignee_rebalancing(self):
        rows = (
            Report.objects.filter(assigned_to__isnull=False)
            .values("assigned_to_id", "assigned_to__username")
            .annotate(
                open_count=Count("id", filter=Q(status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS))),
                resolved_count=Count("id", filter=Q(status=Report.STATUS_RESOLVED)),
            )
        )
        people = []
        for r in rows:
            name = r["assigned_to__username"] or "Unknown"
            open_count = r["open_count"] or 0
            avg_days = Report.objects.filter(
                assigned_to_id=r["assigned_to_id"],
                status=Report.STATUS_RESOLVED,
                resolved_at__isnull=False,
            ).annotate(rt=F("resolved_at") - F("created_at")).aggregate(v=Avg("rt"))["v"]
            avg_days = (avg_days.total_seconds() / 86400.0) if avg_days else 14.0
            people.append({
                "username": name,
                "open_count": open_count,
                "avg_resolution_days": avg_days,
            })
        if len(people) < 2:
            return {"recommendations": [], "model_notes": "Need at least two assignees for balancing suggestions."}
        people.sort(key=lambda x: (x["open_count"], x["avg_resolution_days"]))
        under = people[0]
        over = max(people, key=lambda x: x["open_count"])
        recs = []
        if over["open_count"] - under["open_count"] >= 3:
            move = max(1, (over["open_count"] - under["open_count"]) // 2)
            recs.append({
                "from": over["username"],
                "to": under["username"],
                "suggested_reassignments": move,
                "reason": "Reduce backlog imbalance while preserving throughput.",
            })
        return {"recommendations": recs, "assignees": people}

    def _counterfactual_comparison(self, prioritized_rows):
        backlog_qs = Report.objects.filter(
            status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS)
        ).order_by("created_at")[:120]
        backlog = list(backlog_qs)
        if not backlog:
            return {"policy_a_oldest_first": {}, "policy_b_priority_score": {}}

        hist = Report.objects.filter(status=Report.STATUS_RESOLVED, resolved_at__isnull=False)
        avg_daily_throughput = max(1.0, (hist.count() / 90.0))  # coarse baseline throughput/day
        sample = max(1, int(avg_daily_throughput * 14))

        oldest = sorted(backlog, key=lambda r: r.created_at)[:sample]
        id_to_priority = {r["report_id"]: r["priority_score"] for r in prioritized_rows}
        best = sorted(backlog, key=lambda r: -(id_to_priority.get(r.id, 0.0)))[:sample]

        def avg_age(items):
            if not items:
                return 0.0
            now = timezone.now()
            return sum((now - it.created_at).total_seconds() / 86400.0 for it in items) / len(items)

        return {
            "policy_a_oldest_first": {
                "selected_reports": len(oldest),
                "average_age_days_of_selected": round(avg_age(oldest), 3),
            },
            "policy_b_priority_score": {
                "selected_reports": len(best),
                "average_age_days_of_selected": round(avg_age(best), 3),
            },
            "estimated_delta_days": round(avg_age(best) - avg_age(oldest), 3),
            "model_notes": "Counterfactual replay over current backlog with fixed 14-day throughput budget.",
        }

    def _benchmarking_panel(self):
        councils = []
        for c in LocalCouncil.objects.all():
            count = get_reports_within_boundary(c.boundary, buffer_meters=2000).count()
            area_km2 = max(0.0001, c.boundary.transform(3857, clone=True).area / 1_000_000.0) if c.boundary else 1.0
            councils.append({
                "name": c.name,
                "reports": count,
                "area_km2": round(area_km2, 3),
                "reports_per_km2": round(count / area_km2, 4),
            })
        councils.sort(key=lambda x: -x["reports_per_km2"])

        counties = []
        for c in County.objects.all():
            count = get_reports_within_boundary(c.boundary, buffer_meters=2000).count()
            area_km2 = max(0.0001, c.boundary.transform(3857, clone=True).area / 1_000_000.0) if c.boundary else 1.0
            counties.append({
                "name": c.name,
                "reports": count,
                "area_km2": round(area_km2, 3),
                "reports_per_km2": round(count / area_km2, 4),
            })
        counties.sort(key=lambda x: -x["reports_per_km2"])
        return {
            "councils": councils[:15],
            "counties": counties[:15],
        }

    def get(self, request):
        now = timezone.now()
        total = Report.objects.count()

        status_keys = (
            Report.STATUS_OPEN,
            Report.STATUS_IN_PROGRESS,
            Report.STATUS_RESOLVED,
            Report.STATUS_DISMISSED,
        )

        # Category × workflow status (for stacked / heat-style charts)
        pairs = Report.objects.values("category", "status").annotate(c=Count("id"))
        cat_status = {}
        for row in pairs:
            cat = row["category"] or "Unknown"
            st = row["status"] or Report.STATUS_OPEN
            if cat not in cat_status:
                cat_status[cat] = {s: 0 for s in status_keys}
            if st in cat_status[cat]:
                cat_status[cat][st] = row["c"]
        category_by_status = [
            {"category": cat, **counts}
            for cat, counts in sorted(
                cat_status.items(),
                key=lambda item: -sum(item[1].values()),
            )
        ]

        # Per-category quality / throughput
        category_quality = []
        for cat in sorted(cat_status.keys()):
            qs = Report.objects.filter(category=cat)
            c_total = qs.count()
            if not c_total:
                continue
            resolved_n = qs.filter(status=Report.STATUS_RESOLVED).count()
            invalid_n = qs.filter(is_valid=False).count()
            category_quality.append({
                "category": cat,
                "total": c_total,
                "resolved": resolved_n,
                "invalid": invalid_n,
                "resolution_rate": resolved_n / c_total,
                "invalid_rate": invalid_n / c_total,
                "share_of_all": c_total / total if total else 0.0,
            })
        category_quality.sort(key=lambda x: -x["total"])

        # Weekly volume (last ~16 weeks; bucket start dates from DB TruncWeek)
        weeks_back = 16
        start_week = now - timedelta(weeks=weeks_back)
        per_week_qs = (
            Report.objects.filter(created_at__gte=start_week)
            .annotate(week=TruncWeek("created_at"))
            .values("week")
            .annotate(count=Count("id"))
            .order_by("week")
        )
        reports_per_week = []
        for row in per_week_qs:
            wk = row["week"]
            if wk is None:
                continue
            week_start = wk.date().isoformat() if hasattr(wk, "date") else str(wk)[:10]
            reports_per_week.append({"week_start": week_start, "count": row["count"]})

        # Assignee workload (open pipeline)
        assignee_rows = (
            Report.objects.filter(assigned_to__isnull=False)
            .values("assigned_to__username")
            .annotate(count=Count("id"))
            .order_by("-count")[:25]
        )
        assignee_load = [
            {"username": r["assigned_to__username"] or "Unknown", "assigned_reports": r["count"]}
            for r in assignee_rows
        ]

        # Backlog
        backlog = Report.objects.filter(
            status__in=(Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS),
        ).count()

        # Reporter stats (same logic as summary; kept here so Advanced UI needs one call)
        reporter_stats_qs = Report.objects.values("created_by__username").annotate(
            total_reports=Count("id"),
            resolved_reports=Count("id", filter=Q(status=Report.STATUS_RESOLVED)),
            invalid_reports=Count("id", filter=Q(is_valid=False)),
        ).order_by("-total_reports")[:30]
        reporter_stats = []
        for row in reporter_stats_qs:
            username = row["created_by__username"] or "Anonymous"
            tr = row["total_reports"] or 0
            rr = row["resolved_reports"] or 0
            ir = row["invalid_reports"] or 0
            reporter_stats.append({
                "username": username,
                "total_reports": tr,
                "resolved_reports": rr,
                "invalid_reports": ir,
                "resolution_rate": (rr / tr) if tr else 0.0,
                "invalid_rate": (ir / tr) if tr else 0.0,
                "trusted": tr >= 3 and (ir / tr) < 0.25 if tr else False,
            })

        resolved_qs = Report.objects.filter(
            status=Report.STATUS_RESOLVED,
            resolved_at__isnull=False,
        )
        avg_resolution = resolved_qs.annotate(
            resolution_time=F("resolved_at") - F("created_at")
        ).aggregate(avg_resolution=Avg("resolution_time"))["avg_resolution"]
        avg_resolution_days = (
            avg_resolution.total_seconds() / 86400.0 if avg_resolution else None
        )

        hs = Hotspot.objects.order_by("-created_at").first()
        hotspot_summary = {
            "count": Hotspot.objects.count(),
            "latest_cluster_id": hs.cluster_id if hs else None,
            "latest_created_at": hs.created_at.isoformat() if hs and hs.created_at else None,
        }

        predictive = self._predictive_risk(now)
        priority = self._priority_optimization(now)
        sla_survival = self._sla_survival(now)
        anomalies = self._anomaly_alerts(now)
        network = self._category_network()
        spatial_auto = self._spatial_autocorrelation()
        drilldown = self._drilldown_funnel()
        cohorts = self._reporter_cohorts()
        rebalance = self._assignee_rebalancing()
        counterfactual = self._counterfactual_comparison(priority["top_priority_reports"])
        confidence_bands = self._poisson_confidence_bands(reports_per_week)
        benchmarking = self._benchmarking_panel()

        return Response({
            "total_reports": total,
            "last_7_days": Report.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
            "last_30_days": Report.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
            "backlog_open_or_in_progress": backlog,
            "average_resolution_time_days": avg_resolution_days,
            "category_by_status": category_by_status,
            "category_quality": category_quality,
            "reports_per_week": reports_per_week,
            "reports_per_week_ci": confidence_bands,
            "assignee_load": assignee_load,
            "reporter_stats": reporter_stats,
            "hotspot_summary": hotspot_summary,
            "predictive_risk": predictive,
            "priority_optimization": priority,
            "sla_survival": sla_survival,
            "anomaly_detection": anomalies,
            "category_network": network,
            "spatial_autocorrelation": spatial_auto,
            "drilldown_funnel": drilldown,
            "reporter_cohorts": cohorts,
            "assignee_rebalancing": rebalance,
            "counterfactual_comparison": counterfactual,
            "benchmarking_panel": benchmarking,
        })


class CountyComparisonView(APIView):
    """GET /api/analytics/county-comparison/?counties=DUBLIN,WEXFORD - Compare reports across counties (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        county_names = request.query_params.get("counties", "").split(",")
        county_names = [name.strip().upper() for name in county_names if name.strip()]

        if not county_names:
            return Response({"error": "Please provide county names in ?counties= parameter"}, status=400)

        comparison_data = []
        for county_name in county_names:
            try:
                county = County.objects.get(name__iexact=county_name)
                reports_in_county = get_reports_within_boundary(county.boundary, buffer_meters=2000)

                # Basic stats
                total = reports_in_county.count()
                by_status = (
                    reports_in_county.values("status")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                )
                by_category = (
                    reports_in_county.values("category")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:5]
                )

                # Resolution stats
                resolved = reports_in_county.filter(
                    status=Report.STATUS_RESOLVED,
                    resolved_at__isnull=False,
                )
                avg_resolution = resolved.annotate(
                    resolution_time=F("resolved_at") - F("created_at")
                ).aggregate(avg_resolution=Avg("resolution_time"))["avg_resolution"]
                avg_resolution_days = (
                    avg_resolution.total_seconds() / 86400.0 if avg_resolution else None
                )

                # Reports over time (last 30 days)
                now = timezone.now()
                start = now - timedelta(days=30)
                reports_over_time = (
                    reports_in_county.filter(created_at__gte=start)
                    .annotate(date=TruncDate("created_at"))
                    .values("date")
                    .annotate(count=Count("id"))
                    .order_by("date")
                )
                # Fill missing days with 0
                date_counts = OrderedDict()
                for i in range(31):
                    d = (now - timedelta(days=30 - i)).date()
                    date_counts[str(d)] = 0
                for row in reports_over_time:
                    date_counts[str(row["date"])] = row["count"]
                reports_per_day = [{"date": k, "count": v} for k, v in date_counts.items()]

                comparison_data.append({
                    "name": county.name,
                    "total_reports": total,
                    "by_status": list(by_status),
                    "top_categories": list(by_category),
                    "average_resolution_time_days": avg_resolution_days,
                    "reports_over_time": reports_per_day,
                })

            except County.DoesNotExist:
                comparison_data.append({
                    "name": county_name,
                    "error": "County not found",
                })

        return Response({"comparison": comparison_data})


class ConstituencyComparisonView(APIView):
    """GET /api/analytics/constituency-comparison/?constituencies=Dublin South-West,Dublin South-Central - Compare reports across constituencies (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        constituency_names = request.query_params.get("constituencies", "").split(",")
        constituency_names = [name.strip() for name in constituency_names if name.strip()]

        if not constituency_names:
            return Response({"error": "Please provide constituency names in ?constituencies= parameter"}, status=400)

        comparison_data = []
        for constituency_name in constituency_names:
            try:
                constituency = DailConstituency.objects.get(name__icontains=constituency_name)
                reports_in_constituency = get_reports_within_boundary(constituency.boundary, buffer_meters=2000)
                # Basic stats
                total = reports_in_constituency.count()
                by_status = (
                    reports_in_constituency.values("status")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                )
                by_category = (
                    reports_in_constituency.values("category")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:5]
                )

                # Resolution stats
                resolved = reports_in_constituency.filter(
                    status=Report.STATUS_RESOLVED,
                    resolved_at__isnull=False,
                )
                avg_resolution = resolved.annotate(
                    resolution_time=F("resolved_at") - F("created_at")
                ).aggregate(avg_resolution=Avg("resolution_time"))["avg_resolution"]
                avg_resolution_days = (
                    avg_resolution.total_seconds() / 86400.0 if avg_resolution else None
                )

                # Reports over time (last 30 days)
                now = timezone.now()
                start = now - timedelta(days=30)
                reports_over_time = (
                    reports_in_constituency.filter(created_at__gte=start)
                    .annotate(date=TruncDate("created_at"))
                    .values("date")
                    .annotate(count=Count("id"))
                    .order_by("date")
                )
                # Fill missing days with 0
                date_counts = OrderedDict()
                for i in range(31):
                    d = (now - timedelta(days=30 - i)).date()
                    date_counts[str(d)] = 0
                for row in reports_over_time:
                    date_counts[str(row["date"])] = row["count"]
                reports_per_day = [{"date": k, "count": v} for k, v in date_counts.items()]

                comparison_data.append({
                    "name": constituency.name,
                    "total_reports": total,
                    "by_status": list(by_status),
                    "top_categories": list(by_category),
                    "average_resolution_time_days": avg_resolution_days,
                    "reports_over_time": reports_per_day,
                })
            except DailConstituency.DoesNotExist:
                comparison_data.append({
                    "name": constituency_name,
                    "error": "Constituency not found",
                })

        return Response({"comparison": comparison_data})


class CouncilComparisonView(APIView):
    """GET /api/analytics/council-comparison/?councils=Dublin City Council,Fingal County Council."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        council_names = request.query_params.get("councils", "").split(",")
        council_names = [name.strip() for name in council_names if name.strip()]

        if not council_names:
            return Response({"error": "Please provide council names in ?councils= parameter"}, status=400)

        comparison_data = []
        for council_name in council_names:
            try:
                council = LocalCouncil.objects.get(name__icontains=council_name)
                reports_in_council = get_reports_within_boundary(council.boundary, buffer_meters=2000)
                total = reports_in_council.count()
                by_status = (
                    reports_in_council.values("status")
                    .annotate(count=Count("id"))
                    .order_by("-count")
                )
                by_category = (
                    reports_in_council.values("category")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:5]
                )

                resolved = reports_in_council.filter(
                    status=Report.STATUS_RESOLVED,
                    resolved_at__isnull=False,
                )
                avg_resolution = resolved.annotate(
                    resolution_time=F("resolved_at") - F("created_at")
                ).aggregate(avg_resolution=Avg("resolution_time"))["avg_resolution"]
                avg_resolution_days = (
                    avg_resolution.total_seconds() / 86400.0 if avg_resolution else None
                )

                now = timezone.now()
                start = now - timedelta(days=30)
                reports_over_time = (
                    reports_in_council.filter(created_at__gte=start)
                    .annotate(date=TruncDate("created_at"))
                    .values("date")
                    .annotate(count=Count("id"))
                    .order_by("date")
                )
                date_counts = OrderedDict()
                for i in range(31):
                    d = (now - timedelta(days=30 - i)).date()
                    date_counts[str(d)] = 0
                for row in reports_over_time:
                    date_counts[str(row["date"])] = row["count"]
                reports_per_day = [{"date": k, "count": v} for k, v in date_counts.items()]

                comparison_data.append({
                    "name": council.name,
                    "total_reports": total,
                    "by_status": list(by_status),
                    "top_categories": list(by_category),
                    "average_resolution_time_days": avg_resolution_days,
                    "reports_over_time": reports_per_day,
                })
            except LocalCouncil.DoesNotExist:
                comparison_data.append({
                    "name": council_name,
                    "error": "Council not found",
                })

        return Response({"comparison": comparison_data})


class GeographicReportsView(APIView):
    """GET /api/analytics/geographic-reports/?type=county&name=DUBLIN - Get reports within a specific geographic area (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        geo_type = request.query_params.get("type", "").lower()  # "county", "constituency" or "council"
        name = request.query_params.get("name", "").strip()

        if not geo_type or not name:
            return Response({"error": "Please provide type (county/constituency) and name parameters"}, status=400)

        try:
            if geo_type == "county":
                boundary_obj = County.objects.get(name__iexact=name)
            elif geo_type == "constituency":
                boundary_obj = DailConstituency.objects.get(name__icontains=name)
            elif geo_type == "council":
                boundary_obj = LocalCouncil.objects.get(name__icontains=name)
            else:
                return Response({"error": "Type must be 'county', 'constituency' or 'council'"}, status=400)

            reports = Report.objects.filter(geom__intersects=boundary_obj.boundary).order_by("-created_at")
            
            # Serialize reports
            from .serializers import ReportSerializer
            serializer = ReportSerializer(reports, many=True, context={"request": request})

            return Response({
                "name": boundary_obj.name,
                "type": geo_type,
                "reports": serializer.data,
                "total_count": reports.count(),
            })
        except (County.DoesNotExist, DailConstituency.DoesNotExist, LocalCouncil.DoesNotExist):
            return Response({"error": f"{geo_type.capitalize()} not found"}, status=404)
