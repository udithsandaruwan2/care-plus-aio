from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import HasAIConsent
from apps.common.envutil import refresh_env

from .backends import extract_intent
from .dialogue import process_turn
from .models import DialogueSession, VoiceIntent
from .serializers import VoiceIntentInputSerializer, VoiceIntentSerializer
from .session import clear_active_sessions


class VoiceIntentView(APIView):
    """POST /api/v1/voice/intent/ — transcript → structured intent (consent-gated)."""

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]

    def post(self, request):
        refresh_env()
        input_ser = VoiceIntentInputSerializer(data=request.data)
        input_ser.is_valid(raise_exception=True)
        text = input_ser.validated_data["text"]
        hint = input_ser.validated_data.get("language")

        data = extract_intent(text, hint)
        intent = VoiceIntent.objects.create(user=request.user, **data)

        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_HEALTH,
            request=request,
            target_type="voice_intent",
            target_id=intent.pk,
            metadata={"source": data["source"], "condition": data["condition"]},
        )

        return Response(VoiceIntentSerializer(intent).data, status=status.HTTP_201_CREATED)


class VoiceIntentHistoryView(generics.ListAPIView):
    """GET /api/v1/voice/intent/history/ — the caller's recent intents."""

    serializer_class = VoiceIntentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VoiceIntent.objects.filter(user=self.request.user)


class VoiceTurnView(APIView):
    """POST /api/v1/voice/turn/ — conversational turn (audio and/or text).

    Multipart fields:
      - text: optional Web Speech caption
      - audio: optional recorded blob (preferred for Sinhala/Tamil)
      - has_prior_match: "true"|"false"
      - prior_intent: optional JSON string of current chips
      - prior_match: optional JSON string of current match cards
      - ui_language: Sinhala|Tamil|English
    """

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        refresh_env()
        client_text = (request.data.get("text") or "").strip()
        audio_file = request.FILES.get("audio")
        audio = audio_file.read() if audio_file else None
        content_type = audio_file.content_type if audio_file else None

        has_prior = str(request.data.get("has_prior_match") or "").lower() in (
            "1",
            "true",
            "yes",
        )
        prior_intent = None
        raw_prior = request.data.get("prior_intent")
        if raw_prior:
            import json

            try:
                prior_intent = json.loads(raw_prior) if isinstance(raw_prior, str) else raw_prior
            except (TypeError, json.JSONDecodeError):
                prior_intent = None

        ui_language = (request.data.get("ui_language") or "").strip() or None
        if ui_language not in ("Sinhala", "Tamil", "English"):
            ui_language = None

        prior_match = None
        raw_match = request.data.get("prior_match")
        if raw_match:
            import json

            try:
                prior_match = json.loads(raw_match) if isinstance(raw_match, str) else raw_match
            except (TypeError, json.JSONDecodeError):
                prior_match = None

        result = process_turn(
            user=request.user,
            client_text=client_text,
            audio=audio,
            content_type=content_type,
            has_prior_match=has_prior,
            prior_intent=prior_intent,
            prior_match=prior_match if isinstance(prior_match, dict) else None,
            ui_language=ui_language,
        )

        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_HEALTH,
            request=request,
            target_type="voice_turn",
            target_id=result.get("session_id") or 0,
            metadata={
                "route": result["route"],
                "situation": result.get("situation"),
                "asr_source": result["asr_source"],
                "tts_source": result.get("tts_source"),
                "ui_language": ui_language,
                "has_match": bool(result.get("match")),
                "session_id": result.get("session_id"),
            },
        )
        return Response(result, status=status.HTTP_200_OK)


class VoiceSessionClearView(APIView):
    """POST /api/v1/voice/session/clear/ — New request: drop dialogue memory."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        cleared = clear_active_sessions(request.user)
        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_HEALTH,
            request=request,
            target_type="dialogue_session",
            target_id=0,
            metadata={"cleared": cleared},
            async_=False,
        )
        return Response({"cleared": cleared, "active": False}, status=status.HTTP_200_OK)


class VoiceSessionView(APIView):
    """GET /api/v1/voice/session/ — active DialogueSession snapshot (Step 15g)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        session = (
            DialogueSession.objects.filter(user=request.user, active=True)
            .order_by("-updated_at")
            .first()
        )
        if session is None:
            return Response({"active": False, "session": None})
        return Response(
            {
                "active": True,
                "session": {
                    "id": session.pk,
                    "lang": session.lang,
                    "intent_chips": session.intent_chips or {},
                    "open_questions": session.open_questions or [],
                    "route_history": session.route_history or [],
                    "turns": session.turns or [],
                    "last_match_run_id": session.last_match_run_id,
                    "updated_at": session.updated_at.isoformat(),
                },
            }
        )
