"""Step 73 — health extras, Prometheus metrics, Sentry no-op, JSON logs."""

import json
import logging

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.observability import JsonLogFormatter, _route_label, init_sentry


class HealthObservabilityTests(APITestCase):
    def test_health_includes_sentry_flag(self):
        res = self.client.get(reverse("v1:health"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(res.data["sentry"], ("on", "off"))
        self.assertTrue(res.has_header("X-Request-ID"))


class MetricsEndpointTests(APITestCase):
    def test_metrics_exposes_prometheus_text(self):
        self.client.get(reverse("v1:health"))
        res = self.client.get(reverse("v1:metrics"))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn("careplus_http_requests_total", body)
        self.assertTrue(res["Content-Type"].startswith("text/plain"))

    @override_settings(METRICS_TOKEN="secret-metrics")
    def test_metrics_requires_token_when_configured(self):
        res = self.client.get(reverse("v1:metrics"))
        self.assertEqual(res.status_code, 401)
        ok = self.client.get(reverse("v1:metrics"), HTTP_AUTHORIZATION="Bearer secret-metrics")
        self.assertEqual(ok.status_code, 200)


class ObservabilityHelpersTests(TestCase):
    def test_init_sentry_noop_without_dsn(self):
        self.assertFalse(init_sentry(dsn=""))

    def test_route_label_collapses_ids(self):
        self.assertEqual(_route_label("/api/v1/caregivers/42/"), "/api/v1/caregivers/:id/")

    def test_json_log_formatter_emits_object(self):
        record = logging.LogRecord(
            name="careplus.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        payload = json.loads(JsonLogFormatter().format(record))
        self.assertEqual(payload["msg"], "hello world")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "careplus.test")

    def test_json_log_formatter_includes_extra_and_request_id(self):
        record = logging.LogRecord(
            name="apps.voice.timings",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="voice.turn.timings",
            args=(),
            exc_info=None,
        )
        record.asr_ms = 12
        record.total_ms = 40
        record.request_id = "abc123"
        payload = json.loads(JsonLogFormatter().format(record))
        self.assertEqual(payload["asr_ms"], 12)
        self.assertEqual(payload["total_ms"], 40)
        self.assertEqual(payload["request_id"], "abc123")
