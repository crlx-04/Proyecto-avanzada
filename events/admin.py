from django.contrib import admin

from .models import Quake


@admin.register(Quake)
class QuakeAdmin(admin.ModelAdmin):
    list_display = ("time", "magnitude", "place")
    list_filter = ("magnitude",)
    search_fields = ("place",)
