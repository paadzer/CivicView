# Time-based and category filtering for Report list
from datetime import timedelta

import django_filters
from django.utils import timezone

from .analytics_views import get_reports_within_boundary
from .models import County, DailConstituency, LocalCouncil, Report


# Preset period values for "Filter by time" (historical / timestamp filtering)
PERIOD_LAST_HOUR = "last_hour"
PERIOD_LAST_24H = "last_24h"
PERIOD_YESTERDAY = "yesterday"
PERIOD_LAST_7_DAYS = "last_7_days"
PERIOD_LAST_30_DAYS = "last_30_days"

PERIOD_CHOICES = [
    ("", "All time"),
    (PERIOD_LAST_HOUR, "Last hour"),
    (PERIOD_LAST_24H, "Last 24 hours"),
    (PERIOD_YESTERDAY, "Yesterday"),
    (PERIOD_LAST_7_DAYS, "Last 7 days"),
    (PERIOD_LAST_30_DAYS, "Last 30 days"),
]


def get_period_range(period):
    """
    Return (created_after, created_before) for a preset period, in server timezone.
    Both are timezone-aware datetimes; created_before is typically timezone.now().
    """
    now = timezone.now()
    if period == PERIOD_LAST_HOUR:
        return (now - timedelta(hours=1), now)
    if period == PERIOD_LAST_24H:
        return (now - timedelta(hours=24), now)
    if period == PERIOD_YESTERDAY:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start - timedelta(microseconds=1)
        return (yesterday_start, yesterday_end)
    if period == PERIOD_LAST_7_DAYS:
        return (now - timedelta(days=7), now)
    if period == PERIOD_LAST_30_DAYS:
        return (now - timedelta(days=30), now)
    return (None, None)


class ReportFilter(django_filters.FilterSet):
    """Category + status + time range + geographic (county/constituency) filters."""

    category = django_filters.CharFilter(field_name="category", lookup_expr="exact")
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    period = django_filters.TypedChoiceFilter(
        choices=PERIOD_CHOICES,
        empty_value=None,
        method="filter_period",
    )
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )
    in_county = django_filters.NumberFilter(method="filter_in_county")
    in_constituency = django_filters.NumberFilter(method="filter_in_constituency")
    in_council = django_filters.NumberFilter(method="filter_in_council")

    class Meta:
        model = Report
        fields = [
            "category",
            "status",
            "period",
            "created_after",
            "created_before",
            "in_county",
            "in_constituency",
            "in_council",
        ]

    def filter_period(self, queryset, name, value):
        if not value:
            return queryset
        created_after, created_before = get_period_range(value)
        if created_after is not None:
            queryset = queryset.filter(created_at__gte=created_after)
        if created_before is not None:
            queryset = queryset.filter(created_at__lte=created_before)
        return queryset

    def filter_in_county(self, queryset, name, value):
        if value is None:
            return queryset
        county = County.objects.filter(pk=value).first()
        if not county or not county.boundary:
            return queryset.none()
        report_ids = get_reports_within_boundary(county.boundary).values_list("id", flat=True)
        return queryset.filter(id__in=report_ids)

    def filter_in_constituency(self, queryset, name, value):
        if value is None:
            return queryset
        constituency = DailConstituency.objects.filter(pk=value).first()
        if not constituency or not constituency.boundary:
            return queryset.none()
        report_ids = get_reports_within_boundary(constituency.boundary).values_list("id", flat=True)
        return queryset.filter(id__in=report_ids)

    def filter_in_council(self, queryset, name, value):
        if value is None:
            return queryset
        council = LocalCouncil.objects.filter(pk=value).first()
        if not council or not council.boundary:
            return queryset.none()
        report_ids = get_reports_within_boundary(council.boundary).values_list("id", flat=True)
        return queryset.filter(id__in=report_ids)
