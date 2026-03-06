# Import standard library
import os

# Import Celery for asynchronous task processing
from celery import Celery

# Set Django settings module so Celery can access Django configuration
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "civicview_project.settings")

# Create Celery application instance
app = Celery("civicview_project")
# Load Celery configuration from Django settings (looks for CELERY_* prefixed settings)
app.config_from_object("django.conf:settings", namespace="CELERY")
# Automatically discover tasks from all installed Django apps
# This finds tasks decorated with @shared_task or @app.task
app.autodiscover_tasks()


# Debug task: Useful for testing Celery worker connectivity
@app.task(bind=True)
def debug_task(self):
    # Print task request information for debugging
    print(f"Request: {self.request!r}")


