from django.contrib import admin

from .models import RiskAssessment


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "latitude", "longitude", "level", "score")
    list_filter = ("level",)
