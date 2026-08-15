from django.urls import path

from .views import HealthView, MetricsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("metrics/", MetricsView.as_view(), name="metrics"),
]
