from django.contrib import admin

from .models import Alert, AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("zone", "kind", "threshold", "active", "user")
    list_filter = ("kind", "active")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("message", "severity", "seen", "created_at")
    list_filter = ("severity", "seen")
