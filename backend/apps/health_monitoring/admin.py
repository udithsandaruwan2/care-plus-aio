from django.contrib import admin

from .models import HealthMetric


@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "kind", "value", "unit", "source", "recorded_at")
    list_filter = ("kind", "source")
    search_fields = ("patient__email", "kind", "source")
    readonly_fields = ("created_at",)

