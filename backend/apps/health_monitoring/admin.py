from django.contrib import admin

from .models import HealthEvent, HealthMetric


@admin.register(HealthMetric)
class HealthMetricAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "kind", "value", "unit", "source", "recorded_at")
    list_filter = ("kind", "source")
    search_fields = ("patient__email", "kind", "source")
    readonly_fields = ("created_at", "metadata")


@admin.register(HealthEvent)
class HealthEventAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "event_type", "kind", "rule_key", "window_end", "created_at")
    list_filter = ("event_type", "kind", "rule_key", "severity")
    search_fields = ("patient__email", "event_type", "rule_key")
    readonly_fields = ("created_at", "payload")

