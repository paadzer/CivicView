# Create Staff and Managers groups for production-like access control

from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Staff")
    Group.objects.get_or_create(name="Managers")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("civicview", "0005_county_dailconstituency"),
    ]

    operations = [
        migrations.RunPython(create_groups, noop),
    ]
