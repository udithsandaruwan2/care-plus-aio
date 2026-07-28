from django.urls import path

from .views import HealthMetricIngestView, HealthMetricWindowView

urlpatterns = [
    path("health/metrics/ingest/", HealthMetricIngestView.as_view(), name="health_metric_ingest"),
    path("health/metrics/window/", HealthMetricWindowView.as_view(), name="health_metric_window"),
]

