from django.urls import path

from .views import VoiceIntentHistoryView, VoiceIntentView

urlpatterns = [
    path("voice/intent/", VoiceIntentView.as_view(), name="voice_intent"),
    path("voice/intent/history/", VoiceIntentHistoryView.as_view(), name="voice_intent_history"),
]
