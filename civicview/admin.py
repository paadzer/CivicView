# Import Django admin for model registration
from django.contrib import admin
from .models import Hotspot, Notification, Profile, Report, ReportImage


# Register Report model in Django admin interface
# Provides web-based UI for viewing and managing civic reports
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    # Columns displayed in the admin list view
    list_display = ("id", "title", "category", "created_by", "created_at")
    # Filters available in the sidebar for quick filtering
    list_filter = ("category", "created_at")
    # Fields searchable via the admin search box
    search_fields = ("title", "description")


# Register Hotspot model in Django admin interface
# Provides web-based UI for viewing hotspot clusters
@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):
    # Columns displayed in the admin list view
    list_display = ("id", "cluster_id", "created_at")
    # Filters available in the sidebar for quick filtering
    list_filter = ("cluster_id", "created_at")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "message", "report", "read_at", "created_at")
    list_filter = ("read_at", "created_at")
    search_fields = ("message",)


@admin.register(ReportImage)
class ReportImageAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "created_at")
    list_filter = ("created_at",)
