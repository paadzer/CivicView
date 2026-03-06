# ReportImage model for report photos (e.g. from mobile app)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("civicview", "0007_notification_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReportImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="report_images/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "report",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="civicview.report",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
