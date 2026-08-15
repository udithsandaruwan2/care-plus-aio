"""Health check: confirms the API, PostgreSQL, and Redis are reachable."""

import redis
from django.conf import settings
from django.db import connection
from django.http import HttpResponse
from django.views import View
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def _check_db() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


def _check_redis() -> str:
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        return "ok" if client.ping() else "error"
    except Exception:  # noqa: BLE001
        return "error"


class HealthView(APIView):
    """GET /api/v1/health/ — liveness + dependency readiness."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        db = _check_db()
        cache = _check_redis()
        healthy = db == "ok" and cache == "ok"
        payload = {
            "status": "ok" if healthy else "degraded",
            "db": db,
            "redis": cache,
            "sentry": "on" if getattr(settings, "SENTRY_DSN", "") else "off",
        }
        code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=code)


def _metrics_authorized(request) -> bool:
    token = getattr(settings, "METRICS_TOKEN", "") or ""
    if not token:
        return True
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer ") and header[7:] == token:
        return True
    return request.headers.get("X-Metrics-Token", "") == token


class MetricsView(View):
    """GET /api/v1/metrics/ — Prometheus text. Optional ``METRICS_TOKEN``."""

    def get(self, request):
        if not _metrics_authorized(request):
            return HttpResponse("unauthorized\n", status=401, content_type="text/plain")
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
