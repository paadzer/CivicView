"""Hotspot list and regenerate endpoint."""

from rest_framework import status
from rest_framework.test import APITestCase

from civicview.models import Hotspot, Report
from civicview.tests.base import no_throttle
from civicview.tests.factories import create_report, create_token_user


@no_throttle
class HotspotAPITests(APITestCase):
    def test_list_hotspots_anonymous_ok(self):
        r = self.client.get("/api/hotspots/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_regenerate_requires_authentication(self):
        r = self.client.post("/api/hotspots/regenerate/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regenerate_returns_summary_json(self):
        _, token = create_token_user("hotspot_regen_user")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        Report.objects.all().delete()
        Hotspot.objects.all().delete()
        create_report(title="solo")
        r = self.client.post(
            "/api/hotspots/regenerate/?all_time=true&eps=500&min_samples=5",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("hotspots_created", r.data)
        self.assertIn("total_reports", r.data)
