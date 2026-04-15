"""
Run offline system evaluation metrics (JSON to stdout).

Examples:
  python manage.py evaluate_system
  python manage.py evaluate_system --include-db-counts
"""

import json

from django.core.management.base import BaseCommand
from django.db.models import Count

from civicview.evaluation.metrics import (
    coordinate_validation_matrix,
    run_synthetic_clustering_evaluation,
)
from civicview.models import Hotspot, Report


class Command(BaseCommand):
    help = "Output JSON evaluation report (synthetic clustering + coordinate validation; optional DB counts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-db-counts",
            action="store_true",
            help="Include current Report/Hotspot counts from the configured database (read-only).",
        )

    def handle(self, *args, **options):
        payload = {
            "synthetic_dbscan": run_synthetic_clustering_evaluation(),
            "coordinate_validation": coordinate_validation_matrix(),
        }
        if options["include_db_counts"]:
            payload["database_counts"] = {
                "reports": Report.objects.count(),
                "hotspots": Hotspot.objects.count(),
                "reports_by_status": dict(
                    Report.objects.values("status").annotate(n=Count("id")).values_list("status", "n")
                ),
            }
        self.stdout.write(json.dumps(payload, indent=2))
