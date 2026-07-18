from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAIConsent, RolePermission

from .embeddings import get_embedder, intent_to_text
from .faiss_index import load_index
from .models import CaregiverProfile, PatientProfile
from .serializers import CaregiverProfileSerializer, PatientProfileSerializer


class CaregiverListView(generics.ListAPIView):
    """GET /api/v1/caregivers/ — active caregiver profiles (authenticated)."""

    serializer_class = CaregiverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CaregiverProfile.objects.filter(is_active=True).select_related("user")


class PatientListView(generics.ListAPIView):
    """GET /api/v1/patients/ — patient profiles (admin/auditor only for now)."""

    serializer_class = PatientProfileSerializer
    permission_classes = [RolePermission]
    allowed_roles = ("admin", "auditor")
    queryset = PatientProfile.objects.select_related("user").all()


class CbfPreviewView(APIView):
    """POST /api/v1/match/cbf/ — content-based nearest caregivers (Step 17 preview).

    Full VEHMF fusion lands in Step 19; this endpoint exposes FAISS-only ranking
    so we can verify embeddings end-to-end. Consent-gated like the voice pipeline.
    """

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]

    def post(self, request):
        condition = (request.data.get("condition") or "").strip()
        language = (request.data.get("language") or "").strip()
        care_level = (request.data.get("care_level") or "").strip()
        query = (request.data.get("query") or "").strip()
        try:
            k = int(request.data.get("k", 5))
        except (TypeError, ValueError):
            k = 5
        k = max(1, min(k, 25))

        text = intent_to_text(
            condition=condition, language=language, care_level=care_level, extra=query
        )
        if not text:
            return Response(
                {"detail": "Provide condition, language, care_level, and/or query."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        index = load_index()
        if index.size == 0:
            return Response(
                {"detail": "Caregiver index is empty. Run build_caregiver_index."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        vec = get_embedder().embed([text])[0]
        hits = index.search(vec, k=k)
        id_list = [cid for cid, _ in hits]
        profiles = {
            p.id: p for p in CaregiverProfile.objects.filter(id__in=id_list).select_related("user")
        }
        results = []
        for cid, score in hits:
            p = profiles.get(cid)
            if not p:
                continue
            results.append(
                {
                    "caregiver_id": cid,
                    "score": round(score, 6),
                    "display_name": p.display_name,
                    "specialties": p.specialties,
                    "languages": p.languages,
                    "care_levels": p.care_levels,
                    "trust_score": p.trust_score,
                }
            )
        return Response(
            {
                "query": text,
                "backend": index.backend,
                "index_size": index.size,
                "results": results,
            }
        )
