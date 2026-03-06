# Django management command to import GeoJSON boundary files into County and DailConstituency models
import json
import os

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand

from civicview.models import County, DailConstituency


class Command(BaseCommand):
    help = "Import GeoJSON boundary files for counties and Dáil constituencies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--counties",
            type=str,
            default="civicview/data/boundaries/counties_ireland_osi.geojson",
            help="Path to counties GeoJSON file",
        )
        parser.add_argument(
            "--constituencies",
            type=str,
            default="civicview/data/boundaries/dail_constituencies_2023.geojson",
            help="Path to Dáil constituencies GeoJSON file",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing boundaries before importing",
        )

    def handle(self, *args, **options):
        counties_path = options["counties"]
        constituencies_path = options["constituencies"]
        clear_existing = options["clear"]

        # Clear existing data if requested
        if clear_existing:
            self.stdout.write("Clearing existing boundaries...")
            County.objects.all().delete()
            DailConstituency.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared existing boundaries"))

        # Import counties
        if os.path.exists(counties_path):
            self.stdout.write(f"Importing counties from {counties_path}...")
            self._import_counties(counties_path)
        else:
            self.stdout.write(
                self.style.WARNING(f"Counties file not found: {counties_path}")
            )

        # Import constituencies
        if os.path.exists(constituencies_path):
            self.stdout.write(
                f"Importing Dáil constituencies from {constituencies_path}..."
            )
            self._import_constituencies(constituencies_path)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Constituencies file not found: {constituencies_path}"
                )
            )

    def _import_counties(self, file_path):
        """Import county boundaries from GeoJSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        # Check for CRS declaration in GeoJSON
        source_srid = None
        if "crs" in geojson_data:
            crs_props = geojson_data["crs"].get("properties", {})
            crs_name = crs_props.get("name", "")
            if "EPSG:2157" in crs_name:
                source_srid = 2157
            elif "EPSG:4326" in crs_name:
                source_srid = 4326

        imported = 0
        updated = 0
        errors = 0

        for feature in geojson_data.get("features", []):
            try:
                # Extract county name from properties
                properties = feature.get("properties", {})
                county_name = properties.get("COUNTY", "").strip()

                if not county_name:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping feature with no COUNTY property: {properties}"
                        )
                    )
                    continue

                # Convert GeoJSON geometry to GEOSGeometry.
                geometry = GEOSGeometry(json.dumps(feature["geometry"]))
                
                # Determine source SRID
                if source_srid:
                    # Use CRS from GeoJSON file
                    geometry.srid = source_srid
                elif geometry.srid is None:
                    # Detect by coordinate ranges if no CRS declared
                    try:
                        bounds = geometry.extent
                        x_min, y_min, x_max, y_max = bounds
                        # Irish Grid: X ~500k-800k, Y ~500k-800k (meters)
                        if (x_min > 100000 and x_max < 1000000 and 
                            y_min > 100000 and y_max < 1000000):
                            geometry.srid = 2157
                        else:
                            geometry.srid = 4326
                    except Exception:
                        # Default to Irish Grid for OSI data
                        geometry.srid = 2157
                
                # Transform to WGS84 if not already
                original_srid = geometry.srid
                if geometry.srid != 4326:
                    geometry.transform(4326)
                    self.stdout.write(f"  Transformed {county_name} from EPSG:{original_srid} to EPSG:4326")

                # Ensure it's a MultiPolygon (convert Polygon to MultiPolygon if needed)
                if geometry.geom_type == "Polygon":
                    geometry = MultiPolygon(geometry)

                # Create or update county
                county, created = County.objects.update_or_create(
                    name=county_name,
                    defaults={"boundary": geometry},
                )

                if created:
                    imported += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error importing county {properties.get('COUNTY', 'unknown')}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Counties: {imported} imported, {updated} updated, {errors} errors"
            )
        )

    def _import_constituencies(self, file_path):
        """Import Dáil constituency boundaries from GeoJSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        # Check for CRS declaration in GeoJSON
        source_srid = None
        if "crs" in geojson_data:
            crs_props = geojson_data["crs"].get("properties", {})
            crs_name = crs_props.get("name", "")
            if "EPSG:2157" in crs_name:
                source_srid = 2157
            elif "EPSG:4326" in crs_name:
                source_srid = 4326

        imported = 0
        updated = 0
        errors = 0

        for feature in geojson_data.get("features", []):
            try:
                # Extract constituency name from properties
                properties = feature.get("properties", {})
                constituency_name = properties.get("ENG_NAME_VALUE", "").strip()

                if not constituency_name:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping feature with no ENG_NAME_VALUE property: {properties}"
                        )
                    )
                    continue

                # Convert GeoJSON geometry to GEOSGeometry.
                geometry = GEOSGeometry(json.dumps(feature["geometry"]))
                
                # Determine source SRID
                if source_srid:
                    # Use CRS from GeoJSON file
                    geometry.srid = source_srid
                elif geometry.srid is None:
                    # Detect by coordinate ranges if no CRS declared
                    try:
                        bounds = geometry.extent
                        x_min, y_min, x_max, y_max = bounds
                        # Irish Grid: X ~500k-800k, Y ~500k-800k (meters)
                        if (x_min > 100000 and x_max < 1000000 and 
                            y_min > 100000 and y_max < 1000000):
                            geometry.srid = 2157
                        else:
                            geometry.srid = 4326
                    except Exception:
                        # Default to Irish Grid for OSI data
                        geometry.srid = 2157
                
                # Transform to WGS84 if not already
                original_srid = geometry.srid
                if geometry.srid != 4326:
                    geometry.transform(4326)

                # Ensure it's a MultiPolygon (convert Polygon to MultiPolygon if needed)
                if geometry.geom_type == "Polygon":
                    geometry = MultiPolygon(geometry)

                # Create or update constituency
                constituency, created = DailConstituency.objects.update_or_create(
                    name=constituency_name,
                    defaults={"boundary": geometry},
                )

                if created:
                    imported += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error importing constituency {properties.get('ENG_NAME_VALUE', 'unknown')}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Dáil Constituencies: {imported} imported, {updated} updated, {errors} errors"
            )
        )
