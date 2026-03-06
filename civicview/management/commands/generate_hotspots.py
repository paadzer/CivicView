# Import Django management command base class
from django.core.management.base import BaseCommand

# Import the hotspot generation task function
from civicview.tasks import generate_hotspots


# Management command: Allows running hotspot generation from command line
# Usage: python manage.py generate_hotspots [--days-back=30] [--all-time] [--eps=250] [--min-samples=5]
class Command(BaseCommand):
    # Help text displayed when running: python manage.py help generate_hotspots
    help = "Generate hotspots from existing reports using DBSCAN clustering"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-back",
            type=int,
            default=30,
            help="Number of days to look back for reports (default: 30)",
        )
        parser.add_argument(
            "--all-time",
            action="store_true",
            help="Use all reports regardless of date (overrides --days-back)",
        )
        parser.add_argument(
            "--eps",
            type=float,
            default=None,
            help="DBSCAN eps parameter in meters (default: 250)",
        )
        parser.add_argument(
            "--min-samples",
            type=int,
            default=None,
            help="DBSCAN min_samples parameter (default: 5)",
        )

    # Main command handler: Executed when command is run
    def handle(self, *args, **options):
        days_back = None if options["all_time"] else options["days_back"]
        eps = options["eps"]
        min_samples = options["min_samples"]
        
        # Call the hotspot generation function (runs synchronously, not via Celery)
        result = generate_hotspots(
            days_back=days_back,
            eps_meters=eps,
            min_samples=min_samples,
        )
        
        # Display success message with statistics
        time_info = "all time" if days_back is None else f"last {days_back} days"
        self.stdout.write(
            self.style.SUCCESS(
                f"Hotspots generated: {result['hotspots_created']} clusters "
                f"from {result['total_reports']} reports "
                f"({time_info}, {result['noise_points']} noise points excluded)"
            )
        )
        self.stdout.write(
            f"  Parameters: eps={result['eps_meters']}m, min_samples={result['min_samples']}"
        )
        
        if "error" in result:
            self.stdout.write(self.style.ERROR(f"  Error: {result['error']}"))


