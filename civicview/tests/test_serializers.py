"""ReportSerializer validation and workflow rules."""

from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from civicview.models import Profile, Report
from civicview.serializers import ReportSerializer
from civicview.tests.factories import create_report, create_user


class ReportSerializerValidationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def _context(self, user, method="POST"):
        if method == "GET":
            django_request = self.factory.get("/api/reports/1/")
        elif method == "PATCH":
            django_request = self.factory.patch("/api/reports/1/")
        else:
            django_request = self.factory.post("/api/reports/")
        django_request.method = method
        drf_request = Request(django_request)
        # Bypass DRF re-authentication (would reset to AnonymousUser for factory requests)
        drf_request._user = user  # noqa: SLF001
        return {"request": drf_request}

    def test_rejects_latitude_outside_ireland(self):
        user = create_user("cit1")
        serializer = ReportSerializer(
            data={
                "title": "x",
                "description": "y",
                "category": "Road",
                "latitude": 50.0,
                "longitude": -6.26,
            },
            context=self._context(user),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("latitude", serializer.errors)

    def test_rejects_longitude_outside_ireland(self):
        user = create_user("cit2")
        serializer = ReportSerializer(
            data={
                "title": "x",
                "description": "y",
                "category": "Road",
                "latitude": 53.35,
                "longitude": -4.0,
            },
            context=self._context(user),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("longitude", serializer.errors)

    def test_accepts_valid_ireland_point(self):
        user = create_user("cit3")
        serializer = ReportSerializer(
            data={
                "title": "Pothole",
                "description": "On main st",
                "category": "Potholes",
                "latitude": 53.3498,
                "longitude": -6.2603,
            },
            context=self._context(user),
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_citizen_cannot_set_status_on_create(self):
        user = create_user("cit4", role=Profile.ROLE_CITIZEN)
        serializer = ReportSerializer(
            data={
                "title": "x",
                "description": "y",
                "category": "Road",
                "latitude": 53.35,
                "longitude": -6.26,
                "status": Report.STATUS_RESOLVED,
            },
            context=self._context(user),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_staff_cannot_assign_without_manager_role(self):
        staff = create_user("staff1", role=Profile.ROLE_STAFF)
        assignee = create_user("assignee", role=Profile.ROLE_STAFF)
        report = create_report(user=create_user("owner2"))
        serializer = ReportSerializer(
            report,
            data={"assigned_to": assignee.pk},
            partial=True,
            context=self._context(staff, method="PATCH"),
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("assigned_to", serializer.errors)

    def test_read_geom_geojson(self):
        user = create_user("cit5")
        report = create_report(user=user)
        serializer = ReportSerializer(report, context=self._context(user, method="GET"))
        data = serializer.data
        self.assertEqual(data["geom"]["type"], "Point")
        self.assertAlmostEqual(data["geom"]["coordinates"][0], -6.2603, places=3)
        self.assertAlmostEqual(data["geom"]["coordinates"][1], 53.3498, places=3)
