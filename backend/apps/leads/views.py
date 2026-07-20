from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin

from .models import Lead
from .serializers import LeadContactSerializer, LeadCreateSerializer, LeadSerializer
from .services import create_lead, mark_lead_contacted


class LeadPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LeadListCreateView(generics.ListCreateAPIView):
    """POST public create; GET admin inbox."""

    pagination_class = LeadPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsAdmin()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LeadCreateSerializer
        return LeadSerializer

    def get_queryset(self):
        qs = Lead.objects.select_related("contacted_by").all()
        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request, *args, **kwargs):
        ser = LeadCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        lead = create_lead(
            name=data["name"],
            email=data["email"],
            phone=data.get("phone", ""),
            message=data.get("message", ""),
            city=data.get("city", ""),
            preferred_language=data.get("preferred_language", ""),
            source=data.get("source") or "marketing_form",
        )
        return Response(LeadSerializer(lead).data, status=status.HTTP_201_CREATED)


class LeadContactView(APIView):
    """PATCH /api/v1/leads/<id>/contact/ — admin marks lead contacted."""

    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, pk: int):
        ser = LeadContactSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            lead = Lead.objects.select_related("contacted_by").get(pk=pk)
        except Lead.DoesNotExist as exc:
            raise NotFound("Lead not found.") from exc

        try:
            lead = mark_lead_contacted(
                lead,
                actor=request.user,
                notes=ser.validated_data.get("notes", ""),
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        return Response(LeadSerializer(lead).data)
