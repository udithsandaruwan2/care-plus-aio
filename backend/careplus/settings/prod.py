"""Production settings (Step 70 hardened transport + cookies)."""

from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Never allow mock confirm in production.
MOCK_PAYMENT_CONFIRM_ENABLED = False

# Fail closed: do not allow all CORS origins when DEBUG is off.
CORS_ALLOW_ALL_ORIGINS = False
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    _frontend = FRONTEND_BASE_URL.rstrip("/")  # noqa: F405
    if _frontend.startswith("http"):
        CORS_ALLOWED_ORIGINS = [_frontend]  # noqa: F405
if not CSRF_TRUSTED_ORIGINS and CORS_ALLOWED_ORIGINS:  # noqa: F405
    CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)  # noqa: F405
