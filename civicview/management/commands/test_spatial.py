# Django management command to test spatial queries and diagnose why reports show 0
from django.core.management.base import BaseCommand

from civicview.models import County, DailConstituency, Report


class Command(BaseCommand):
    help = "Test spatial queries to diagnose why report counts are showing 0"

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("SPATIAL QUERY DIAGNOSTIC")
        self.stdout.write("=" * 70)
        
        # Check total reports
        total_reports = Report.objects.count()
        self.stdout.write(f"\n✓ Total reports in database: {total_reports}")
        
        if total_reports == 0:
            self.stdout.write(self.style.WARNING("\n⚠ No reports found! Please seed reports first."))
            return
        
        # Show sample report coordinates
        sample_report = Report.objects.first()
        if sample_report:
            self.stdout.write(f"\n✓ Sample report:")
            self.stdout.write(f"  - ID: {sample_report.id}")
            self.stdout.write(f"  - Title: {sample_report.title}")
            self.stdout.write(f"  - Location SRID: {sample_report.geom.srid}")
            self.stdout.write(f"  - Coordinates: ({sample_report.geom.x}, {sample_report.geom.y})")
            self.stdout.write(f"  - Valid: {sample_report.geom.valid}")
        
        # Check counties
        county_count = County.objects.count()
        self.stdout.write(f"\n✓ Total counties: {county_count}")
        
        if county_count == 0:
            self.stdout.write(self.style.WARNING("\n⚠ No counties found! Please run: python manage.py import_boundaries"))
            return
        
        # Test Dublin county specifically
        dublin = County.objects.filter(name__icontains="DUBLIN").first()
        if dublin:
            self.stdout.write(f"\n{'=' * 70}")
            self.stdout.write(f"TESTING DUBLIN COUNTY")
            self.stdout.write(f"{'=' * 70}")
            self.stdout.write(f"✓ Found: {dublin.name}")
            self.stdout.write(f"  - Boundary SRID: {dublin.boundary.srid}")
            self.stdout.write(f"  - Boundary type: {dublin.boundary.geom_type}")
            self.stdout.write(f"  - Boundary valid: {dublin.boundary.valid}")
            
            # Get boundary bounds
            try:
                bounds = dublin.boundary.extent
                self.stdout.write(f"  - Boundary extent: {bounds}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  - Error getting extent: {e}"))
            
            # Test spatial query
            self.stdout.write(f"\n  Testing spatial query: Report.objects.filter(geom__intersects=dublin.boundary)")
            try:
                reports_in_dublin = Report.objects.filter(geom__intersects=dublin.boundary)
                count = reports_in_dublin.count()
                self.stdout.write(f"  ✓ Reports intersecting Dublin boundary: {count}")
                
                if count == 0:
                    self.stdout.write(self.style.WARNING("\n  ⚠ No reports found! Testing alternatives..."))
                    
                    # Test if reports are near Dublin center
                    from django.contrib.gis.geos import Point
                    dublin_center = Point(-6.2603, 53.3498, srid=4326)
                    nearby_reports = Report.objects.filter(geom__distance_lte=(dublin_center, 50000))  # 50km
                    nearby_count = nearby_reports.count()
                    self.stdout.write(f"  - Reports within 50km of Dublin center: {nearby_count}")
                    
                    # Test contains query
                    try:
                        contains_count = Report.objects.filter(geom__within=dublin.boundary).count()
                        self.stdout.write(f"  - Reports using 'within' query: {contains_count}")
                    except Exception as e:
                        self.stdout.write(f"  - Error with 'within' query: {e}")
                    
                    # Check if sample report is inside boundary
                    if sample_report:
                        try:
                            is_inside = dublin.boundary.contains(sample_report.geom)
                            self.stdout.write(f"\n  Testing sample report:")
                            self.stdout.write(f"    - Sample report coords: ({sample_report.geom.x}, {sample_report.geom.y})")
                            self.stdout.write(f"    - Is inside Dublin boundary: {is_inside}")
                            
                            # Try reverse check
                            intersects_reverse = sample_report.geom.intersects(dublin.boundary)
                            self.stdout.write(f"    - Sample report intersects boundary: {intersects_reverse}")
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"    - Error testing sample: {e}"))
                else:
                    # Show some examples
                    self.stdout.write(f"\n  ✓ Found {count} reports! Sample IDs:")
                    for r in reports_in_dublin[:5]:
                        self.stdout.write(f"    - Report {r.id}: {r.title} at ({r.geom.x}, {r.geom.y})")
                        
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Error running spatial query: {e}"))
                import traceback
                self.stdout.write(traceback.format_exc())
        else:
            self.stdout.write(self.style.ERROR("\n✗ Dublin county not found!"))
        
        # Test a few more counties
        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write("TESTING OTHER COUNTIES")
        self.stdout.write(f"{'=' * 70}")
        for county in County.objects.all()[:5]:
            try:
                count = Report.objects.filter(geom__intersects=county.boundary).count()
                status = "✓" if count > 0 else "⚠"
                self.stdout.write(f"{status} {county.name}: {count} reports")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ {county.name}: Error - {e}"))
        
        # Test constituencies
        constituency_count = DailConstituency.objects.count()
        self.stdout.write(f"\n✓ Total constituencies: {constituency_count}")
        
        if constituency_count > 0:
            self.stdout.write(f"\n{'=' * 70}")
            self.stdout.write("TESTING DUBLIN CONSTITUENCIES")
            self.stdout.write(f"{'=' * 70}")
            dublin_constituencies = DailConstituency.objects.filter(name__icontains="Dublin")[:3]
            for constituency in dublin_constituencies:
                try:
                    count = Report.objects.filter(geom__intersects=constituency.boundary).count()
                    status = "✓" if count > 0 else "⚠"
                    self.stdout.write(f"{status} {constituency.name}: {count} reports")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ {constituency.name}: Error - {e}"))
        
        self.stdout.write(f"\n{'=' * 70}")
        self.stdout.write("DIAGNOSTIC COMPLETE")
        self.stdout.write(f"{'=' * 70}")
