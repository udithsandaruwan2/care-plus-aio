"""WebSocket URL routes for the common app."""

from django.urls import path

from apps.matching.consumers import MatchConsumer
from apps.messaging.consumers import MessageConsumer

from .consumers import PingConsumer

websocket_urlpatterns = [
    path("ws/ping", PingConsumer.as_asgi()),
    path("ws/match/<int:patient_id>/", MatchConsumer.as_asgi()),
    path("ws/messages/<int:thread_id>/", MessageConsumer.as_asgi()),
]
