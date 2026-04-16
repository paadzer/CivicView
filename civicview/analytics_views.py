# Analytics API for council/admin: summary stats and dashboard data
from collections import OrderedDict
from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate, TruncWeek
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

        return Response({
            "total_reports": total,
            "last_7_days": Report.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
            "last_30_days": Report.objects.filter(created_at__gte=now - timedelta(days=30)).count(),
            "backlog_open_or_in_progress": backlog,
            "average_resolution_time_days": avg_resolution_days,
            "category_by_status": category_by_status,
            "category_quality": category_quality,
            "reports_per_week": reports_per_week,
            "assignee_load": assignee_load,
            "reporter_stats": reporter_stats,
            "hotspot_summary": hotspot_summary,
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
