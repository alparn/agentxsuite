"""
Admin configuration for accounts app.
"""
from django.contrib import admin

from apps.accounts.models import ServiceAccount, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Admin interface for User model."""

    list_display = ["email", "is_active", "is_staff", "is_superuser", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email"]
    ordering = ["-date_joined"]


@admin.register(ServiceAccount)
class ServiceAccountAdmin(admin.ModelAdmin):
    """Admin interface for ServiceAccount model."""

    list_display = ["name", "organization", "environment", "audience", "issuer", "enabled", "created_at"]
    list_filter = ["enabled", "organization", "environment"]
    search_fields = ["name", "audience", "issuer"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

