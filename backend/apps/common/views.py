"""Health check: confirms the API, PostgreSQL, and Redis are reachable."""

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
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

    @extend_schema(
        summary="Health check",
        responses={200: None, 503: None},
    )
    def get(self, request):
        db = _check_db()
        cache = _check_redis()
        healthy = db == "ok" and cache == "ok"
        payload = {
            "status": "ok" if healthy else "degraded",
            "db": db,
            "redis": cache,
        }
        code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=code)
