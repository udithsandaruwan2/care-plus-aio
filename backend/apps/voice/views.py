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
from .models import VoiceIntent
from .serializers import VoiceIntentInputSerializer, VoiceIntentSerializer


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

        result = process_turn(
            user=request.user,
            client_text=client_text,
            audio=audio,
            content_type=content_type,
            has_prior_match=has_prior,
            prior_intent=prior_intent,
        )

        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_HEALTH,
            request=request,
            target_type="voice_turn",
            target_id=0,
            metadata={
                "route": result["route"],
                "asr_source": result["asr_source"],
                "has_match": bool(result.get("match")),
            },
        )
        return Response(result, status=status.HTTP_200_OK)
