"""DBSCAN hotspot generation against a live PostGIS test database."""

from django.test import TestCase

from civicview.models import Hotspot, Report
from civicview.tasks import generate_hotspots
from civicview.tests.factories import point_wgs84


class GenerateHotspotsTests(TestCase):
    def test_no_reports_returns_summary(self):
        Report.objects.all().delete()
        Hotspot.objects.all().delete()
        result = generate_hotspots(days_back=None, eps_meters=500, min_samples=3)
        self.assertEqual(result["hotspots_created"], 0)
        self.assertEqual(result["total_reports"], 0)

    def test_insufficient_points_returns_no_hotspots(self):
        Report.objects.all().delete()
        Hotspot.objects.all().delete()
        Report.objects.create(
            title="Only one",
            description="x",
            category="Road",
            geom=point_wgs84(),
        )
        result = generate_hotspots(days_back=None, eps_meters=500, min_samples=5)
        self.assertEqual(result["hotspots_created"], 0)
        self.assertIn("error", result)

    def test_cluster_of_reports_produces_hotspot_polygon(self):
        Report.objects.all().delete()
        Hotspot.objects.all().delete()
        base_lon, base_lat = -6.2603, 53.3498
        for i in range(5):
            Report.objects.create(
                title=f"Cluster pt {i}",
                description="d",
                category="Road",
                geom=point_wgs84(base_lon + i * 0.00025, base_lat + i * 0.00025),
            )
        result = generate_hotspots(days_back=None, eps_meters=450, min_samples=3)
        self.assertGreaterEqual(result["hotspots_created"], 1)
        self.assertGreaterEqual(result["clusters_found"], 1)
        self.assertTrue(Hotspot.objects.exists())
