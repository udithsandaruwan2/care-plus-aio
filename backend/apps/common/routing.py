"""WebSocket URL routes for the common app."""

from django.urls import path

from apps.matching.consumers import MatchConsumer
from apps.messaging.consumers import MessageConsumer
from apps.voice.live_consumer import VoiceLiveConsumer

from .consumers import PingConsumer

websocket_urlpatterns = [
    path("ws/ping", PingConsumer.as_asgi()),
    path("ws/match/<int:patient_id>/", MatchConsumer.as_asgi()),
    path("ws/messages/<int:thread_id>/", MessageConsumer.as_asgi()),
    path("ws/voice/live/<int:user_id>/", VoiceLiveConsumer.as_asgi()),
]
