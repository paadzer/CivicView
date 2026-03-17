# Import JSON for parsing GeoJSON geometry data
import json
from datetime import timedelta

# Import GeoDjango Point class for creating spatial geometries
from django.contrib.gis.geos import Point
# Import Django REST Framework serializers
from rest_framework import serializers
from django.utils import timezone

from .models import County, DailConstituency, Hotspot, Notification, Profile, Report, ReportImage


# Valid latitude/longitude ranges (WGS84)
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0
# Ireland approximate bounds (for location validation improvement)
IRELAND_LAT_MIN, IRELAND_LAT_MAX = 51.4, 55.4
IRELAND_LON_MIN, IRELAND_LON_MAX = -11.0, -5.0


# ReportSerializer: Converts Report model instances to/from JSON for API
# Handles conversion between lat/lng (user-friendly) and PostGIS Point geometry
class ReportSerializer(serializers.ModelSerializer):
    # Accept latitude/longitude as separate fields when creating reports (write-only)
    # This is more user-friendly than requiring GeoJSON format
    latitude = serializers.FloatField(write_only=True)
    longitude = serializers.FloatField(write_only=True)
    # Return geometry as GeoJSON when reading (read-only, computed field)
    geom = serializers.SerializerMethodField(read_only=True)
    # Readable status label (e.g. "In progress") alongside internal status value
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    # Read-only username of the reporter and assignee for convenience in the frontend
    created_by_username = serializers.SerializerMethodField(read_only=True)
    assigned_to_username = serializers.SerializerMethodField(read_only=True)
    # Computed priority score combining recency, category severity, status, and hotspot membership
    priority_score = serializers.SerializerMethodField(read_only=True)
    # Image URLs for report photos (from mobile or web)
    images = serializers.SerializerMethodField(read_only=True)
    # Simple engagement metrics
    like_count = serializers.SerializerMethodField(read_only=True)
    liked_by_me = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "description",
            "category",
            "status",
            "is_valid",
            "latitude",
            "longitude",
            "geom",
            "created_by",
            "created_by_username",
            "assigned_to",
            "assigned_to_username",
            "target_resolution_date",
            "created_at",
            "resolved_at",
            "status_display",
            "priority_score",
            "images",
            "like_count",
            "liked_by_me",
        ]
        # These fields are auto-generated or set server-side
        read_only_fields = [
            "id",
            "geom",
            "created_by",
            "created_by_username",
            "created_at",
            "resolved_at",
            "status_display",
            "assigned_to_username",
            "priority_score",
            "images",
            "like_count",
            "liked_by_me",
        ]

    def validate(self, data):
        """Location validation: valid WGS84 range and optional Ireland bounds.

        Also enforces that only privileged roles can modify workflow fields such as
        status, assigned_to, and target_resolution_date.
        """
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None:
            if not (LAT_MIN <= lat <= LAT_MAX):
                raise serializers.ValidationError(
                    {"latitude": f"Latitude must be between {LAT_MIN} and {LAT_MAX}."}
                )
            if not (IRELAND_LAT_MIN <= lat <= IRELAND_LAT_MAX):
                raise serializers.ValidationError(
                    {"latitude": f"Location must be within Ireland (latitude {IRELAND_LAT_MIN}–{IRELAND_LAT_MAX})."}
                )
        if lon is not None:
            if not (LON_MIN <= lon <= LON_MAX):
                raise serializers.ValidationError(
                    {"longitude": f"Longitude must be between {LON_MIN} and {LON_MAX}."}
                )
            if not (IRELAND_LON_MIN <= lon <= IRELAND_LON_MAX):
                raise serializers.ValidationError(
                    {"longitude": f"Location must be within Ireland (longitude {IRELAND_LON_MIN}–{IRELAND_LON_MAX})."}
                )

        # Workflow / quality-control field permission checks
        request = self.context.get("request")
        if request and request.method in ("POST", "PUT", "PATCH"):
            user = request.user
            profile = getattr(user, "profile", None) if user else None
            role = getattr(profile, "role", None) if profile else None
            can_manage_workflow = role in Profile.WORKFLOW_ROLES
            can_assign = role in Profile.CAN_ASSIGN_ROLES

            if not can_manage_workflow:
                restricted = {}
                for field in ("status", "target_resolution_date", "is_valid"):
                    if field in data:
                        restricted[field] = "You do not have permission to modify this field."
                if "assigned_to" in data:
                    restricted["assigned_to"] = "You do not have permission to modify this field."
                if restricted:
                    raise serializers.ValidationError(restricted)
            elif "assigned_to" in data and not can_assign:
                # Staff/council can change workflow but only manager/admin can set assignee
                if data.get("assigned_to") is not None:
                    raise serializers.ValidationError(
                        {"assigned_to": "Only managers or admins can assign reports to someone else."}
                    )

            # If manager/admin sets assigned_to, ensure assignee is an assignable user
            if can_assign and "assigned_to" in data:
                assignee_value = data.get("assigned_to")
                if assignee_value is not None:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    # PrimaryKeyRelatedField may already have resolved to a User instance in validate()
                    if isinstance(assignee_value, User):
                        assignee = assignee_value
                    else:
                        try:
                            assignee = User.objects.get(pk=assignee_value)
                        except User.DoesNotExist:
                            raise serializers.ValidationError(
                                {"assigned_to": "User not found."}
                            )
                    assignee_profile = getattr(assignee, "profile", None)
                    if not assignee_profile or assignee_profile.role not in Profile.ASSIGNABLE_ROLES:
                        raise serializers.ValidationError(
                            {"assigned_to": "That user cannot be assigned reports (must be staff, council, or manager)."}
                        )
        return data

    # Custom create method: Converts lat/lng to PostGIS Point geometry; created_by set in view
    def create(self, validated_data):
        # Extract latitude and longitude from the request data
        lat = validated_data.pop("latitude")
        lon = validated_data.pop("longitude")
        # Create a Point geometry (longitude first, then latitude, WGS84 SRID)
        geom = Point(lon, lat, srid=4326)
        created_by = validated_data.pop("created_by", None)
        return Report.objects.create(geom=geom, created_by=created_by, **validated_data)

    def update(self, instance, validated_data):
        """Update report and manage resolved_at when status changes. Create in-app notification when assigned_to is set."""
        old_assignee_id = instance.assigned_to_id
        old_status = instance.status
        instance = super().update(instance, validated_data)

        # Automatically set or clear resolved_at based on status transitions
        if instance.status == Report.STATUS_RESOLVED and instance.resolved_at is None:
            instance.resolved_at = timezone.now()
            instance.save(update_fields=["resolved_at"])
        elif instance.status != Report.STATUS_RESOLVED and instance.resolved_at is not None:
            instance.resolved_at = None
            instance.save(update_fields=["resolved_at"])

        # In-app notification when report is assigned to someone (and assignee changed)
        if "assigned_to" in validated_data and instance.assigned_to_id and instance.assigned_to_id != old_assignee_id:
            Notification.objects.create(
                user_id=instance.assigned_to_id,
                message=f'Report "{instance.title}" assigned to you.',
                report=instance,
            )
        return instance

    # Convert PostGIS geometry to GeoJSON format for API responses
    def get_geom(self, obj):
        # obj.geom.geojson returns a GeoJSON string, parse it to a Python dict
        return json.loads(obj.geom.geojson)

    def get_assigned_to_username(self, obj):
        user = getattr(obj, "assigned_to", None)
        return getattr(user, "username", None) if user else None

    def get_created_by_username(self, obj):
        user = getattr(obj, "created_by", None)
        return getattr(user, "username", None) if user else None

    def get_priority_score(self, obj):
        """
        Compute a simple priority score combining:
        - Recency (newer reports score higher)
        - Category severity (safety-related > cosmetic)
        - Workflow status (open / in progress > resolved / dismissed)
        - Hotspot membership (reports inside hotspots are more important)
        """
        score = 0.0

        # Recency component: up to ~10 points for very recent reports
        if obj.created_at:
            age = timezone.now() - obj.created_at
            age_days = age.total_seconds() / 86400.0
            recency_component = max(0.0, 10.0 - age_days)
            score += recency_component

        # Category severity weights (can be tuned per deployment)
        category_weights = {
            "Safety": 10.0,
            "Lighting": 6.0,
            "Road": 7.0,
            "Potholes": 5.0,
        }
        score += category_weights.get(obj.category, 3.0)

        # Workflow status: unresolved items are more urgent
        if obj.status in (Report.STATUS_OPEN, Report.STATUS_IN_PROGRESS):
            score += 5.0

        # De-prioritise reports explicitly marked invalid
        if not getattr(obj, "is_valid", True):
            score -= 10.0

        # Hotspot membership: bump priority if report is inside at least one hotspot
        try:
            in_hotspot = Hotspot.objects.filter(geom__intersects=obj.geom).exists()
        except Exception:
            in_hotspot = False
        if in_hotspot:
            score += 8.0

        # Slight boost for reports created by council/admin users (institutional reporters)
        creator = getattr(obj, "created_by", None)
        profile = getattr(creator, "profile", None) if creator else None
        role = getattr(profile, "role", None) if profile else None
        if role in Profile.DASHBOARD_ROLES:
            score += 4.0

        return round(score, 2)

    def get_images(self, obj):
        """Return list of full image URLs for this report."""
        request = self.context.get("request")
        if not request:
            return [img.image.url for img in obj.images.all() if img.image]
        return [request.build_absolute_uri(img.image.url) for img in obj.images.all() if img.image]

    def get_like_count(self, obj):
        # Number of users who support/like this report
        return obj.supporters.count()

    def get_liked_by_me(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return obj.supporters.filter(id=user.id).exists()


# HotspotSerializer: Converts Hotspot model instances to/from JSON for API
# Provides read-only access to hotspot cluster data
class HotspotSerializer(serializers.ModelSerializer):
    # Return geometry as GeoJSON when reading (read-only, computed field)
    geom = serializers.SerializerMethodField(read_only=True)
    # Count of reports in this cluster (computed field)
    count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Hotspot
        # Fields exposed in the API
        fields = ["id", "cluster_id", "geom", "count", "created_at"]
        # These fields are auto-generated and cannot be modified via API
        read_only_fields = ["id", "geom", "count", "created_at"]

    # Convert PostGIS geometry to GeoJSON format for API responses
    def get_geom(self, obj):
        # obj.geom.geojson returns a GeoJSON string, parse it to a Python dict
        return json.loads(obj.geom.geojson)
    
    # Get count of reports in this cluster
    # Note: This is approximate - counts reports within the hotspot polygon
    def get_count(self, obj):
        # Count reports that intersect with this hotspot polygon
        # Using a small buffer to account for points near polygon edges
        from .models import Report
        return Report.objects.filter(geom__intersects=obj.geom).count()


# CountySerializer: Converts County model instances to/from JSON for API
class CountySerializer(serializers.ModelSerializer):
    # Return geometry as GeoJSON when reading (read-only, computed field)
    geom = serializers.SerializerMethodField(read_only=True)
    # Count of reports within this county boundary
    report_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = County
        fields = ["id", "name", "geom", "report_count"]
        read_only_fields = ["id", "geom", "report_count"]

    def get_geom(self, obj):
        """Convert PostGIS MultiPolygon to GeoJSON format."""
        return json.loads(obj.boundary.geojson)

    def get_report_count(self, obj):
        """Count reports that fall within this county boundary."""
        if not obj.boundary:
            return 0
        try:
            # Use PostGIS ST_DWithin for fast distance-based query (2km buffer)
            # This is much faster than buffering the entire geometry
            # ST_DWithin checks if geometries are within a distance (in meters for geography type)
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM civicview_report 
                    WHERE ST_DWithin(
                        geom::geography, 
                        %s::geography, 
                        2000
                    )
                """, [obj.boundary.ewkb])
                return cursor.fetchone()[0]
        except Exception:
            # Fallback to simple intersection query
            return Report.objects.filter(geom__intersects=obj.boundary).count()


# Notification serializer for in-app notification list
class NotificationSerializer(serializers.ModelSerializer):
    report_title = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "message", "report", "report_title", "read_at", "created_at"]
        read_only_fields = ["id", "message", "report", "report_title", "created_at"]

    def get_report_title(self, obj):
        return obj.report.title if obj.report_id and obj.report else None


# Minimal serializer for assignable users (staff, council, manager) for report assignment dropdown
class AssignableUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)

    def to_representation(self, instance):
        profile = getattr(instance, "profile", None)
        role = profile.role if profile else "citizen"
        return {"id": instance.id, "username": instance.username, "role": role}


# DailConstituencySerializer: Converts DailConstituency model instances to/from JSON for API
class DailConstituencySerializer(serializers.ModelSerializer):
    # Return geometry as GeoJSON when reading (read-only, computed field)
    geom = serializers.SerializerMethodField(read_only=True)
    # Count of reports within this constituency boundary
    report_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DailConstituency
        fields = ["id", "name", "geom", "report_count"]
        read_only_fields = ["id", "geom", "report_count"]

    def get_geom(self, obj):
        """Convert PostGIS MultiPolygon to GeoJSON format."""
        return json.loads(obj.boundary.geojson)

    def get_report_count(self, obj):
        """Count reports that fall within this constituency boundary."""
        if not obj.boundary:
            return 0
        try:
            # Use PostGIS ST_DWithin for fast distance-based query (2km buffer)
            # This is much faster than buffering the entire geometry
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM civicview_report 
                    WHERE ST_DWithin(
                        geom::geography, 
                        %s::geography, 
                        2000
                    )
                """, [obj.boundary.ewkb])
                return cursor.fetchone()[0]
        except Exception:
            # Fallback to simple intersection query
            return Report.objects.filter(geom__intersects=obj.boundary).count()

