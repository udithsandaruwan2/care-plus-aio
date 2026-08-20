"""Base settings shared across environments.

Lean profile: one PostgreSQL instance (PostGIS + TimescaleDB), one Redis
(cache + Redlock + Celery broker + Channels layer). See docs/ARCHITECTURE.md.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)

# Prefer a mounted ``/app/.env`` (see docker-compose) so Gemini keys update
# without ``docker compose up --force-recreate``.
for _env_path in (Path("/app/.env"), BASE_DIR.parent / ".env", BASE_DIR / ".env"):
    if _env_path.is_file():
        environ.Env.read_env(str(_env_path), overwrite=True)
        break

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ── Applications ─────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",  # GeoDjango (PostGIS)
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.common",
    "apps.voice",
    "apps.matching",
    "apps.vocab",
    "apps.leads",
    "apps.catalog",
    "apps.medical_records",
    "apps.messaging",
    "apps.health_monitoring",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.common.observability.RequestIdMetricsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves admin / DRF Browsable API CSS/JS under uvicorn (runserver
    # is the only Django server that serves static files itself in DEBUG).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "careplus.urls"
WSGI_APPLICATION = "careplus.wsgi.application"
ASGI_APPLICATION = "careplus.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── Database (PostGIS backend on the TimescaleDB image) ──────────
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("POSTGRES_DB", default="careplus"),
        "USER": env("POSTGRES_USER", default="careplus"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="careplus"),
        "HOST": env("POSTGRES_HOST", default="db"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}

# ── Cache + Channels + Celery (all on Redis) ─────────────────────
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
# Tests / sync callers set ALWAYS_EAGER so audit writes happen in-process.
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

from celery.schedules import crontab  # noqa: E402

CELERY_BEAT_SCHEDULE = {
    "train-cf-nightly": {
        "task": "matching.train_cf_model",
        "schedule": crontab(hour=2, minute=0),
    },
    "expire-care-requests-hourly": {
        "task": "matching.expire_care_requests",
        "schedule": crontab(minute=15),
    },
    "remind-care-requests-hourly": {
        "task": "matching.remind_care_requests",
        "schedule": crontab(minute=45),
    },
    "recompute-caregiver-trust-nightly": {
        "task": "matching.recompute_all_caregiver_trust",
        "schedule": crontab(hour=3, minute=30),
    },
    "detect-health-anomalies-every-5min": {
        "task": "health_monitoring.detect_health_anomalies",
        "schedule": crontab(minute="*/5"),
    },
    "purge-erased-accounts-weekly": {
        "task": "accounts.purge_erased_accounts",
        "schedule": crontab(hour=4, minute=15, day_of_week=0),
    },
    "rebuild-faiss-index-if-stale": {
        "task": "matching.rebuild_caregiver_index_if_stale",
        "schedule": crontab(minute=20),
    },
}

# ── Cognitive layer (voice → intent + dialogue) ──────────────────
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-flash-lite-latest")
# stub | gemini | local (local URL empty until you add an on-prem model)
VOICE_INTENT_BACKEND = env("VOICE_INTENT_BACKEND", default="gemini" if GEMINI_API_KEY else "stub")
# auto | client | gemini_audio | faster_whisper — default is local Whisper (own ASR)
ASR_BACKEND = env("ASR_BACKEND", default="faster_whisper")
WHISPER_MODEL = env("WHISPER_MODEL", default="small")
WHISPER_DEVICE = env("WHISPER_DEVICE", default="cpu")
WHISPER_COMPUTE_TYPE = env("WHISPER_COMPUTE_TYPE", default="int8")
WHISPER_DOWNLOAD_ROOT = env("WHISPER_DOWNLOAD_ROOT", default="/ml/whisper")
# Sinhala specialist (SPEAK-ASR). Empty → multilingual only.
WHISPER_SINHALA_MODEL = env(
    "WHISPER_SINHALA_MODEL",
    default="SPEAK-ASR/faster-whisper-medium-si-exp10-fp16",
)
WHISPER_SINHALA_COMPUTE_TYPE = env("WHISPER_SINHALA_COMPUTE_TYPE", default="")
WHISPER_PRELOAD = env.bool("WHISPER_PRELOAD", default=False)
# auto | piper | gemini_tts | browser — server TTS for Serah (si/ta/en)
TTS_BACKEND = env("TTS_BACKEND", default="auto")
TTS_GEMINI_MODEL = env("TTS_GEMINI_MODEL", default="gemini-2.5-flash-preview-tts")
TTS_GEMINI_VOICE = env("TTS_GEMINI_VOICE", default="Kore")
# Step 84 — Redis phrase cache + defer uncached synthesis off the turn response.
TTS_PHRASE_CACHE = env.bool("TTS_PHRASE_CACHE", default=True)
TTS_DEFER_UNCACHED = env.bool("TTS_DEFER_UNCACHED", default=True)
# Neural Sinhala/Tamil via edge-tts when Gemini TTS quota is exhausted.
EDGE_TTS_ENABLED = env.bool("EDGE_TTS_ENABLED", default=True)
PIPER_BIN = env("PIPER_BIN", default="")
PIPER_MODEL_DIR = env("PIPER_MODEL_DIR", default="/ml/tts/piper")
PIPER_EN_MODEL = env("PIPER_EN_MODEL", default="en_US-lessac-medium.onnx")
DIALOGUE_CHAT_BACKEND = env("DIALOGUE_CHAT_BACKEND", default="gemini" if GEMINI_API_KEY else "stub")
# Gemini chat only (MATCH/REFINE always local VEHMF). 0 disables Gemini chat.
DIALOGUE_GEMINI_RATE_LIMIT = env.int("DIALOGUE_GEMINI_RATE_LIMIT", default=120)
DIALOGUE_GEMINI_RATE_WINDOW_SEC = env.int("DIALOGUE_GEMINI_RATE_WINDOW_SEC", default=3600)
# Future local LLM endpoint (leave blank)
LOCAL_LLM_URL = env("LOCAL_LLM_URL", default="")

# ── Matching / embeddings (Step 17) ──────────────────────────────
# "hash" = deterministic feature hashing (lean/CI). "e5" = multilingual-e5-base.
EMBEDDING_BACKEND = env("EMBEDDING_BACKEND", default="hash")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-base")
# Empty → ``<repo>/ml/artifacts`` when present, else ``backend/var/faiss``.
FAISS_ARTIFACT_DIR = env("FAISS_ARTIFACT_DIR", default="")
# CF ALS artifacts (Step 21). Empty → ``<FAISS_ARTIFACT_DIR>/cf`` or ``ml/artifacts/cf``.
CF_ARTIFACT_DIR = env("CF_ARTIFACT_DIR", default="")
# Blend trained CF into VEHMF fusion (Step 22). Set false to zero β and use CBF/geo/trust only.
CF_ENABLED = env.bool("CF_ENABLED", default=True)
# Step 91 — gated promotion: candidate must beat incumbent holdout metric by this margin.
CF_PROMOTE_MARGIN = env.float("CF_PROMOTE_MARGIN", default=0.01)
CF_PROMOTE_METRIC = env("CF_PROMOTE_METRIC", default="ndcg_at_5")
CF_EVAL_HOLDOUT_DAYS = env.int("CF_EVAL_HOLDOUT_DAYS", default=14)
# When false, train_cf_als promotes unconditionally (legacy / emergency).
CF_GATED_PROMOTION = env.bool("CF_GATED_PROMOTION", default=True)
# Minimum patient profile completion % before requesting care (Step 22b).
PATIENT_PROFILE_MIN_COMPLETION = env.int("PATIENT_PROFILE_MIN_COMPLETION", default=80)
# Caregiver onboarding + auto-approval (Step 22c).
CAREGIVER_AUTO_APPROVE = env.bool("CAREGIVER_AUTO_APPROVE", default=True)
CAREGIVER_PROFILE_MIN_COMPLETION = env.int("CAREGIVER_PROFILE_MIN_COMPLETION", default=80)
# Pending care requests auto-expire after this many hours (Step 23 / 28).
CARE_REQUEST_TTL_HOURS = env.int("CARE_REQUEST_TTL_HOURS", default=72)
# Step 28 — email patient + caregiver on mid-TTL reminder and auto-expiry.
CARE_REQUEST_NOTIFY_EMAIL_ENABLED = env.bool("CARE_REQUEST_NOTIFY_EMAIL_ENABLED", default=True)
# Step 25 — block a second active primary caregiver for the same patient.
ONE_PRIMARY_CAREGIVER = env.bool("ONE_PRIMARY_CAREGIVER", default=True)
# Step 27 — auto-ack email when a marketing lead is submitted.
LEAD_ACK_EMAIL_ENABLED = env.bool("LEAD_ACK_EMAIL_ENABLED", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@careplus.local")
# Step 40 — templated notification emails (checkout links, etc.).
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173")
NOTIFICATION_EMAIL_ENABLED = env.bool("NOTIFICATION_EMAIL_ENABLED", default=True)
# Step 41 — Web Push (VAPID). Generate with: python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys(); print(v.public_key); print(v.private_key)"
WEB_PUSH_ENABLED = env.bool("WEB_PUSH_ENABLED", default=True)
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_SUBJECT = env("VAPID_SUBJECT", default="mailto:noreply@careplus.local")
# Step 49 — mobile push alerts via Firebase Admin SDK.
FCM_CREDENTIALS_JSON = env("FCM_CREDENTIALS_JSON", default="")
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# Step 31 — payment providers (mock | payhere). Never mark paid without confirm/webhook.
PAYMENT_PROVIDER = env("PAYMENT_PROVIDER", default="mock")
MOCK_PAYMENT_CONFIRM_ENABLED = env.bool("MOCK_PAYMENT_CONFIRM_ENABLED", default=True)
PAYHERE_MERCHANT_ID = env("PAYHERE_MERCHANT_ID", default="")
PAYHERE_MERCHANT_SECRET = env("PAYHERE_MERCHANT_SECRET", default="")
PAYHERE_SANDBOX = env.bool("PAYHERE_SANDBOX", default=True)
PAYHERE_NOTIFY_URL = env("PAYHERE_NOTIFY_URL", default="")
# Step 33 — email LKR receipt after successful payment.
RECEIPT_EMAIL_ENABLED = env.bool("RECEIPT_EMAIL_ENABLED", default=True)

# Step 34/68 — app-level AES (Fernet) for PHI columns (medical notes, intent, health payloads).
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

# ── AHP fusion weights (Step 18) ─────────────────────────────────
# JSON written by ``build_ahp_weights``. Comma overrides: "0.45,0.1,0.2,0.25"
AHP_WEIGHTS_PATH = env("AHP_WEIGHTS_PATH", default="")
AHP_WEIGHTS = env("AHP_WEIGHTS", default="")
AHP_EMERGENCY_WEIGHTS = env("AHP_EMERGENCY_WEIGHTS", default="")

# ── Password validation ──────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── i18n / tz ────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static ───────────────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Step 35 — medical record uploads (local media; signed download URLs in API).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
MEDICAL_RECORD_MAX_UPLOAD_BYTES = env.int(
    "MEDICAL_RECORD_MAX_UPLOAD_BYTES", default=10 * 1024 * 1024
)
MEDICAL_RECORD_ALLOWED_MIMES = env.list(
    "MEDICAL_RECORD_ALLOWED_MIMES",
    default=[
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/plain",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
)
MEDICAL_RECORD_DOWNLOAD_URL_TTL_SECONDS = env.int(
    "MEDICAL_RECORD_DOWNLOAD_URL_TTL_SECONDS",
    default=3600,
)

# Step 22d — profile photos + caregiver certification documents (local media).
PROFILE_PHOTO_MAX_BYTES = env.int("PROFILE_PHOTO_MAX_BYTES", default=2 * 1024 * 1024)
PROFILE_DOC_MAX_BYTES = env.int("PROFILE_DOC_MAX_BYTES", default=8 * 1024 * 1024)
PROFILE_MEDIA_URL_TTL_SECONDS = env.int("PROFILE_MEDIA_URL_TTL_SECONDS", default=3600)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

# ── Browser / transport security (Step 70; TLS terminates at reverse proxy) ─
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# ── DRF ───────────────────────────────────────────────────────────
# API exploration/testing uses DRF's built-in Browsable API (enabled in dev),
# not Swagger. Session auth lets you log in via the browsable UI; JWT stays the
# primary auth for API clients.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("DRF_THROTTLE_ANON", default="60/min"),
        "user": env("DRF_THROTTLE_USER", default="300/min"),
        "auth": env("DRF_THROTTLE_AUTH", default="20/min"),
        "match": env("DRF_THROTTLE_MATCH", default="30/min"),
        "voice": env("DRF_THROTTLE_VOICE", default="60/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# Step 22f — optional email OTP second factor (off by default).
OTP_ENABLED = env.bool("OTP_ENABLED", default=False)
OTP_TTL_SECONDS = env.int("OTP_TTL_SECONDS", default=600)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
# Dummy OTP: fixed code, no outbound email (demo / thesis). Set false to send real mail.
OTP_DUMMY = env.bool("OTP_DUMMY", default=True)
OTP_DUMMY_CODE = env("OTP_DUMMY_CODE", default="123456")

# ── CORS lockdown (Step 70) ──────────────────────────────────────
# Prefer explicit allow-list. In DEBUG with an empty list, allow all for local
# Expo / Vite convenience. Production must set CORS_ALLOWED_ORIGINS (or rely on
# FRONTEND_BASE_URL as a single origin).
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
if CORS_ALLOWED_ORIGINS:
    CORS_ALLOW_ALL_ORIGINS = False
elif DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    _frontend = env("FRONTEND_BASE_URL", default="").rstrip("/")
    if _frontend.startswith("http"):
        CORS_ALLOWED_ORIGINS = [_frontend]
    CORS_ALLOW_ALL_ORIGINS = False
if not CSRF_TRUSTED_ORIGINS and CORS_ALLOWED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

# ── Observability (Step 73) ──────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)
METRICS_TOKEN = env("METRICS_TOKEN", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "{levelname} {name} {message}",
            "style": "{",
        },
        "json": {
            "()": "apps.common.observability.JsonLogFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

from apps.common.observability import init_sentry  # noqa: E402

init_sentry(
    dsn=SENTRY_DSN,
    environment=SENTRY_ENVIRONMENT,
    traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
)
