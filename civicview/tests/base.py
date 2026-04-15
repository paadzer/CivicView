"""Shared helpers and settings overrides for API tests."""

from django.conf import settings
from django.test import override_settings

# Disable DRF throttling in tests (avoids flaky 429s when many requests run quickly).
REST_FRAMEWORK_TEST = {
    **getattr(settings, "REST_FRAMEWORK", {}),
    "DEFAULT_THROTTLE_CLASSES": [],
}

no_throttle = override_settings(REST_FRAMEWORK=REST_FRAMEWORK_TEST)
