"""Test data factories (PostGIS-aware)."""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.authtoken.models import Token

from civicview.models import Profile, Report

User = get_user_model()

# Dublin city centre — valid Ireland coordinates for reports
DUBLIN_LAT = 53.3498
DUBLIN_LON = -6.2603


def point_wgs84(lon=DUBLIN_LON, lat=DUBLIN_LAT):
    return Point(lon, lat, srid=4326)


def create_user(username, password="TestPassword123!", role=Profile.ROLE_CITIZEN):
    user = User.objects.create_user(username=username, password=password)
    # post_save signal creates Profile(citizen); align role for tests
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"role": role})
    if profile.role != role:
        profile.role = role
        profile.save(update_fields=["role"])
    return user


def create_token_user(username, password="TestPassword123!", role=Profile.ROLE_CITIZEN):
    user = create_user(username, password, role)
    token, _ = Token.objects.get_or_create(user=user)
    return user, token


def create_report(
    title="Test issue",
    description="Desc",
    category="Road",
    user=None,
    lon=DUBLIN_LON,
    lat=DUBLIN_LAT,
    **kwargs,
):
    return Report.objects.create(
        title=title,
        description=description,
        category=category,
        geom=point_wgs84(lon, lat),
        created_by=user,
        **kwargs,
    )
