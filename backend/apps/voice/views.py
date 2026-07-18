from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import HasAIConsent

from .extraction import extract_intent
from .models import VoiceIntent
from .serializers import VoiceIntentInputSerializer, VoiceIntentSerializer


class VoiceIntentView(APIView):
    """POST /api/v1/voice/intent/ — transcript → structured intent (consent-gated).

    Requires an authenticated user with recorded ``ai_processing`` consent
    (``HasAIConsent`` returns 451 otherwise). Persists a ``VoiceIntent`` row and
    returns the structured result.
    """

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]

    def post(self, request):
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
    """GET /api/v1/voice/intent/ — the caller's recent intents."""

    serializer_class = VoiceIntentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VoiceIntent.objects.filter(user=self.request.user)
