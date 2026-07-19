"""Base settings shared across environments.

Lean profile: one PostgreSQL instance (PostGIS + TimescaleDB), one Redis
(cache + Redlock + Celery broker + Channels layer). See docs/ARCHITECTURE.md.
"""

from datetime import timedelta
from pathlib import Path

import environ

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
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
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

# ── Cognitive layer (voice → intent + dialogue) ──────────────────
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODEL = env("GEMINI_MODEL", default="gemini-flash-lite-latest")
# stub | gemini | local (local URL empty until you add an on-prem model)
VOICE_INTENT_BACKEND = env(
    "VOICE_INTENT_BACKEND", default="gemini" if GEMINI_API_KEY else "stub"
)
# auto | client | gemini_audio | faster_whisper (whisper slot empty for now)
ASR_BACKEND = env("ASR_BACKEND", default="auto")
DIALOGUE_CHAT_BACKEND = env(
    "DIALOGUE_CHAT_BACKEND", default="gemini" if GEMINI_API_KEY else "stub"
)
# Future local LLM / local ASR endpoint (leave blank)
LOCAL_LLM_URL = env("LOCAL_LLM_URL", default="")

# ── Matching / embeddings (Step 17) ──────────────────────────────
# "hash" = deterministic feature hashing (lean/CI). "e5" = multilingual-e5-base.
EMBEDDING_BACKEND = env("EMBEDDING_BACKEND", default="hash")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-base")
# Empty → ``<repo>/ml/artifacts`` when present, else ``backend/var/faiss``.
FAISS_ARTIFACT_DIR = env("FAISS_ARTIFACT_DIR", default="")

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

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
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
