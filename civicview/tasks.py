# Import Celery decorator for async task execution
from celery import shared_task
# Import GeoDjango geometry classes
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
# Import Shapely for geometric operations
from shapely.geometry import Point as ShapelyPoint
from shapely.ops import unary_union
# Import DBSCAN clustering algorithm from scikit-learn
from sklearn.cluster import DBSCAN

from django.utils import timezone
from datetime import timedelta

from .models import Hotspot, Report


# DBSCAN parameters (in meters)
EPS_METERS = 250  # Maximum distance between points to be in same cluster (250m)
MIN_SAMPLES = 5  # Minimum number of reports needed to form a cluster (lowered for better clustering)
BUFFER_METERS = 120  # Buffer radius for creating polygons from points
SIMPLIFY_TOLERANCE_METERS = 15  # Simplify tolerance for reducing polygon complexity


# Main task: Generate hotspot clusters from existing reports using DBSCAN
# This can be run asynchronously via Celery or synchronously via management command
@shared_task
def generate_hotspots(days_back=30, eps_meters=None, min_samples=None):
    """
    Generate hotspot clusters from reports using DBSCAN.
    
    Args:
        days_back: Number of days to look back for reports (default: 30, None = all time)
        eps_meters: DBSCAN eps parameter in meters (default: EPS_METERS constant)
        min_samples: DBSCAN min_samples parameter (default: MIN_SAMPLES constant)
    
    Returns:
        Dictionary with statistics about generated hotspots
    """
    # Use provided parameters or defaults
    eps = eps_meters if eps_meters is not None else EPS_METERS
    min_samp = min_samples if min_samples is not None else MIN_SAMPLES
    
    # Filter reports by time window (if days_back is provided)
    if days_back is not None:
        cutoff_date = timezone.now() - timedelta(days=days_back)
        reports = Report.objects.filter(created_at__gte=cutoff_date)
    else:
        # No time filter - use all reports
        reports = Report.objects.all()
    
    # Early return if no reports exist
    if not reports.exists():
        return {"hotspots_created": 0, "total_reports": 0, "clusters_found": 0}

    # Extract coordinates and transform to meters (EPSG:3857 Web Mercator)
    # EPSG:3857 is good for Ireland and works well with DBSCAN in meters
    # Use GeoDjango's transform method (via GDAL) for coordinate transformation
    coords_wgs84 = []
    coords_meters = []
    report_ids = []
    
    for report in reports:
        lon, lat = report.geom.x, report.geom.y
        # Skip invalid coordinates (sanity check)
        if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
            continue
        coords_wgs84.append((lon, lat))
        # Transform to meters using GeoDjango Point transform
        try:
            point_3857 = report.geom.transform(3857, clone=True)
            # Skip if transformation produces invalid values
            if abs(point_3857.x) > 20037509 or abs(point_3857.y) > 20037509:
                continue
            coords_meters.append([point_3857.x, point_3857.y])
            report_ids.append(report.id)
        except Exception:
            # Skip reports with transformation errors
            continue
    
    # Early return if no valid coordinates
    if len(coords_meters) < min_samp:
        return {
            "hotspots_created": 0,
            "total_reports": len(coords_meters),
            "clusters_found": 0,
            "noise_points": len(coords_meters),
            "error": f"Not enough valid reports (need at least {min_samp}, got {len(coords_meters)})",
            "eps_meters": eps,
            "min_samples": min_samp,
        }
    
    # Apply DBSCAN clustering algorithm in meters
    # eps is now in meters, not degrees
    clustering = DBSCAN(eps=eps, min_samples=min_samp).fit(coords_meters)
    labels = clustering.labels_

    # Delete all existing hotspots before generating new ones
    Hotspot.objects.all().delete()

    # Group points by their cluster label
    clusters = {}
    for (lon, lat), label in zip(coords_wgs84, labels):
        # Skip noise points (label -1) - these are isolated reports
        if label == -1:
            continue
        # Add point to its cluster group
        clusters.setdefault(label, []).append((lon, lat))

    # Create Hotspot records for each cluster using buffered union method
    created = 0
    
    for cluster_id, points in clusters.items():
        # Skip clusters that are too small (shouldn't happen due to min_samples, but safety check)
        if len(points) < min_samp:
            continue
        
        # Generate polygon using buffered union method
        try:
            polygon = _create_buffered_polygon(points)
            
            if polygon:
                # If MultiPolygon, extract the largest polygon (model uses PolygonField)
                if isinstance(polygon, MultiPolygon):
                    # Find the largest polygon by area
                    largest = max(polygon, key=lambda p: p.area)
                    polygon = largest
                
                Hotspot.objects.create(cluster_id=cluster_id, geom=polygon)
                created += 1
        except Exception as e:
            # Skip clusters that fail polygon generation
            continue

    # Return summary statistics
    return {
        "hotspots_created": created,
        "total_reports": len(coords_meters),
        "clusters_found": len(clusters),
        "noise_points": int((labels == -1).sum()),
        "eps_meters": eps,
        "min_samples": min_samp,
    }


def _create_buffered_polygon(points_wgs84):
    """
    Create a polygon from cluster points using buffered union method.
    
    Steps:
    1. Transform points to meters (EPSG:3857) using GeoDjango
    2. Buffer each point by BUFFER_METERS using Shapely
    3. Union all buffers
    4. Simplify the result
    5. Transform back to WGS84 using GeoDjango
    6. Convert to GeoDjango Polygon/MultiPolygon
    
    Args:
        points_wgs84: List of (lon, lat) tuples in WGS84
    
    Returns:
        GeoDjango Polygon or MultiPolygon, or None if invalid
    """
    if len(points_wgs84) < 2:
        return None
    
    # Transform points to meters and create buffered circles
    buffers = []
    
    for lon, lat in points_wgs84:
        # Create GeoDjango Point and transform to EPSG:3857
        point_wgs84 = Point(lon, lat, srid=4326)
        point_3857 = point_wgs84.transform(3857, clone=True)
        
        # Create Shapely point in meters and buffer it
        point_shapely = ShapelyPoint(point_3857.x, point_3857.y)
        buffer = point_shapely.buffer(BUFFER_METERS)
        buffers.append(buffer)
    
    # Union all buffers to create a single geometry
    union = unary_union(buffers)
    
    # Simplify the geometry to reduce complexity
    union = union.simplify(SIMPLIFY_TOLERANCE_METERS, preserve_topology=True)
    
    # Handle MultiPolygon (if cluster splits into separate areas)
    if union.geom_type == "MultiPolygon":
        polygons = []
        for poly in union.geoms:
            # Transform exterior ring back to WGS84
            # Create GeoDjango Polygon from Shapely coordinates
            coords_3857 = list(poly.exterior.coords)
            # Convert each coordinate back to WGS84
            coords_wgs84 = []
            for x_m, y_m in coords_3857:
                point_3857 = Point(x_m, y_m, srid=3857)
                point_wgs84 = point_3857.transform(4326, clone=True)
                coords_wgs84.append((point_wgs84.x, point_wgs84.y))
            polygons.append(Polygon(coords_wgs84))
        return MultiPolygon(polygons)
    
    elif union.geom_type == "Polygon":
        # Transform exterior ring back to WGS84
        coords_3857 = list(union.exterior.coords)
        coords_wgs84 = []
        for x_m, y_m in coords_3857:
            point_3857 = Point(x_m, y_m, srid=3857)
            point_wgs84 = point_3857.transform(4326, clone=True)
            coords_wgs84.append((point_wgs84.x, point_wgs84.y))
        return Polygon(coords_wgs84)
    
    # Fallback: return None if geometry type is unexpected
    return None

