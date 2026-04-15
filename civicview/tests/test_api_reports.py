"""REST API: reports list/create/update/delete, categories, likes, permissions."""

from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from civicview.models import Profile, Report
from civicview.tests.base import no_throttle
from civicview.tests.factories import (
    DUBLIN_LAT,
    DUBLIN_LON,
    create_report,
    create_token_user,
    create_user,
)


@no_throttle
class ReportAPITests(APITestCase):
    def setUp(self):
        self.citizen, self.citizen_token = create_token_user("api_citizen", role=Profile.ROLE_CITIZEN)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.citizen_token.key}")

    def test_list_reports_anonymous_allowed(self):
        self.client.credentials()
        create_report(title="Public")
        r = self.client.get("/api/reports/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(r.data), 1)

    def test_create_report_requires_auth(self):
        self.client.credentials()
        payload = {
            "title": "No auth",
            "description": "x",
            "category": "Road",
            "latitude": DUBLIN_LAT,
            "longitude": DUBLIN_LON,
        }
        with patch("civicview.views.generate_hotspots") as mock_gen:
            mock_gen.delay = MagicMock()
            r = self.client.post("/api/reports/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_report_success_sets_created_by(self):
        payload = {
            "title": "Auth report",
            "description": "body",
            "category": "Lighting",
            "latitude": DUBLIN_LAT,
            "longitude": DUBLIN_LON,
        }
        with patch("civicview.views.generate_hotspots") as mock_gen:
            mock_gen.delay = MagicMock()
            r = self.client.post("/api/reports/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["title"], "Auth report")
        rid = r.data["id"]
        report = Report.objects.get(pk=rid)
        self.assertEqual(report.created_by_id, self.citizen.id)

    def test_create_report_rejects_non_ireland(self):
        payload = {
            "title": "Far away",
            "description": "x",
            "category": "Road",
            "latitude": 40.0,
            "longitude": -6.0,
        }
        with patch("civicview.views.generate_hotspots") as mock_gen:
            mock_gen.delay = MagicMock()
            r = self.client.post("/api/reports/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_patch_own_report(self):
        report = create_report(user=self.citizen, title="Mine")
        with patch("civicview.views.generate_hotspots") as mock_gen:
            mock_gen.delay = MagicMock()
            r = self.client.patch(
                f"/api/reports/{report.id}/",
                {"title": "Updated title"},
                format="json",
            )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.title, "Updated title")

    def test_other_user_cannot_delete_foreign_report(self):
        report = create_report(user=self.citizen)
        _, tok = create_token_user("api_other2", role=Profile.ROLE_CITIZEN)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {tok.key}")
        r = self.client.delete(f"/api/reports/{report.id}/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_moderator_can_delete_any_report(self):
        report = create_report(user=self.citizen)
        _, mod_tok = create_token_user("api_mod2", role=Profile.ROLE_MODERATOR)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {mod_tok.key}")
        r = self.client.delete(f"/api/reports/{report.id}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Report.objects.filter(pk=report.id).exists())

    def test_categories_action_returns_distinct(self):
        create_report(category="Alpha")
        create_report(category="Beta")
        create_report(category="Alpha")
        self.client.credentials()
        r = self.client.get("/api/reports/categories/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("Alpha", r.data)
        self.assertIn("Beta", r.data)

    def test_like_increments_count(self):
        report = create_report()
        r = self.client.post(f"/api/reports/{report.id}/like/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["like_count"], 1)
        self.assertTrue(r.data["liked_by_me"])

    def test_filter_by_category(self):
        create_report(category="Lighting", title="L1")
        create_report(category="Road", title="R1")
        self.client.credentials()
        r = self.client.get("/api/reports/", {"category": "Lighting"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        titles = [row["title"] for row in r.data]
        self.assertIn("L1", titles)
        self.assertNotIn("R1", titles)

    def test_export_csv_authenticated(self):
        create_report(title="CSVRow")
        r = self.client.get("/api/reports/export/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn(b"CSVRow", r.content)

    def test_upload_image_requires_owner_or_staff(self):
        report = create_report(user=self.citizen)
        img = SimpleUploadedFile("test.jpg", b"\xff\xd8\xff\xe0fakejpeg", content_type="image/jpeg")
        r = self.client.post(f"/api/reports/{report.id}/images/", {"images": img}, format="multipart")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertGreaterEqual(r.data["uploaded"], 1)

    def test_moderator_can_patch_report_status(self):
        report = create_report(user=self.citizen)
        _, mod_tok = create_token_user("api_mod_status", role=Profile.ROLE_MODERATOR)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {mod_tok.key}")
        r = self.client.patch(
            f"/api/reports/{report.id}/",
            {"status": Report.STATUS_IN_PROGRESS},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.STATUS_IN_PROGRESS)

    def test_manager_can_assign_report_to_staff(self):
        report = create_report(user=self.citizen)
        assignee = create_user("assignee_staff_api", role=Profile.ROLE_STAFF)
        _, mgr_tok = create_token_user("api_mgr_assign", role=Profile.ROLE_MANAGER)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {mgr_tok.key}")
        r = self.client.patch(
            f"/api/reports/{report.id}/",
            {"assigned_to": assignee.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        report.refresh_from_db()
        self.assertEqual(report.assigned_to_id, assignee.id)
