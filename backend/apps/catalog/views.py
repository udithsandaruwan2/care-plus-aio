from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import IsPatient

from .checkout import create_checkout_order
from .models import AddOn, CarePackage, Order
from .serializers import (
    AddOnSerializer,
    CarePackageSerializer,
    CheckoutCreateSerializer,
    OrderSerializer,
)


class CarePackageListView(generics.ListAPIView):
    """GET /api/v1/catalog/packages/ — active LKR care packages."""

    permission_classes = [permissions.AllowAny]
    serializer_class = CarePackageSerializer
    pagination_class = None

    def get_queryset(self):
        qs = CarePackage.objects.filter(is_active=True)
        level = (self.request.query_params.get("care_level") or "").strip()
        if level:
            qs = qs.filter(care_level=level)
        return qs


class AddOnListView(generics.ListAPIView):
    """GET /api/v1/catalog/addons/ — active LKR add-ons."""

    permission_classes = [permissions.AllowAny]
    serializer_class = AddOnSerializer
    pagination_class = None

    def get_queryset(self):
        qs = AddOn.objects.filter(is_active=True)
        category = (self.request.query_params.get("category") or "").strip()
        if category:
            qs = qs.filter(category=category)
        return qs


class CheckoutCreateView(APIView):
    """POST /api/v1/checkout/ — create priced Order in awaiting_payment."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def post(self, request):
        ser = CheckoutCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            order = create_checkout_order(
                patient=request.user,
                care_request_id=data["care_request_id"],
                package_id=data["package_id"],
                addon_ids=data.get("addon_ids") or [],
                days=data.get("days"),
            )
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        order = Order.objects.prefetch_related("lines").get(pk=order.pk)
        record_audit(
            actor=request.user,
            action=AuditAction.CREATE_ORDER,
            request=request,
            target_type="order",
            target_id=order.pk,
            metadata={
                "care_request_id": order.care_request_id,
                "total_lkr": str(order.total_lkr),
                "days": order.days,
                "package_slug": next(
                    (line.slug for line in order.lines.all() if line.kind == "package"),
                    None,
                ),
            },
            async_=False,
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    """GET /api/v1/orders/<id>/ — patient-owned order with line items."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]
    serializer_class = OrderSerializer
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return Order.objects.filter(patient=self.request.user).prefetch_related("lines")
