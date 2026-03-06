# Ensure every User has a Profile and sync Profile.role to Django groups (Staff / Managers)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .models import Profile

User = get_user_model()

STAFF_GROUP_NAME = "Staff"
MANAGERS_GROUP_NAME = "Managers"


def _ensure_groups_exist():
    Group.objects.get_or_create(name=STAFF_GROUP_NAME)
    Group.objects.get_or_create(name=MANAGERS_GROUP_NAME)


def sync_profile_to_groups(profile):
    """Add user to Staff and/or Managers group based on Profile.role."""
    if not profile or not profile.user_id:
        return
    user = profile.user
    staff_group = Group.objects.filter(name=STAFF_GROUP_NAME).first()
    managers_group = Group.objects.filter(name=MANAGERS_GROUP_NAME).first()
    if not staff_group:
        staff_group = Group.objects.create(name=STAFF_GROUP_NAME)
    if not managers_group:
        managers_group = Group.objects.create(name=MANAGERS_GROUP_NAME)

    in_staff = profile.role in Profile.ASSIGNABLE_ROLES  # staff, council, manager
    in_managers = profile.role == Profile.ROLE_MANAGER or profile.role == Profile.ROLE_ADMIN

    if in_staff and staff_group not in user.groups.all():
        user.groups.add(staff_group)
    elif not in_staff and staff_group in user.groups.all():
        user.groups.remove(staff_group)

    if in_managers and managers_group not in user.groups.all():
        user.groups.add(managers_group)
    elif not in_managers and managers_group in user.groups.all():
        user.groups.remove(managers_group)


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance, defaults={"role": Profile.ROLE_CITIZEN})


@receiver(post_save, sender=Profile)
def sync_profile_groups(sender, instance, **kwargs):
    sync_profile_to_groups(instance)
