"""Step 70 — CORS lockdown, security headers, DRF throttles."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from django.contrib.auth import get_user_model

User = get_user_model()


@override_settings(
    DEBUG=False,
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["https://app.careplus.test"],
    CSRF_TRUSTED_ORIGINS=["https://app.careplus.test"],
)
class CorsLockdownTests(APITestCase):
    def test_allowed_origin_gets_aca_header(self):
        res = self.client.get(
            reverse("v1:health"),
            HTTP_ORIGIN="https://app.careplus.test",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Access-Control-Allow-Origin"], "https://app.careplus.test")

    def test_unknown_origin_has_no_aca_header(self):
        res = self.client.get(
            reverse("v1:health"),
            HTTP_ORIGIN="https://evil.example",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn("Access-Control-Allow-Origin", res)


class SecurityHeaderTests(TestCase):
    def test_base_security_flags(self):
        from django.conf import settings

        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(settings.SECURE_REFERRER_POLICY, "same-origin")
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class AuthThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(email="throttle@example.com", password="pw-strong-123")
        self.url = reverse("v1:token_obtain_pair")

    def test_auth_scope_returns_429(self):
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        payload = {"email": "throttle@example.com", "password": "wrong-password"}
        with patch.object(
            ScopedRateThrottle,
            "THROTTLE_RATES",
            {
                "auth": "2/min",
                "anon": "1000/min",
                "user": "1000/min",
                "match": "1000/min",
                "voice": "1000/min",
            },
        ):
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 401)
            self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 401)
            third = self.client.post(self.url, payload, format="json")
            self.assertEqual(third.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ProdSettingsSmokeTests(TestCase):
    def test_prod_module_has_tls_and_cors_closed(self):
        from django.conf import settings as live

        # Import prod module without activating it as DJANGO_SETTINGS_MODULE.
        import importlib

        prod = importlib.import_module("careplus.settings.prod")
        self.assertFalse(prod.DEBUG)
        self.assertTrue(prod.SECURE_SSL_REDIRECT)
        self.assertTrue(prod.SESSION_COOKIE_SECURE)
        self.assertGreaterEqual(prod.SECURE_HSTS_SECONDS, 31536000)
        self.assertFalse(prod.CORS_ALLOW_ALL_ORIGINS)
        self.assertEqual(prod.LOGGING["handlers"]["console"]["formatter"], "json")
        # Live settings still the test/dev module.
        self.assertTrue(hasattr(live, "REST_FRAMEWORK"))
        self.assertIn("auth", live.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])
