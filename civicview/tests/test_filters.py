"""Report filter period helper behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from civicview.filters import PERIOD_LAST_7_DAYS, get_period_range


class PeriodFilterTests(TestCase):
    def test_last_7_days_range(self):
        after, before = get_period_range(PERIOD_LAST_7_DAYS)
        self.assertIsNotNone(after)
        self.assertIsNotNone(before)
        self.assertLess(after, before)
        self.assertGreater(timezone.now() - after, timedelta(days=6, hours=23))

    def test_empty_period_returns_none_tuple(self):
        after, before = get_period_range("")
        self.assertIsNone(after)
        self.assertIsNone(before)
