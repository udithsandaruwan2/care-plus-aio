from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction
from apps.accounts.permissions import HasOtpIfEnabled, IsAdmin, IsPatient, RolePermission
from apps.common.idempotency import (
    IdempotencyScope,
    resolve_idempotency_key,
    run_idempotent,
)

from .checkout import create_checkout_order
from .models import AddOn, CarePackage, Order, OrderStatus, PaymentIntent
from .payments.service import (
    confirm_mock_payment,
    create_payment_intent,
    handle_payhere_webhook,
)
from .receipts import format_receipt_html
from .serializers import (
    AddOnSerializer,
    AddOnWriteSerializer,
    CarePackageSerializer,
    CarePackageWriteSerializer,
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


class AdminCarePackageListCreateView(APIView):
    """GET/POST /api/v1/admin/catalog/packages/ — admin+auditor list; admin create."""

    allowed_roles = ("admin", "auditor")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    def get(self, request):
        qs = CarePackage.objects.all().order_by("sort_order", "price_lkr", "name")
        level = (request.query_params.get("care_level") or "").strip()
        if level:
            qs = qs.filter(care_level=level)
        return Response(CarePackageSerializer(qs, many=True).data)

    def post(self, request):
        ser = CarePackageWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = CarePackage.objects.create(**ser.validated_data)
        return Response(CarePackageSerializer(row).data, status=status.HTTP_201_CREATED)


class AdminCarePackageDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/admin/catalog/packages/<id>/."""

    allowed_roles = ("admin", "auditor")

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    def _get(self, pk: int) -> CarePackage:
        try:
            return CarePackage.objects.get(pk=pk)
        except CarePackage.DoesNotExist as exc:
            raise NotFound("Package not found.") from exc

    def get(self, request, pk: int):
        return Response(CarePackageSerializer(self._get(pk)).data)

    def patch(self, request, pk: int):
        row = self._get(pk)
        ser = CarePackageWriteSerializer(row, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(row, key, value)
        row.save()
        return Response(CarePackageSerializer(row).data)

    def delete(self, request, pk: int):
        self._get(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminAddOnListCreateView(APIView):
    """GET/POST /api/v1/admin/catalog/addons/ — admin+auditor list; admin create."""

    allowed_roles = ("admin", "auditor")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    def get(self, request):
        qs = AddOn.objects.all().order_by("sort_order", "category", "price_lkr", "name")
        category = (request.query_params.get("category") or "").strip()
        if category:
            qs = qs.filter(category=category)
        return Response(AddOnSerializer(qs, many=True).data)

    def post(self, request):
        ser = AddOnWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = AddOn.objects.create(**ser.validated_data)
        return Response(AddOnSerializer(row).data, status=status.HTTP_201_CREATED)


class AdminAddOnDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/admin/catalog/addons/<id>/."""

    allowed_roles = ("admin", "auditor")

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [RolePermission()]

    def _get(self, pk: int) -> AddOn:
        try:
            return AddOn.objects.get(pk=pk)
        except AddOn.DoesNotExist as exc:
            raise NotFound("Add-on not found.") from exc

    def get(self, request, pk: int):
        return Response(AddOnSerializer(self._get(pk)).data)

    def patch(self, request, pk: int):
        row = self._get(pk)
        ser = AddOnWriteSerializer(row, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(row, key, value)
        row.save()
        return Response(AddOnSerializer(row).data)

    def delete(self, request, pk: int):
        self._get(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckoutCreateView(APIView):
    """POST /api/v1/checkout/ — create priced Order in awaiting_payment."""

    permission_classes = [permissions.IsAuthenticated, IsPatient, HasOtpIfEnabled]

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


class OrderReceiptView(APIView):
    """GET /api/v1/orders/<id>/receipt/ — HTML receipt for print/download (Step 33)."""

    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def get(self, request, pk: int):
        try:
            order = (
                Order.objects.prefetch_related("lines")
                .select_related("patient")
                .get(pk=pk, patient=request.user)
            )
        except Order.DoesNotExist as exc:
            raise NotFound("Order not found.") from exc
        if order.status != OrderStatus.PAID:
            raise DRFValidationError("Receipt is available after the order is paid.")
        intent = (
            PaymentIntent.objects.filter(order=order, status="succeeded")
            .order_by("-confirmed_at")
            .first()
        )
        html = format_receipt_html(order=order, payment_intent=intent)
        return HttpResponse(html, content_type="text/html; charset=utf-8")


class PaymentIntentView(APIView):
    """POST/GET /api/v1/orders/<id>/payment-intent/ — create or fetch latest intent."""

    permission_classes = [permissions.IsAuthenticated, IsPatient, HasOtpIfEnabled]

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

    permission_classes = [permissions.IsAuthenticated, IsPatient, HasOtpIfEnabled]

    def post(self, request, provider_intent_id: str):
        key = resolve_idempotency_key(request)
        if not key:
            key = f"mock-confirm:{provider_intent_id}"

        def execute():
            intent = confirm_mock_payment(
                patient=request.user,
                provider_intent_id=provider_intent_id,
            )
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
                    "idempotency_key": key,
                },
                async_=False,
            )
            return PaymentIntentSerializer(intent).data, status.HTTP_200_OK

        try:
            body, code, _replayed = run_idempotent(
                user=request.user,
                scope=IdempotencyScope.PAYMENT_CONFIRM,
                key=key,
                execute=execute,
            )
        except (DRFValidationError, NotFound, PermissionDenied):
            raise
        except Exception as exc:
            raise DRFValidationError(str(exc)) from exc

        return Response(body, status=code)


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
