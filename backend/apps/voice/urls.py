from django.urls import path

from .views import (
    VoiceDialoguePolicyView,
    VoiceIntentHistoryView,
    VoiceIntentView,
    VoiceMatchHistoryView,
    VoiceSessionClearView,
    VoiceSessionView,
    VoiceTtsView,
    VoiceTurnView,
)

urlpatterns = [
    path("voice/intent/", VoiceIntentView.as_view(), name="voice_intent"),
    path("voice/intent/history/", VoiceIntentHistoryView.as_view(), name="voice_intent_history"),
    path("voice/history/", VoiceMatchHistoryView.as_view(), name="voice_match_history"),
    path("voice/turn/", VoiceTurnView.as_view(), name="voice_turn"),
    path("voice/tts/", VoiceTtsView.as_view(), name="voice_tts"),
    path("voice/session/", VoiceSessionView.as_view(), name="voice_session"),
    path("voice/session/clear/", VoiceSessionClearView.as_view(), name="voice_session_clear"),
    path("voice/policy/", VoiceDialoguePolicyView.as_view(), name="voice_dialogue_policy"),
]
