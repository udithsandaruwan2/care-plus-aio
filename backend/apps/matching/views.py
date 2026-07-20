import time

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import HasAIConsent, IsCaregiver, IsPatient, RolePermission

from .ahp import build_config, get_ahp_weights
from .cf_model import cf_model_info, get_cf_model
from .embeddings import get_embedder, intent_to_text
from .engine import run_match
from .faiss_index import load_index
from .interactions import log_interaction, record_match_interactions
from .care_requests import accept_care_request, cancel_care_request, create_care_request, reject_care_request
from .caregiver_profile import activate_caregiver_if_ready
from .models import (
    CareRequest,
    CaregiverProfile,
    InteractionKind,
    MatchResult,
    MatchRun,
    PatientProfile,
)
from .serializers import (
    CaregiverDetailSerializer,
    CaregiverMeSerializer,
    CaregiverProfileSerializer,
    CaregiverProfileUpdateSerializer,
    CareRequestActionSerializer,
    CareRequestCreateSerializer,
    CareRequestSerializer,
    MatchRequestSerializer,
    PatientProfileSerializer,
    PatientProfileUpdateSerializer,
)


class CaregiverPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CaregiverListView(generics.ListAPIView):
    """GET /api/v1/caregivers/ — searchable active caregivers (Step 20b).

    Query params (combinable):
      q, language, specialty, city, care_level, available,
      near=lon,lat, radius_km (default 25 when near is set)
    """

    serializer_class = CaregiverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CaregiverPagination

    def get_queryset(self):
        qs = CaregiverProfile.objects.filter(is_active=True).select_related("user")
        params = self.request.query_params

        q = (params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(display_name__icontains=q)
                | Q(bio__icontains=q)
                | Q(city__icontains=q)
                | Q(specialties__icontains=q)
            )

        language = (params.get("language") or "").strip()
        if language:
            qs = qs.filter(languages__contains=[language])

        specialty = (params.get("specialty") or "").strip().lower()
        if specialty:
            qs = qs.filter(specialties__icontains=specialty)

        city = (params.get("city") or "").strip()
        if city:
            qs = qs.filter(city__iexact=city)

        care_level = (params.get("care_level") or "").strip().lower()
        if care_level:
            qs = qs.filter(care_levels__contains=[care_level])

        available = (params.get("available") or "").strip().lower()
        if available in ("1", "true", "yes"):
            qs = qs.filter(is_available=True)
        elif available in ("0", "false", "no"):
            qs = qs.filter(is_available=False)

        near = (params.get("near") or "").strip()
        if near:
            try:
                lon_s, lat_s = near.split(",", 1)
                lon, lat = float(lon_s.strip()), float(lat_s.strip())
            except (TypeError, ValueError):
                return qs.none()
            try:
                radius_km = float(params.get("radius_km") or 25)
            except (TypeError, ValueError):
                radius_km = 25.0
            radius_km = max(0.5, min(radius_km, 500.0))
            origin = Point(lon, lat, srid=4326)
            qs = (
                qs.filter(location__dwithin=(origin, D(km=radius_km)))
                .annotate(distance=Distance("location", origin))
                .order_by("distance", "-trust_score")
            )
        else:
            qs = qs.order_by("-trust_score", "display_name")

        return qs


class CaregiverDetailView(generics.RetrieveAPIView):
    """GET /api/v1/caregivers/<id>/ — public caregiver profile (Step 20d)."""

    serializer_class = CaregiverDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        return CaregiverProfile.objects.filter(is_active=True).select_related("user")

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        record_audit(
            actor=request.user,
            action=AuditAction.VIEW_CAREGIVER,
            request=request,
            target_type="caregiver_profile",
            target_id=instance.pk,
            metadata={
                "display_name": instance.display_name,
                "city": instance.city,
            },
            async_=False,
        )
        if hasattr(request.user, "patient_profile"):
            log_interaction(
                request.user,
                instance,
                InteractionKind.VIEW,
                metadata={"source": "caregiver_detail"},
            )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CaregiverMeView(APIView):
    """GET/PATCH /api/v1/caregivers/me/ — onboarding + presence (Step 22c)."""

    permission_classes = [permissions.IsAuthenticated, IsCaregiver]

    def _profile(self, user) -> CaregiverProfile:
        profile, _ = CaregiverProfile.objects.get_or_create(
            user=user,
            defaults={
                "display_name": user.first_name or user.email.split("@")[0],
                "location": Point(79.8612, 6.9271, srid=4326),
                "city": "",
                "is_active": False,
                "is_approved": False,
            },
        )
        return profile

    def get(self, request):
        profile = self._profile(request.user)
        return Response(CaregiverMeSerializer(profile).data)

    def patch(self, request):
        profile = self._profile(request.user)
        ser = CaregiverProfileUpdateSerializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        profile = activate_caregiver_if_ready(profile)
        profile.refresh_from_db()
        return Response(CaregiverMeSerializer(profile).data)


class PatientMeView(APIView):
    """GET/PATCH /api/v1/patients/me/ — patient onboarding profile (Step 22b)."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def _profile(self, user) -> PatientProfile:
        profile, _ = PatientProfile.objects.get_or_create(user=user)
        return profile

    def get(self, request):
        profile = self._profile(request.user)
        return Response(PatientProfileSerializer(profile).data)

    def patch(self, request):
        profile = self._profile(request.user)
        ser = PatientProfileUpdateSerializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        profile.refresh_from_db()
        return Response(PatientProfileSerializer(profile).data)


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


class AhpWeightsView(APIView):
    """GET /api/v1/match/weights/ — current AHP fusion weights (Step 18)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import json

        from .ahp import default_config_path

        path = default_config_path()
        if path.exists():
            doc = json.loads(path.read_text(encoding="utf-8"))
        else:
            doc = build_config()
        doc["vector"] = list(get_ahp_weights())
        doc["emergency_vector"] = list(get_ahp_weights(emergency=True))
        factors = doc.get("factors") or ["cbf", "cf", "geo", "trust"]
        doc["factors"] = factors
        doc["weights"] = {name: round(w, 6) for name, w in zip(factors, doc["vector"], strict=True)}
        doc["emergency_weights"] = {
            name: round(w, 6) for name, w in zip(factors, doc["emergency_vector"], strict=True)
        }
        doc["cf"] = cf_model_info(get_cf_model())
        return Response(doc)


class MatchView(APIView):
    """POST /api/v1/match/ — VEHMF ranked caregivers + breakdown + XAI (Step 19)."""

    permission_classes = [permissions.IsAuthenticated, HasAIConsent]

    def post(self, request):
        ser = MatchRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Prefer explicit lon/lat; else the caller's patient profile location.
        lon, lat = data.get("longitude"), data.get("latitude")
        if lon is None:
            profile = getattr(request.user, "patient_profile", None)
            if profile is not None and profile.location is not None:
                lon, lat = profile.location.x, profile.location.y

        t0 = time.perf_counter()
        try:
            out = run_match(
                condition=data.get("condition", ""),
                language=data.get("language", ""),
                care_level=data.get("care_level", ""),
                query=data.get("query", ""),
                patient_id=request.user.pk,
                longitude=lon,
                latitude=lat,
                top_k=data.get("k", 10),
                emergency=bool(data.get("emergency")),
            )
        except Exception as exc:  # index missing / empty
            return Response(
                {"detail": f"Match engine unavailable: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        run = MatchRun.objects.create(
            user=request.user,
            query=out.query,
            condition=data.get("condition", ""),
            language=data.get("language", ""),
            care_level=data.get("care_level", ""),
            emergency=out.emergency,
            weights=list(out.weights),
            latency_ms=latency_ms,
        )
        profiles = {
            p.id: p
            for p in CaregiverProfile.objects.filter(
                id__in=[r.caregiver_id for r in out.results]
            ).select_related("user")
        }
        result_rows = []
        for rank, hit in enumerate(out.results, start=1):
            MatchResult.objects.create(
                run=run,
                caregiver_id=hit.caregiver_id,
                rank=rank,
                score=hit.score,
                cbf=hit.cbf,
                cf=hit.cf,
                geo=hit.geo,
                trust=hit.trust,
                explanation=hit.explanation,
                distance_m=hit.distance_m,
            )
            p = profiles.get(hit.caregiver_id)
            result_rows.append(
                {
                    "caregiver_id": hit.caregiver_id,
                    "rank": rank,
                    "score": round(hit.score, 6),
                    "breakdown": {
                        "cbf": round(hit.cbf, 6),
                        "cf": round(hit.cf, 6),
                        "geo": round(hit.geo, 6),
                        "trust": round(hit.trust, 6),
                    },
                    "explanation": hit.explanation,
                    "distance_m": None if hit.distance_m is None else round(hit.distance_m, 1),
                    "display_name": p.display_name if p else "",
                    "specialties": p.specialties if p else [],
                    "languages": p.languages if p else [],
                    "care_levels": p.care_levels if p else [],
                    "trust_score": p.trust_score if p else None,
                    "is_available": bool(p.is_available) if p else False,
                }
            )

        record_match_interactions(
            request.user,
            [r.caregiver_id for r in out.results],
            source="match_api",
        )

        payload = {
            "request_id": run.pk,
            "latency_ms": latency_ms,
            "query": out.query,
            "emergency": out.emergency,
            "cf_enabled": out.cf_enabled,
            "cf_version": out.cf_version,
            "weights": {
                "cbf": round(out.weights[0], 6),
                "cf": round(out.weights[1], 6),
                "geo": round(out.weights[2], 6),
                "trust": round(out.weights[3], 6),
            },
            "results": result_rows,
        }
        from .push import push_match_results

        push_match_results(request.user.pk, payload)
        return Response(payload, status=status.HTTP_201_CREATED)


class CareRequestPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class CareRequestListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/v1/care-requests/ — patient outgoing / caregiver inbox (Step 23)."""

    serializer_class = CareRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CareRequestPagination

    def get_queryset(self):
        user = self.request.user
        qs = (
            CareRequest.objects.select_related(
                "patient", "caregiver", "caregiver__user", "relationship"
            )
            .all()
            .order_by("-created_at")
        )
        if user.role == "patient":
            return qs.filter(patient=user)
        if user.role == "caregiver":
            return qs.filter(caregiver__user=user)
        return qs.none()

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsPatient()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CareRequestCreateSerializer
        return CareRequestSerializer

    def create(self, request, *args, **kwargs):
        ser = CareRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        caregiver = ser.context["caregiver"]
        match_run = ser.context.get("match_run")
        try:
            care_request = create_care_request(
                patient=request.user,
                caregiver=caregiver,
                message=ser.validated_data.get("message", ""),
                match_run=match_run,
                match_snapshot=ser.validated_data.get("match_snapshot") or {},
            )
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if isinstance(exc, DRFValidationError):
                raise
            if hasattr(exc, "detail"):
                raise
            raise DRFValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.CREATE_CARE_REQUEST,
            request=request,
            target_type="care_request",
            target_id=care_request.pk,
            metadata={
                "caregiver_id": caregiver.pk,
                "caregiver_name": caregiver.display_name,
                "match_run_id": match_run.pk if match_run else None,
            },
            async_=False,
        )
        out = CareRequestSerializer(care_request)
        return Response(out.data, status=status.HTTP_201_CREATED)


class CareRequestDetailView(generics.RetrieveAPIView):
    """GET /api/v1/care-requests/<id>/ — detail for patient or caregiver."""

    serializer_class = CareRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        user = self.request.user
        qs = CareRequest.objects.select_related(
            "patient", "caregiver", "caregiver__user", "relationship"
        )
        if user.role == "patient":
            return qs.filter(patient=user)
        if user.role == "caregiver":
            return qs.filter(caregiver__user=user)
        return qs.none()


class CareRequestActionView(APIView):
    """PATCH /api/v1/care-requests/<id>/action/ — cancel / accept / reject."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk: int):
        ser = CareRequestActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        action = ser.validated_data["action"]

        if action == "cancel":
            if request.user.role != "patient":
                raise PermissionDenied("Only patients can cancel care requests.")
            return self._cancel(request, pk)

        if action in ("accept", "reject"):
            if request.user.role != "caregiver":
                raise PermissionDenied("Only caregivers can accept or reject care requests.")
            if action == "accept":
                return self._accept(request, pk)
            return self._reject(request, pk, reason=ser.validated_data.get("reason", ""))

        raise ValidationError({"action": "Unsupported action."})

    def _get_care_request(self, pk: int):
        return CareRequest.objects.select_related(
            "patient", "caregiver", "caregiver__user"
        ).get(pk=pk)

    def _cancel(self, request, pk: int):
        try:
            care_request = self._get_care_request(pk)
        except CareRequest.DoesNotExist as exc:
            raise NotFound("Care request not found.") from exc
        if care_request.patient_id != request.user.pk:
            raise NotFound("Care request not found.")

        try:
            care_request = cancel_care_request(care_request, patient=request.user)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.CANCEL_CARE_REQUEST,
            request=request,
            target_type="care_request",
            target_id=care_request.pk,
            metadata={"caregiver_id": care_request.caregiver_id},
            async_=False,
        )
        return Response(CareRequestSerializer(care_request).data)

    def _accept(self, request, pk: int):
        try:
            care_request = self._get_care_request(pk)
        except CareRequest.DoesNotExist as exc:
            raise NotFound("Care request not found.") from exc
        if care_request.caregiver.user_id != request.user.pk:
            raise NotFound("Care request not found.")

        try:
            care_request, relationship = accept_care_request(
                care_request, caregiver_user=request.user
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.ACCEPT_CARE_REQUEST,
            request=request,
            target_type="care_request",
            target_id=care_request.pk,
            metadata={
                "patient_id": care_request.patient_id,
                "relationship_id": relationship.pk,
            },
            async_=False,
        )
        return Response(CareRequestSerializer(care_request).data)

    def _reject(self, request, pk: int, *, reason: str):
        try:
            care_request = self._get_care_request(pk)
        except CareRequest.DoesNotExist as exc:
            raise NotFound("Care request not found.") from exc
        if care_request.caregiver.user_id != request.user.pk:
            raise NotFound("Care request not found.")

        try:
            care_request = reject_care_request(
                care_request, caregiver_user=request.user, reason=reason
            )
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.REJECT_CARE_REQUEST,
            request=request,
            target_type="care_request",
            target_id=care_request.pk,
            metadata={"patient_id": care_request.patient_id, "reason": reason.strip()},
            async_=False,
        )
        return Response(CareRequestSerializer(care_request).data)
