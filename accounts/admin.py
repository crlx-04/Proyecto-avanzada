from django.contrib import admin

from .models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "latitude", "longitude", "radius_km")
    list_filter = ("user",)
