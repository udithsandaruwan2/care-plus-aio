"""ASGI entry point.

Step 3: HTTP only. Step 4 wraps this in a Channels ProtocolTypeRouter to add
WebSocket support (ws/ping, later ws/match and ws/alerts).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "careplus.settings.dev")

application = get_asgi_application()
