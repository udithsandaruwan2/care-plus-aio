from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import IsPatient

from .checkout import create_checkout_order
from .models import AddOn, CarePackage, Order, PaymentIntent
from .payments.service import (
    confirm_mock_payment,
    create_payment_intent,
    handle_payhere_webhook,
)
from .serializers import (
    AddOnSerializer,
    CarePackageSerializer,
    CheckoutCreateSerializer,
    OrderSerializer,
    PaymentIntentSerializer,
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


class PaymentIntentView(APIView):
    """POST/GET /api/v1/orders/<id>/payment-intent/ — create or fetch latest intent."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def post(self, request, pk: int):
        try:
            intent = create_payment_intent(patient=request.user, order_id=pk)
        except (DRFValidationError, NotFound, PermissionDenied):
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.CREATE_PAYMENT_INTENT,
            request=request,
            target_type="payment_intent",
            target_id=intent.pk,
            metadata={
                "order_id": intent.order_id,
                "provider": intent.provider,
                "provider_intent_id": intent.provider_intent_id,
                "amount_lkr": str(intent.amount_lkr),
            },
            async_=False,
        )
        return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)

    def get(self, request, pk: int):
        if not Order.objects.filter(pk=pk, patient=request.user).exists():
            raise NotFound("Order not found.")
        intent = (
            PaymentIntent.objects.filter(order_id=pk, patient=request.user)
            .order_by("-created_at")
            .first()
        )
        if intent is None:
            raise NotFound("No payment intent for this order.")
        return Response(PaymentIntentSerializer(intent).data)


class MockPaymentConfirmView(APIView):
    """POST /api/v1/payments/mock/<provider_intent_id>/confirm/ — explicit mock pay."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def post(self, request, provider_intent_id: str):
        try:
            intent = confirm_mock_payment(
                patient=request.user,
                provider_intent_id=provider_intent_id,
            )
        except (DRFValidationError, NotFound, PermissionDenied):
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        record_audit(
            actor=request.user,
            action=AuditAction.CONFIRM_PAYMENT,
            request=request,
            target_type="payment_intent",
            target_id=intent.pk,
            metadata={
                "order_id": intent.order_id,
                "source": "mock_confirm",
                "provider_intent_id": intent.provider_intent_id,
            },
            async_=False,
        )
        return Response(PaymentIntentSerializer(intent).data)


class PayHereWebhookView(APIView):
    """POST /api/v1/payments/payhere/webhook/ — verified PayHere notify stub."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.body or b""
        headers = {k: v for k, v in request.META.items() if k.startswith("HTTP_")}
        try:
            intent = handle_payhere_webhook(body=body, headers=headers)
        except PermissionDenied:
            raise
        except NotFound:
            raise
        except DRFValidationError:
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        record_audit(
            actor=None,
            action=AuditAction.PAYMENT_WEBHOOK,
            request=request,
            target_type="payment_intent",
            target_id=intent.pk,
            metadata={
                "order_id": intent.order_id,
                "provider": "payhere",
                "status": intent.status,
                "provider_intent_id": intent.provider_intent_id,
            },
            async_=False,
        )
        # PayHere expects a plain 200 OK body.
        return Response({"status": intent.status}, status=status.HTTP_200_OK)
