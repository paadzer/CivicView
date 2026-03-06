from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Report",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("category", models.CharField(max_length=100)),
                ("geom", django.contrib.gis.db.models.fields.PointField(srid=4326)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"indexes": [models.Index(fields=["created_at"], name="report_created_at_idx")]},
        ),
        migrations.CreateModel(
            name="Hotspot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cluster_id", models.IntegerField()),
                ("geom", django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["cluster_id"], name="hotspot_cluster_idx"),
                    models.Index(fields=["created_at"], name="hotspot_created_idx"),
                ]
            },
        ),
    ]

