from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConditionTerm
from .resolver import export_vocab_json
from .serializers import ConditionTermSerializer


class ConditionListView(APIView):
    """GET /api/v1/vocab/conditions/ — active canonical medical terms (Step 15b)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = ConditionTerm.objects.filter(active=True).order_by("canonical_en")
        if qs.exists():
            data = ConditionTermSerializer(qs, many=True).data
        else:
            data = export_vocab_json()
        return Response({"count": len(data), "results": data})
