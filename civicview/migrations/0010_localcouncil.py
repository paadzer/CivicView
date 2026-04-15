from django.contrib.gis.db import models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("civicview", "0009_report_supporters_alter_profile_role_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LocalCouncil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, unique=True)),
                ("boundary", models.MultiPolygonField(srid=4326)),
            ],
            options={
                "verbose_name": "local council",
                "verbose_name_plural": "local councils",
            },
        ),
        migrations.AddIndex(
            model_name="localcouncil",
            index=models.Index(fields=["name"], name="local_council_name_idx"),
        ),
    ]
