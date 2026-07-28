from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import HealthMetricIngestSerializer, HealthMetricSerializer
from .services import aggregate_window, ingest_metric, metrics_queryset_for_user, resolve_ingest_patient


class HealthMetricIngestView(APIView):
    """POST /health/metrics/ingest/ — ingest one health metric sample."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = HealthMetricIngestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        patient = resolve_ingest_patient(
            actor=request.user,
            requested_patient_id=data.get("patient_id"),
        )
        row = ingest_metric(
            actor=request.user,
            patient=patient,
            kind=data["kind"],
            value=data["value"],
            unit=data.get("unit", ""),
            source=data.get("source", "manual"),
            recorded_at=data.get("recorded_at"),
            metadata=data.get("metadata"),
        )
        return Response(HealthMetricSerializer(row).data, status=201)


class HealthMetricWindowView(APIView):
    """GET /health/metrics/window/?kind=&hours=&patient_id= — quick aggregates."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        kind = (request.query_params.get("kind") or "").strip()
        if not kind:
            raise ValidationError("kind query parameter is required.")
        hours_raw = (request.query_params.get("hours") or "24").strip()
        try:
            hours = int(hours_raw)
        except ValueError as exc:
            raise ValidationError("hours must be an integer.") from exc
        hours = max(1, min(hours, 24 * 30))

        qs = metrics_queryset_for_user(request.user)
        patient_id_raw = (request.query_params.get("patient_id") or "").strip()
        if patient_id_raw:
            try:
                pid = int(patient_id_raw)
            except ValueError as exc:
                raise ValidationError("patient_id must be an integer.") from exc
            qs = qs.filter(patient_id=pid)
        payload = aggregate_window(queryset=qs, kind=kind, hours=hours)
        return Response(payload)

