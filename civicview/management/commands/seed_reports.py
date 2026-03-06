"""
Django management command to seed realistic civic issue reports across Ireland.

This script generates reports clustered around major cities/towns and scattered
across Ireland, ensuring all coordinates are on land (no ocean points).

Usage:
    python manage.py seed_reports
    python manage.py seed_reports --clusters 6 --scattered 120
    python manage.py seed_reports --reset  # Delete existing seeded reports first
"""

import math
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from civicview.models import Report

# ============================================================================
# MODEL FIELD MAPPING
# ============================================================================
# If your model fields differ, update these constants:
MODEL_NAME = "Report"
LOCATION_FIELD = "geom"  # GeoDjango PointField
CATEGORY_FIELD = "category"
TITLE_FIELD = "title"
DESCRIPTION_FIELD = "description"
CREATED_AT_FIELD = "created_at"
CREATED_BY_FIELD = "created_by"

# ============================================================================
# IRELAND TOWN/CITY CENTERS (lat, lon) - Used as seed points
# ============================================================================
# Major cities for dense clusters (20-40 reports each)
MAJOR_CITIES = [
    {"name": "Dublin", "lat": 53.3498, "lon": -6.2603, "type": "city", "cluster_weight": 40},
    {"name": "Cork", "lat": 51.8985, "lon": -8.4756, "type": "city", "cluster_weight": 35},
    {"name": "Galway", "lat": 53.2707, "lon": -9.0568, "type": "city", "cluster_weight": 30},
    {"name": "Limerick", "lat": 52.6638, "lon": -8.6267, "type": "city", "cluster_weight": 30},
    {"name": "Waterford", "lat": 52.2593, "lon": -7.1101, "type": "city", "cluster_weight": 25},
    {"name": "Kilkenny", "lat": 52.6541, "lon": -7.2522, "type": "city", "cluster_weight": 25},
]

# Towns for scattered reports (1-3 reports each)
TOWNS = [
    {"name": "Sligo", "lat": 54.2766, "lon": -8.4761, "type": "town"},
    {"name": "Letterkenny", "lat": 54.9544, "lon": -7.7333, "type": "town"},
    {"name": "Dundalk", "lat": 54.0037, "lon": -6.4047, "type": "town"},
    {"name": "Drogheda", "lat": 53.7179, "lon": -6.3503, "type": "town"},
    {"name": "Bray", "lat": 53.2028, "lon": -6.0983, "type": "town"},
    {"name": "Navan", "lat": 53.6528, "lon": -6.6814, "type": "town"},
    {"name": "Ennis", "lat": 52.8436, "lon": -8.9864, "type": "town"},
    {"name": "Carlow", "lat": 52.8408, "lon": -6.9261, "type": "town"},
    {"name": "Tralee", "lat": 52.2700, "lon": -9.6986, "type": "town"},
    {"name": "New Ross", "lat": 52.3967, "lon": -6.9367, "type": "town"},
    {"name": "Wexford", "lat": 52.3369, "lon": -6.4633, "type": "town"},
    {"name": "Clonmel", "lat": 52.3547, "lon": -7.7039, "type": "town"},
    {"name": "Thurles", "lat": 52.6800, "lon": -7.8100, "type": "town"},
    {"name": "Tullamore", "lat": 53.2739, "lon": -7.4889, "type": "town"},
    {"name": "Athlone", "lat": 53.4239, "lon": -7.9378, "type": "town"},
    {"name": "Mullingar", "lat": 53.5233, "lon": -7.3383, "type": "town"},
    {"name": "Longford", "lat": 53.7250, "lon": -7.7978, "type": "town"},
    {"name": "Roscommon", "lat": 53.6333, "lon": -8.1833, "type": "town"},
    {"name": "Castlebar", "lat": 53.8500, "lon": -9.3000, "type": "town"},
    {"name": "Ballina", "lat": 54.1167, "lon": -9.1667, "type": "town"},
    {"name": "Westport", "lat": 53.8000, "lon": -9.5167, "type": "town"},
    {"name": "Swords", "lat": 53.4597, "lon": -6.2181, "type": "town"},
    {"name": "Naas", "lat": 53.2158, "lon": -6.6669, "type": "town"},
    {"name": "Portlaoise", "lat": 53.0300, "lon": -7.3000, "type": "town"},
    {"name": "Birr", "lat": 53.0914, "lon": -7.9133, "type": "town"},
]

# ============================================================================
# SAFE BOUNDING BOXES FOR IRELAND LAND AREAS
# ============================================================================
# Conservative bounding boxes covering populated regions, excluding obvious sea areas
# Format: (min_lat, max_lat, min_lon, max_lon)
IRELAND_LAND_BOXES = [
    # Dublin area (east coast)
    (53.20, 53.50, -6.50, -6.00),
    # Cork area (south coast)
    (51.70, 52.10, -8.80, -8.20),
    # Galway area (west coast)
    (53.10, 53.40, -9.30, -8.80),
    # Limerick area (mid-west)
    (52.50, 52.80, -8.80, -8.40),
    # Waterford area (south-east)
    (52.10, 52.40, -7.30, -6.90),
    # Kilkenny area (south-east inland)
    (52.50, 52.80, -7.40, -7.00),
    # Sligo area (north-west)
    (54.10, 54.40, -8.60, -8.30),
    # Donegal area (north)
    (54.80, 55.20, -7.90, -7.40),
    # Louth/Meath area (north-east)
    (53.60, 54.00, -6.60, -6.20),
    # Wicklow area (east coast)
    (52.90, 53.20, -6.30, -6.00),
    # Wexford area (south-east)
    (52.20, 52.50, -6.60, -6.20),
    # Tipperary area (mid-south)
    (52.30, 52.80, -8.00, -7.50),
    # Offaly/Westmeath area (midlands)
    (53.20, 53.60, -7.60, -7.20),
    # Mayo area (west)
    (53.70, 54.20, -9.60, -9.00),
    # Kerry area (south-west)
    (52.10, 52.40, -9.90, -9.50),
]

# ============================================================================
# CATEGORIES WITH WEIGHTS AND LOCATION RULES
# ============================================================================
# Format: (category_name, weight, allowed_in_cities_only)
CATEGORIES = [
    ("Pothole", 25, False),  # Common everywhere
    ("Streetlight", 20, False),  # Common everywhere
    ("Litter", 18, False),  # Common everywhere
    ("Illegal dumping", 15, False),  # Common, especially suburban/rural
    ("Footpath damage", 12, False),  # Mostly urban/suburban
    ("Graffiti", 10, False),  # Mostly urban
    ("Drain blocked", 8, False),  # Common everywhere
    ("Traffic signal", 6, True),  # CITIES ONLY
    ("Road sign damage", 5, False),  # Common everywhere
    ("Water leak", 4, False),  # Less common
    ("Cycling lane issue", 3, True),  # CITIES ONLY
    ("Noise complaint", 2, False),  # Mostly urban
    ("Antisocial behaviour", 2, False),  # Mostly urban
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_point_near(center_lat, center_lon, max_km=2.0):
    """
    Generate a random point near a center location.
    
    Args:
        center_lat: Center latitude
        center_lon: Center longitude
        max_km: Maximum distance in kilometers
    
    Returns:
        (lat, lon) tuple
    """
    # Approximate conversion: 1 degree lat ≈ 111 km
    # 1 degree lon ≈ 111 km * cos(lat)
    max_lat_offset = max_km / 111.0
    max_lon_offset = max_km / (111.0 * math.cos(math.radians(center_lat)))
    
    # Generate random offset (uniform distribution within circle)
    angle = random.uniform(0, 2 * math.pi)
    distance_km = random.uniform(0, max_km)
    
    lat_offset = (distance_km / 111.0) * math.cos(angle)
    lon_offset = (distance_km / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
    
    new_lat = center_lat + lat_offset
    new_lon = center_lon + lon_offset
    
    return new_lat, new_lon


def is_plausible_ireland_land(lat, lon):
    """
    Check if coordinates are within safe Ireland land bounding boxes.
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Returns:
        True if point is within any safe bounding box
    """
    for min_lat, max_lat, min_lon, max_lon in IRELAND_LAND_BOXES:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return True
    return False


def generate_realistic_description(category, location_name, location_type):
    """
    Generate a realistic description for a report.
    
    Args:
        category: Report category
        location_name: Name of town/city
        location_type: "city" or "town"
    
    Returns:
        Description string
    """
    descriptors = {
        "Pothole": [
            f"Large pothole on road near {location_name} causing vehicle damage.",
            f"Deep pothole at junction requiring urgent repair.",
            f"Multiple potholes forming on this stretch of road.",
            f"Pothole outside residential area needs attention.",
        ],
        "Streetlight": [
            f"Streetlight out on main road through {location_name}.",
            f"Broken streetlight near bus stop creating safety hazard.",
            f"Multiple streetlights not working in this area.",
            f"Streetlight flickering and needs replacement.",
        ],
        "Litter": [
            f"Accumulation of litter at roadside near {location_name}.",
            f"Litter bins overflowing and rubbish scattered around.",
            f"Large amount of litter dumped in public area.",
            f"Regular littering issue at this location.",
        ],
        "Illegal dumping": [
            f"Furniture and waste illegally dumped at roadside.",
            f"Large items dumped in lay-by near {location_name}.",
            f"Illegal waste dumping site developing here.",
            f"Household waste dumped in rural area.",
        ],
        "Footpath damage": [
            f"Cracked and uneven footpath causing trip hazard.",
            f"Footpath damage outside shops in {location_name}.",
            f"Broken paving slabs need replacement.",
            f"Footpath surface deteriorating and unsafe.",
        ],
        "Graffiti": [
            f"Graffiti on public building wall in {location_name}.",
            f"Vandalism graffiti on bus shelter.",
            f"Extensive graffiti covering public property.",
            f"Graffiti needs removal from public space.",
        ],
        "Drain blocked": [
            f"Blocked drain causing water pooling on road.",
            f"Drain overflow near {location_name} after heavy rain.",
            f"Blocked drain needs clearing urgently.",
            f"Drainage issue causing localised flooding.",
        ],
        "Traffic signal": [
            f"Traffic lights malfunctioning at busy junction in {location_name}.",
            f"Traffic signal timing issue causing delays.",
            f"Broken traffic light needs repair at intersection.",
            f"Traffic signal not responding properly.",
        ],
        "Road sign damage": [
            f"Road sign damaged and difficult to read.",
            f"Direction sign knocked over at junction.",
            f"Road sign vandalised and needs replacement.",
            f"Signage damaged and creating confusion.",
        ],
        "Water leak": [
            f"Water leak from pipe causing road damage.",
            f"Water main leak near {location_name} needs urgent repair.",
            f"Continuous water leak wasting resources.",
            f"Water leak creating hazard on footpath.",
        ],
        "Cycling lane issue": [
            f"Cycling lane blocked by parked vehicles in {location_name}.",
            f"Cycling lane surface damaged and unsafe.",
            f"Cycling infrastructure needs maintenance.",
            f"Cycling lane markings faded and unclear.",
        ],
        "Noise complaint": [
            f"Excessive noise from construction site affecting residents.",
            f"Late night noise disturbance in {location_name}.",
            f"Ongoing noise issue needs council attention.",
            f"Noise complaint from commercial premises.",
        ],
        "Antisocial behaviour": [
            f"Reports of antisocial behaviour in public area.",
            f"Concerns about antisocial activity near {location_name}.",
            f"Public space being misused causing issues.",
            f"Antisocial behaviour affecting local community.",
        ],
    }
    
    options = descriptors.get(category, [f"Issue reported in {location_name}."])
    return random.choice(options)


def choose_category(location_type):
    """
    Choose a category based on weights and location rules.
    
    Args:
        location_type: "city" or "town"
    
    Returns:
        Category name string
    """
    # Filter categories based on location type
    if location_type == "city":
        available = [(cat, weight) for cat, weight, cities_only in CATEGORIES]
    else:
        available = [(cat, weight) for cat, weight, cities_only in CATEGORIES if not cities_only]
    
    # Weighted random selection
    categories, weights = zip(*available)
    return random.choices(categories, weights=weights)[0]


# ============================================================================
# DJANGO MANAGEMENT COMMAND
# ============================================================================


class Command(BaseCommand):
    help = "Seed realistic civic issue reports across Ireland (land-only, clustered)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clusters",
            type=int,
            default=6,
            help="Number of reports per major city cluster (default: 6 cities, ~30 each)",
        )
        parser.add_argument(
            "--cluster-size",
            type=int,
            default=30,
            help="Average reports per cluster (default: 30)",
        )
        parser.add_argument(
            "--scattered",
            type=int,
            default=80,
            help="Number of scattered reports across towns (default: 80)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing seeded reports before creating new ones",
        )

    def handle(self, *args, **options):
        cluster_count = options["clusters"]
        cluster_size = options["cluster_size"]
        scattered_count = options["scattered"]
        reset = options["reset"]

        # Delete existing seeded reports if requested
        if reset:
            deleted = Report.objects.all().delete()[0]
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted} existing reports.")
            )

        User = get_user_model()
        user = User.objects.first()

        now = timezone.now()
        created = 0
        rejected = 0
        category_counts = {}
        cluster_counts = {}

        # Generate clustered reports around major cities
        self.stdout.write("Generating clustered reports around major cities...")
        cities_to_use = random.sample(MAJOR_CITIES, min(cluster_count, len(MAJOR_CITIES)))
        
        for city in cities_to_use:
            cluster_name = city["name"]
            cluster_reports = 0
            cluster_size_actual = random.randint(
                int(cluster_size * 0.7), int(cluster_size * 1.3)
            )
            
            for _ in range(cluster_size_actual):
                # Generate point near city center
                max_km = random.uniform(0.5, 2.0)  # Within 0.5-2 km
                lat, lon = generate_point_near(city["lat"], city["lon"], max_km)
                
                # Validate point is on land
                if not is_plausible_ireland_land(lat, lon):
                    rejected += 1
                    continue
                
                category = choose_category(city["type"])
                title = f"{category} issue in {cluster_name}"
                description = generate_realistic_description(
                    category, cluster_name, city["type"]
                )
                
                # Timestamp: more recent reports (weighted toward last 30 days)
                days_ago = int(random.expovariate(1.0 / 20))  # Exponential distribution
                days_ago = min(days_ago, 90)  # Cap at 90 days
                created_at = now - timedelta(days=days_ago)
                
                point = Point(lon, lat, srid=4326)
                report = Report.objects.create(
                    title=title,
                    description=description,
                    category=category,
                    geom=point,
                    created_by=user,
                )
                report.created_at = created_at
                report.save(update_fields=["created_at"])
                
                created += 1
                cluster_reports += 1
                category_counts[category] = category_counts.get(category, 0) + 1
            
            cluster_counts[cluster_name] = cluster_reports
            self.stdout.write(f"  {cluster_name}: {cluster_reports} reports")

        # Generate scattered reports across towns
        self.stdout.write(f"\nGenerating {scattered_count} scattered reports across towns...")
        for i in range(scattered_count):
            town = random.choice(TOWNS)
            
            # Generate point near town center (smaller radius for towns)
            max_km = random.uniform(0.3, 1.5)
            lat, lon = generate_point_near(town["lat"], town["lon"], max_km)
            
            # Validate point is on land
            if not is_plausible_ireland_land(lat, lon):
                rejected += 1
                continue
            
            category = choose_category(town["type"])
            title = f"{category} issue near {town['name']}"
            description = generate_realistic_description(
                category, town["name"], town["type"]
            )
            
            # Timestamp: spread over last 90 days
            days_ago = random.randint(0, 90)
            created_at = now - timedelta(days=days_ago)
            
            point = Point(lon, lat, srid=4326)
            report = Report.objects.create(
                title=title,
                description=description,
                category=category,
                geom=point,
                created_by=user,
            )
            report.created_at = created_at
            report.save(update_fields=["created_at"])
            
            created += 1
            category_counts[category] = category_counts.get(category, 0) + 1

        # Summary output
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
        self.stdout.write(self.style.SUCCESS("SEEDING SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Total reports created: {created}")
        self.stdout.write(f"Rejected (invalid coordinates): {rejected}")
        
        self.stdout.write("\nReports by cluster:")
        for cluster_name, count in cluster_counts.items():
            self.stdout.write(f"  {cluster_name}: {count}")
        
        self.stdout.write("\nReports by category:")
        for category, count in sorted(
            category_counts.items(), key=lambda x: x[1], reverse=True
        ):
            self.stdout.write(f"  {category}: {count}")
        
        # Coordinate bounds check
        if created > 0:
            all_reports = Report.objects.all()
            lats = [r.geom.y for r in all_reports]
            lons = [r.geom.x for r in all_reports]
            self.stdout.write(f"\nCoordinate bounds:")
            self.stdout.write(f"  Lat: {min(lats):.4f} to {max(lats):.4f}")
            self.stdout.write(f"  Lon: {min(lons):.4f} to {max(lons):.4f}")
        
        self.stdout.write(self.style.SUCCESS("\n✓ Seeding completed successfully!"))
