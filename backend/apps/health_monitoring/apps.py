from django.apps import AppConfig


class HealthMonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.health_monitoring"
    label = "health_monitoring"
    verbose_name = "Health monitoring"

