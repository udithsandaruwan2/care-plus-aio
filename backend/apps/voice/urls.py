from django.urls import path

from .views import VoiceIntentHistoryView, VoiceIntentView, VoiceTurnView

urlpatterns = [
    path("voice/intent/", VoiceIntentView.as_view(), name="voice_intent"),
    path("voice/intent/history/", VoiceIntentHistoryView.as_view(), name="voice_intent_history"),
    path("voice/turn/", VoiceTurnView.as_view(), name="voice_turn"),
]
