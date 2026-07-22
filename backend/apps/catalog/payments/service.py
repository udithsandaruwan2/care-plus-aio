"""PaymentIntent create / confirm / webhook services (Step 31)."""

from __future__ import annotations

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import Role

from ..models import (
    Order,
    OrderStatus,
    PaymentIntent,
    PaymentIntentStatus,
    PaymentProviderName,
)
from .providers import get_payment_provider
from .providers.payhere import PayHereProvider


def _open_intent_qs(order: Order):
    return PaymentIntent.objects.filter(
        order=order,
        status__in=[
            PaymentIntentStatus.REQUIRES_PAYMENT,
            PaymentIntentStatus.PROCESSING,
        ],
    )


@transaction.atomic
def create_payment_intent(*, patient, order_id: int) -> PaymentIntent:
    if getattr(patient, "role", None) != Role.PATIENT:
        raise ValidationError("Only patients can create payment intents.")

    try:
        order = Order.objects.select_for_update().get(pk=order_id)
    except Order.DoesNotExist as exc:
        raise NotFound("Order not found.") from exc

    if order.patient_id != patient.pk:
        raise PermissionDenied("Order does not belong to this patient.")

    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise ValidationError(
            "Payment intent requires an order awaiting payment.",
            code="order_not_awaiting_payment",
        )

    existing = _open_intent_qs(order).first()
    if existing is not None:
        return existing

    provider = get_payment_provider()
    provider_name = (
        PaymentProviderName.PAYHERE
        if provider.name == "payhere"
        else PaymentProviderName.MOCK
    )
    attempt = PaymentIntent.objects.filter(order=order).count() + 1
    idempotency_key = f"order-{order.pk}-v{attempt}"

    # Provider needs a lightweight stand-in; we persist after create_intent returns.
    draft = PaymentIntent(
        order=order,
        patient=patient,
        provider=provider_name,
        status=PaymentIntentStatus.REQUIRES_PAYMENT,
        amount_lkr=order.total_lkr,
        currency=order.currency,
        provider_intent_id="",
        idempotency_key=idempotency_key,
    )
    result = provider.create_intent(order=order, payment_intent=draft)
    draft.provider_intent_id = result.provider_intent_id
    draft.client_payload = result.client_payload
    draft.provider_response = result.provider_response
    draft.save()
    return draft


@transaction.atomic
def apply_payment_success(*, payment_intent: PaymentIntent, source: str) -> PaymentIntent:
    """Mark intent succeeded, order paid, activate CareRelationship, send receipt (Steps 32–33)."""
    intent = PaymentIntent.objects.select_for_update().get(pk=payment_intent.pk)
    if intent.status == PaymentIntentStatus.SUCCEEDED:
        order = Order.objects.get(pk=intent.order_id)
        _activate_relationship_for_paid_order(order)
        _send_receipt_safe(order=order, payment_intent=intent, source=source)
        return intent

    order = Order.objects.select_for_update().get(pk=intent.order_id)
    if order.status == OrderStatus.PAID:
        intent.status = PaymentIntentStatus.SUCCEEDED
        if intent.confirmed_at is None:
            intent.confirmed_at = timezone.now()
        intent.save(update_fields=["status", "confirmed_at", "updated_at"])
        _activate_relationship_for_paid_order(order)
        _send_receipt_safe(order=order, payment_intent=intent, source=source)
        return intent

    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise ValidationError("Order is not awaiting payment.")

    now = timezone.now()
    intent.status = PaymentIntentStatus.SUCCEEDED
    intent.confirmed_at = now
    intent.failure_code = ""
    intent.failure_message = ""
    intent.save(
        update_fields=[
            "status",
            "confirmed_at",
            "failure_code",
            "failure_message",
            "updated_at",
        ]
    )

    order.status = OrderStatus.PAID
    order.save(update_fields=["status", "updated_at"])
    _activate_relationship_for_paid_order(order)
    _send_receipt_safe(order=order, payment_intent=intent, source=source)
    return intent


def _send_receipt_safe(*, order: Order, payment_intent: PaymentIntent, source: str) -> None:
    import logging

    from apps.catalog.receipts import send_order_receipt

    try:
        send_order_receipt(order=order, payment_intent=payment_intent, source=source)
    except Exception:
        logging.getLogger(__name__).exception(
            "Receipt email failed for order=%s", order.pk
        )


def _activate_relationship_for_paid_order(order: Order) -> None:
    """Activate pending_payment relationship; sync caregiver availability via activate_relationship."""
    from apps.accounts.audit import record_audit
    from apps.accounts.models import AuditAction
    from apps.matching.care_relationships import activate_relationship, relationship_payload
    from apps.matching.models import CareRelationship, CareRelationshipStatus
    from apps.matching.push import push_care_relationship_update

    try:
        rel = (
            CareRelationship.objects.select_related("patient", "caregiver", "caregiver__user")
            .select_for_update()
            .get(care_request_id=order.care_request_id)
        )
    except CareRelationship.DoesNotExist:
        return

    if rel.status != CareRelationshipStatus.PENDING_PAYMENT:
        return

    rel = activate_relationship(rel, actor=order.patient)
    record_audit(
        actor=order.patient,
        action=AuditAction.ACTIVATE_CARE_RELATIONSHIP,
        request=None,
        target_type="care_relationship",
        target_id=rel.pk,
        metadata={
            "patient_id": rel.patient_id,
            "caregiver_id": rel.caregiver_id,
            "order_id": order.pk,
            "source": "payment_success",
        },
        async_=False,
    )
    payload = relationship_payload(rel, event="activated")
    push_care_relationship_update(rel.patient_id, payload)
    push_care_relationship_update(rel.caregiver.user_id, payload)


@transaction.atomic
def apply_payment_failure(
    *,
    payment_intent: PaymentIntent,
    failure_code: str = "",
    failure_message: str = "",
    webhook_payload: dict | None = None,
) -> PaymentIntent:
    intent = PaymentIntent.objects.select_for_update().get(pk=payment_intent.pk)
    if intent.status == PaymentIntentStatus.SUCCEEDED:
        return intent

    intent.status = PaymentIntentStatus.FAILED
    intent.failure_code = (failure_code or "")[:64]
    intent.failure_message = failure_message or ""
    update_fields = ["status", "failure_code", "failure_message", "updated_at"]
    if webhook_payload is not None:
        intent.webhook_payload = webhook_payload
        update_fields.append("webhook_payload")
    intent.save(update_fields=update_fields)

    from apps.accounts.notifications.dispatch import notify_anomaly_alert_email

    patient = intent.patient
    detail = failure_message or failure_code or "Payment could not be completed."
    notify_anomaly_alert_email(
        user=patient,
        alert_title="Payment failed",
        detail=f"Payment intent #{intent.pk}: {detail}",
    )
    return intent


@transaction.atomic
def confirm_mock_payment(*, patient, provider_intent_id: str) -> PaymentIntent:
    if not getattr(settings, "MOCK_PAYMENT_CONFIRM_ENABLED", True):
        raise PermissionDenied("Mock payment confirmation is disabled.")

    if getattr(patient, "role", None) != Role.PATIENT:
        raise ValidationError("Only patients can confirm mock payments.")

    try:
        intent = PaymentIntent.objects.select_for_update().get(
            provider_intent_id=provider_intent_id,
            provider=PaymentProviderName.MOCK,
        )
    except PaymentIntent.DoesNotExist as exc:
        raise NotFound("Mock payment intent not found.") from exc

    if intent.patient_id != patient.pk:
        raise PermissionDenied("Payment intent does not belong to this patient.")

    if intent.status == PaymentIntentStatus.SUCCEEDED:
        return intent

    if intent.status not in (
        PaymentIntentStatus.REQUIRES_PAYMENT,
        PaymentIntentStatus.PROCESSING,
    ):
        raise ValidationError("Payment intent cannot be confirmed in its current state.")

    return apply_payment_success(payment_intent=intent, source="mock_confirm")


@transaction.atomic
def handle_payhere_webhook(*, body: bytes, headers: dict) -> PaymentIntent:
    provider = PayHereProvider()
    if not provider.verify_webhook_signature(body=body, headers=headers):
        raise PermissionDenied("Invalid PayHere webhook signature.")

    event = provider.parse_webhook(body=body)
    if not event.provider_intent_id:
        raise ValidationError("Webhook missing order_id.")

    try:
        intent = PaymentIntent.objects.select_for_update().get(
            provider_intent_id=event.provider_intent_id,
            provider=PaymentProviderName.PAYHERE,
        )
    except PaymentIntent.DoesNotExist as exc:
        raise NotFound("Payment intent not found for webhook.") from exc

    intent.webhook_payload = event.raw
    intent.save(update_fields=["webhook_payload", "updated_at"])

    if event.succeeded:
        return apply_payment_success(payment_intent=intent, source="payhere_webhook")
    return apply_payment_failure(
        payment_intent=intent,
        failure_code=event.failure_code,
        failure_message=event.failure_message,
        webhook_payload=event.raw,
    )
