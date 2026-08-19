"""Sentry, JSON logs, and Prometheus helpers (Step 73)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

_HTTP_REQUESTS = None
_HTTP_LATENCY = None


def init_sentry(
    *,
    dsn: str = "",
    environment: str = "development",
    traces_sample_rate: float = 0.0,
) -> bool:
    """Configure Sentry when ``dsn`` is set. No-op otherwise."""
    if not dsn:
        return False
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        traces_sample_rate=float(traces_sample_rate or 0.0),
        send_default_pii=False,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    return True


def _metrics():
    global _HTTP_REQUESTS, _HTTP_LATENCY
    from prometheus_client import Counter, Histogram

    if _HTTP_REQUESTS is None:
        _HTTP_REQUESTS = Counter(
            "careplus_http_requests_total",
            "HTTP requests",
            ["method", "path", "status"],
        )
        _HTTP_LATENCY = Histogram(
            "careplus_http_request_duration_seconds",
            "HTTP request latency",
            ["method", "path"],
            buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 0.8, 1.0, 2.5, 5.0),
        )
    return _HTTP_REQUESTS, _HTTP_LATENCY


def _route_label(path: str) -> str:
    """Collapse high-cardinality IDs so Prometheus cardinality stays bounded."""
    parts = [p for p in path.split("/") if p]
    cleaned: list[str] = []
    for part in parts[:8]:
        if part.isdigit() or (
            len(part) >= 8 and all(c in "0123456789abcdef-" for c in part.lower())
        ):
            cleaned.append(":id")
        else:
            cleaned.append(part[:48])
    return "/" + "/".join(cleaned) + ("/" if path.endswith("/") else "")


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line for journald / Docker json-file / Loki."""

    _RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
        "color_message",
        "msg",
        "args",
        "exc_info",
        "exc_text",
        "stack_info",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get() or getattr(record, "request_id", "")
        if rid:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key in payload:
                continue
            if key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestIdMetricsMiddleware(MiddlewareMixin):
    """Assign a request id, emit JSON-friendly extras, record Prometheus timings."""

    def process_request(self, request: HttpRequest) -> None:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        request.request_id = rid  # type: ignore[attr-defined]
        request._obs_start = time.perf_counter()  # type: ignore[attr-defined]

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        rid = getattr(request, "request_id", "") or request_id_var.get()
        if rid:
            response["X-Request-ID"] = rid
        path = request.path or "/"
        if path.startswith("/api/v1/metrics"):
            request_id_var.set("")
            return response
        start = getattr(request, "_obs_start", None)
        try:
            counter, hist = _metrics()
            label = _route_label(path)
            counter.labels(request.method, label, str(response.status_code)).inc()
            if start is not None:
                hist.labels(request.method, label).observe(time.perf_counter() - start)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).debug("metrics record failed", exc_info=True)
        request_id_var.set("")
        return response
