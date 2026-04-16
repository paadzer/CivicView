# Django management command to import GeoJSON boundary files into County and DailConstituency models
import json
import os

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand

from civicview.models import County, DailConstituency, LocalCouncil


class Command(BaseCommand):
    help = "Import GeoJSON boundary files for counties, local councils and Dáil constituencies"

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
            "--councils",
            type=str,
            default="civicview/data/boundaries/local_councils_ireland.geojson",
            help="Path to local councils GeoJSON file",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing boundaries before importing",
        )

    def handle(self, *args, **options):
        counties_path = options["counties"]
        constituencies_path = options["constituencies"]
        councils_path = options["councils"]
        clear_existing = options["clear"]

        # Clear existing data if requested
        if clear_existing:
            self.stdout.write("Clearing existing boundaries...")
            County.objects.all().delete()
            DailConstituency.objects.all().delete()
            LocalCouncil.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Cleared existing boundaries"))

        # Import counties
        if os.path.exists(counties_path):
            self.stdout.write(f"Importing counties from {counties_path}...")
            self._import_counties(counties_path)
        else:
            self.stdout.write(
                self.style.WARNING(f"Counties file not found: {counties_path}")
            )

        # Import local councils
        if os.path.exists(councils_path):
            self.stdout.write(f"Importing local councils from {councils_path}...")
            self._import_councils(councils_path)
        else:
            self.stdout.write(
                self.style.WARNING(f"Councils file not found: {councils_path}")
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
                # Force 2D coordinates so we can store into 2D PostGIS columns.
                geometry_data = {
                    **feature["geometry"],
                    "coordinates": self._strip_z_from_coordinates(
                        feature["geometry"].get("coordinates")
                    ),
                }
                geometry = GEOSGeometry(json.dumps(geometry_data))
                
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
                # Force 2D coordinates so we can store into 2D PostGIS columns.
                geometry_data = {
                    **feature["geometry"],
                    "coordinates": self._strip_z_from_coordinates(
                        feature["geometry"].get("coordinates")
                    ),
                }
                geometry = GEOSGeometry(json.dumps(geometry_data))
                
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

    def _import_councils(self, file_path):
        """Import local council boundaries from GeoJSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

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
        council_parts = {}

        for feature in geojson_data.get("features", []):
            properties = feature.get("properties", {})
            try:
                # Support common field names used in local authority datasets.
                council_name = (
                    properties.get("ENG_NAME_VALUE")
                    or properties.get("COUNCIL")
                    or properties.get("NAME")
                    or properties.get("name")
                    or ""
                ).strip()

                if not council_name:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping feature with no council name property: {properties}"
                        )
                    )
                    continue

                geometry_data = {
                    **feature["geometry"],
                    "coordinates": self._strip_z_from_coordinates(
                        feature["geometry"].get("coordinates")
                    ),
                }
                geometry = GEOSGeometry(json.dumps(geometry_data))

                if source_srid:
                    geometry.srid = source_srid
                elif geometry.srid is None:
                    try:
                        x_min, y_min, x_max, y_max = geometry.extent
                        if (
                            x_min > 100000
                            and x_max < 1000000
                            and y_min > 100000
                            and y_max < 1000000
                        ):
                            geometry.srid = 2157
                        else:
                            geometry.srid = 4326
                    except Exception:
                        geometry.srid = 2157

                if geometry.srid != 4326:
                    geometry.transform(4326)

                # Collect polygon parts for later dissolve/merge by council.
                council_parts.setdefault(council_name, []).append(geometry)

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error reading council feature {properties.get('ENG_NAME_VALUE', properties.get('NAME', 'unknown'))}: {str(e)}"
                    )
                )

        # Dissolve all parts per council into one MultiPolygon boundary.
        for council_name, parts in council_parts.items():
            try:
                dissolved = parts[0]
                for part in parts[1:]:
                    dissolved = dissolved.union(part)

                if dissolved.geom_type == "Polygon":
                    dissolved = MultiPolygon(dissolved)
                elif dissolved.geom_type != "MultiPolygon":
                    polygons = [g for g in getattr(dissolved, "geoms", []) if g.geom_type == "Polygon"]
                    if not polygons:
                        raise ValueError(f"Unsupported dissolved geometry type: {dissolved.geom_type}")
                    dissolved = MultiPolygon(*polygons)

                _, created = LocalCouncil.objects.update_or_create(
                    name=council_name,
                    defaults={"boundary": dissolved},
                )
                if created:
                    imported += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"Error dissolving council {council_name}: {str(e)}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Local Councils: {imported} imported, {updated} updated, {errors} errors"
            )
        )

    def _strip_z_from_coordinates(self, coords):
        """
        Recursively drop Z values from GeoJSON coordinate arrays.
        Converts [x, y, z] -> [x, y] while preserving Polygon/MultiPolygon nesting.
        """
        if not isinstance(coords, (list, tuple)):
            return coords
        if len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords[:2]):
            return [coords[0], coords[1]]
        return [self._strip_z_from_coordinates(c) for c in coords]
