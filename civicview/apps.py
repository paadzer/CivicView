from django.apps import AppConfig


class CivicviewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "civicview"

    def ready(self):
        import civicview.signals  # noqa: F401 - connect post_save to ensure Profile for User
