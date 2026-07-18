"""Development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True

# Renderable browsable API in dev for convenience.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append(  # noqa: F405
    "rest_framework.renderers.BrowsableAPIRenderer"
)
