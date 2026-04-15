"""Auth endpoints and council-only boundary APIs."""

import unittest

from django.conf import settings
from django.contrib.gis.geos import MultiPolygon, Polygon
from rest_framework import status
from rest_framework.test import APITestCase

from civicview.models import County, LocalCouncil, Profile
from civicview.tests.base import no_throttle
from civicview.tests.factories import create_token_user, create_user


@no_throttle
class AuthAPITests(APITestCase):
    def test_register_returns_token(self):
        r = self.client.post(
            "/api/auth/register/",
            {
                "username": "newuser_reg",
                "password": "ComplexPass123!",
                "email": "n@example.com",
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", r.data)
        self.assertEqual(r.data["username"], "newuser_reg")
        self.assertEqual(r.data["role"], Profile.ROLE_CITIZEN)

    def test_register_rejects_duplicate_username(self):
        self.client.post(
            "/api/auth/register/",
            {"username": "dupuser", "password": "ComplexPass123!"},
            format="json",
        )
        r = self.client.post(
            "/api/auth/register/",
            {"username": "dupuser", "password": "ComplexPass456!"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requires_token(self):
        r = self.client.get("/api/auth/me/")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_role(self):
        _, token = create_token_user("me_user", role=Profile.ROLE_STAFF)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/auth/me/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["role"], Profile.ROLE_STAFF)

    def test_login_returns_token(self):
        create_user("login_user", password="ComplexPass999!")
        r = self.client.post(
            "/api/auth/login/",
            {"username": "login_user", "password": "ComplexPass999!"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("token", r.data)

    def test_assignable_users_forbidden_for_staff(self):
        _, token = create_token_user("staff_assign", role=Profile.ROLE_STAFF)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/auth/assignable-users/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assignable_users_ok_for_manager(self):
        create_user("assignable_target", role=Profile.ROLE_STAFF)
        _, token = create_token_user("mgr_assign", role=Profile.ROLE_MANAGER)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/auth/assignable-users/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        usernames = [row["username"] for row in r.data]
        self.assertIn("assignable_target", usernames)


def _uses_postgis():
    engine = settings.DATABASES["default"].get("ENGINE", "")
    return "postgis" in engine


@unittest.skipUnless(
    _uses_postgis(),
    "County/constituency list uses PostGIS-specific geography SQL; run tests with PostGIS or skip.",
)
@no_throttle
class BoundaryAPITests(APITestCase):
    def setUp(self):
        poly = Polygon.from_bbox((-6.5, 53.2, -6.2, 53.5))
        self.county = County.objects.create(
            name=f"API_Test_County_{id(self)}",
            boundary=MultiPolygon(poly),
        )
        self.council = LocalCouncil.objects.create(
            name=f"API_Test_Council_{id(self)}",
            boundary=MultiPolygon(poly),
        )

    def test_counties_forbidden_for_citizen(self):
        _, token = create_token_user("cit_county", role=Profile.ROLE_CITIZEN)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/counties/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_counties_allowed_for_staff(self):
        _, token = create_token_user("staff_county", role=Profile.ROLE_STAFF)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/counties/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in r.data]
        self.assertIn(self.county.id, ids)

    def test_counties_minimal_query_returns_report_counts(self):
        _, token = create_token_user("staff_min", role=Profile.ROLE_STAFF)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/counties/", {"minimal": "1"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(x for x in r.data if x["id"] == self.county.id)
        self.assertIn("report_count", row)

    def test_councils_forbidden_for_citizen(self):
        _, token = create_token_user("cit_council", role=Profile.ROLE_CITIZEN)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/councils/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_councils_allowed_for_staff(self):
        _, token = create_token_user("staff_council", role=Profile.ROLE_STAFF)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        r = self.client.get("/api/councils/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [row["id"] for row in r.data]
        self.assertIn(self.council.id, ids)
