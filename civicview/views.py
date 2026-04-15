# Import Django REST Framework viewsets for API endpoints
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
import logging
from django.http import HttpResponse
import csv
from .filters import ReportFilter
from .models import County, DailConstituency, Hotspot, LocalCouncil, Report, ReportImage
from .permissions import IsCouncilOrAdmin, ReportPermission
from .serializers import (
    CountySerializer,
    DailConstituencySerializer,
    HotspotSerializer,
    LocalCouncilSerializer,
    ReportSerializer,
)
from .tasks import generate_hotspots


# ReportViewSet: Provides full CRUD operations for civic reports
# Handles GET (list/detail), POST (create), PUT/PATCH (update), DELETE operations
class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all().order_by("-created_at")
    serializer_class = ReportSerializer
    permission_classes = [ReportPermission]
    # Category + time filters; ordering: ?ordering=-created_at or ordering=created_at, status
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ReportFilter
    ordering_fields = ["created_at", "status", "assigned_to"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        # Auto-refresh: trigger hotspot regeneration after new report.
        # Prefer async via Celery, but fall back to synchronous execution if Redis/Celery is unavailable.
        logger = logging.getLogger(__name__)
        try:
            generate_hotspots.delay()
        except Exception as exc:
            logger.warning("Celery/Redis unavailable, running generate_hotspots synchronously: %s", exc)
            try:
                generate_hotspots()
            except Exception as inner_exc:
                logger.error("generate_hotspots failed; continuing without hotspot update: %s", inner_exc)
        return instance

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """List distinct report categories for filter dropdown. GET /api/reports/categories/"""
        categories = Report.objects.values_list("category", flat=True).distinct().order_by("category")
        return Response(list(categories))

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def export(self, request):
        """
        Export reports to CSV.

        Respects existing filters (?category=..., ?period=..., etc.).
        """
        queryset = self.filter_queryset(self.get_queryset())

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reports.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "title",
                "description",
                "category",
                "status",
                "is_valid",
                "created_at",
                "resolved_at",
                "latitude",
                "longitude",
                "like_count",
            ]
        )

        for report in queryset.iterator():
            lat = report.geom.y if report.geom else ""
            lon = report.geom.x if report.geom else ""
            writer.writerow(
                [
                    report.id,
                    report.title,
                    report.description,
                    report.category,
                    report.status,
                    report.is_valid,
                    report.created_at.isoformat() if report.created_at else "",
                    report.resolved_at.isoformat() if report.resolved_at else "",
                    lat,
                    lon,
                    report.supporters.count(),
                ]
            )

        return response

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def images(self, request, pk=None):
        """Upload one or more images for a report. POST /api/reports/{id}/images/ with multipart: image or images[]."""
        report = self.get_object()
        files = request.FILES.getlist("images") or request.FILES.getlist("image") or list(request.FILES.values())
        if not files:
            return Response(
                {"detail": "No image file(s) provided. Send 'image' or 'images' in multipart form."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        created = []
        for f in files[:10]:  # cap at 10 images per request
            if not getattr(f, "content_type", "").startswith("image/"):
                continue
            img = ReportImage.objects.create(report=report, image=f)
            url = request.build_absolute_uri(img.image.url) if img.image else None
            if url:
                created.append(url)
        return Response({"uploaded": len(created), "images": created}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        """
        Mark the current authenticated user as supporting/liking this report.
        POST /api/reports/{id}/like/
        """
        report = self.get_object()
        report.supporters.add(request.user)
        return Response(
            {
                "like_count": report.supporters.count(),
                "liked_by_me": True,
            }
        )


# HotspotViewSet: Provides read-only access to hotspot clusters
# Only supports GET operations (list and detail views) since hotspots are auto-generated
class HotspotViewSet(viewsets.ReadOnlyModelViewSet):
    # Query all hotspots, ordered by most recent first (descending by created_at)
    queryset = Hotspot.objects.all().order_by("-created_at")
    # Serializer class that converts between JSON and Hotspot model instances
    serializer_class = HotspotSerializer
    
    @action(detail=False, methods=["post"])
    def regenerate(self, request):
        """
        Regenerate hotspots with optional parameters.
        POST /api/hotspots/regenerate/?days_back=30&eps=250&min_samples=5&all_time=false
        """
        # Get parameters from query string
        days_back_param = request.query_params.get("days_back")
        days_back = int(days_back_param) if days_back_param else 30
        
        # Check if all_time flag is set
        if request.query_params.get("all_time", "").lower() == "true":
            days_back = None
        
        eps_param = request.query_params.get("eps")
        eps = float(eps_param) if eps_param else None
        
        min_samples_param = request.query_params.get("min_samples")
        min_samples = int(min_samples_param) if min_samples_param else None
        
        # Run synchronously for immediate response (or use .delay() for async)
        result = generate_hotspots(
            days_back=days_back,
            eps_meters=eps,
            min_samples=min_samples,
        )
        return Response(result)


# CountyViewSet: Provides read-only access to county boundaries
class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = County.objects.all().order_by("name")
    serializer_class = CountySerializer
    permission_classes = [IsCouncilOrAdmin]

    def list(self, request, *args, **kwargs):
        if request.query_params.get("minimal"):
            return self._list_minimal_counties()
        return super().list(request, *args, **kwargs)

    def _list_minimal_counties(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT c.id, c.name,
                    (SELECT COUNT(*) FROM civicview_report r
                     WHERE ST_DWithin(r.geom::geography, c.boundary::geography, 2000)) AS report_count
                FROM civicview_county c
                ORDER BY c.name
            """)
            rows = cursor.fetchall()
        return Response([
            {"id": r[0], "name": r[1], "report_count": r[2]}
            for r in rows
        ])


# DailConstituencyViewSet: Provides read-only access to Dáil constituency boundaries
class DailConstituencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailConstituency.objects.all().order_by("name")
    serializer_class = DailConstituencySerializer
    permission_classes = [IsCouncilOrAdmin]

    def list(self, request, *args, **kwargs):
        if request.query_params.get("minimal"):
            return self._list_minimal_constituencies()
        return super().list(request, *args, **kwargs)

    def _list_minimal_constituencies(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT d.id, d.name,
                    (SELECT COUNT(*) FROM civicview_report r
                     WHERE ST_DWithin(r.geom::geography, d.boundary::geography, 2000)) AS report_count
                FROM civicview_dailconstituency d
                ORDER BY d.name
            """)
            rows = cursor.fetchall()
        return Response([
            {"id": r[0], "name": r[1], "report_count": r[2]}
            for r in rows
        ])


# LocalCouncilViewSet: Provides read-only access to local council boundaries
class LocalCouncilViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LocalCouncil.objects.all().order_by("name")
    serializer_class = LocalCouncilSerializer
    permission_classes = [IsCouncilOrAdmin]

    def list(self, request, *args, **kwargs):
        if request.query_params.get("minimal"):
            return self._list_minimal_councils()
        return super().list(request, *args, **kwargs)

    def _list_minimal_councils(self):
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT l.id, l.name,
                    (SELECT COUNT(*) FROM civicview_report r
                     WHERE ST_DWithin(r.geom::geography, l.boundary::geography, 2000)) AS report_count
                FROM civicview_localcouncil l
                ORDER BY l.name
            """)
            rows = cursor.fetchall()
        return Response([
            {"id": r[0], "name": r[1], "report_count": r[2]}
            for r in rows
        ])
