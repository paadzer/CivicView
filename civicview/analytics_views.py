# Analytics API for council/admin: summary stats and dashboard data
from collections import OrderedDict
from datetime import timedelta

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import County, DailConstituency, Report
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


class GeographicReportsView(APIView):
    """GET /api/analytics/geographic-reports/?type=county&name=DUBLIN - Get reports within a specific geographic area (council/admin only)."""

    permission_classes = [IsCouncilOrAdmin]

    def get(self, request):
        geo_type = request.query_params.get("type", "").lower()  # "county" or "constituency"
        name = request.query_params.get("name", "").strip()

        if not geo_type or not name:
            return Response({"error": "Please provide type (county/constituency) and name parameters"}, status=400)

        try:
            if geo_type == "county":
                boundary_obj = County.objects.get(name__iexact=name)
            elif geo_type == "constituency":
                boundary_obj = DailConstituency.objects.get(name__icontains=name)
            else:
                return Response({"error": "Type must be 'county' or 'constituency'"}, status=400)

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
        except (County.DoesNotExist, DailConstituency.DoesNotExist):
            return Response({"error": f"{geo_type.capitalize()} not found"}, status=404)