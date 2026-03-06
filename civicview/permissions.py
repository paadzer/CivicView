# Custom permissions for Report and Analytics
from rest_framework import permissions

from .models import Profile


def user_has_dashboard_role(user):
    """True if user can see analytics/dashboard (staff, council, manager, admin)."""
    if not user or not user.is_authenticated:
        return False
    if not hasattr(user, "profile"):
        return False
    return getattr(user.profile, "role", None) in Profile.DASHBOARD_ROLES


def user_has_manager_or_admin_role(user):
    """True if user can assign reports to others (manager, admin)."""
    if not user or not user.is_authenticated:
        return False
    if not hasattr(user, "profile"):
        return False
    return getattr(user.profile, "role", None) in Profile.CAN_ASSIGN_ROLES


# Kept for backward compatibility; now allows staff, council, manager, admin
def user_has_council_or_admin_role(user):
    """True if user has dashboard access (staff, council, manager, admin)."""
    return user_has_dashboard_role(user)


class IsCouncilOrAdmin(permissions.BasePermission):
    """Allow access only to users with dashboard role (staff, council, manager, admin)."""

    def has_permission(self, request, view):
        return user_has_dashboard_role(request.user)


class IsManagerOrAdmin(permissions.BasePermission):
    """Allow access only to users who can assign reports (manager, admin)."""

    def has_permission(self, request, view):
        return user_has_manager_or_admin_role(request.user)


class ReportPermission(permissions.BasePermission):
    """Read: anyone. Create: authenticated. Update/Delete: owner or moderator/staff/council/manager/admin."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == "POST":
            return request.user and request.user.is_authenticated
        if request.method in ("PUT", "PATCH", "DELETE"):
            return request.user and request.user.is_authenticated
        return False

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method in ("PUT", "PATCH", "DELETE", "POST"):
            # POST used for e.g. adding images to a report (detail action)
            if not request.user or not request.user.is_authenticated:
                return False
            if getattr(obj, "created_by", None) and obj.created_by_id == request.user.id:
                return True
            if hasattr(request.user, "profile"):
                return request.user.profile.role in Profile.WORKFLOW_ROLES
            return False
        return False
