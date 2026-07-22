"""Order payment receipts — LKR breakdown email + HTML (Step 33)."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import escape

from apps.accounts.audit import record_audit
from apps.accounts.models import AuditAction

from .models import Order, OrderStatus

logger = logging.getLogger(__name__)


def format_lkr(value: Decimal | str | float | int) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    return f"LKR {amount:,.2f}"


def receipt_line_rows(order: Order) -> list[dict]:
    rows = []
    for line in order.lines.all():
        if line.kind == "package":
            detail = f"{format_lkr(line.unit_price_lkr)} × {line.quantity} days"
        else:
            detail = "Add-on"
        rows.append(
            {
                "kind": line.kind,
                "name": line.name,
                "detail": detail,
                "line_total": format_lkr(line.line_total_lkr),
            }
        )
    return rows


def format_receipt_text(*, order: Order, payment_intent=None, source: str = "") -> str:
    lines = receipt_line_rows(order)
    body_lines = [
        "Care Plus — Payment receipt",
        "",
        f"Order #{order.pk}",
        f"Status: {order.status}",
        f"Days of care: {order.days}",
        "",
        "Breakdown:",
    ]
    for row in lines:
        body_lines.append(f"  • {row['name']} ({row['detail']}) — {row['line_total']}")
    body_lines.extend(
        [
            "",
            f"Total ({order.currency}): {format_lkr(order.total_lkr)}",
        ]
    )
    if payment_intent is not None:
        body_lines.append(f"Provider: {payment_intent.provider}")
        if payment_intent.confirmed_at:
            body_lines.append(f"Paid at: {payment_intent.confirmed_at.isoformat()}")
        body_lines.append(f"Reference: {payment_intent.provider_intent_id}")
    if source:
        body_lines.append(f"Source: {source}")
    body_lines.extend(["", "Thank you for choosing Care Plus.", "", "— Care Plus"])
    return "\n".join(body_lines)


def format_receipt_html(*, order: Order, payment_intent=None) -> str:
    rows = "".join(
        f"<tr><td>{escape(r['name'])}</td><td>{escape(r['detail'])}</td>"
        f"<td style='text-align:right'>{escape(r['line_total'])}</td></tr>"
        for r in receipt_line_rows(order)
    )
    meta = ""
    if payment_intent is not None:
        paid = (
            payment_intent.confirmed_at.isoformat()
            if payment_intent.confirmed_at
            else ""
        )
        meta = (
            f"<p>Provider: {escape(payment_intent.provider)}<br/>"
            f"Paid at: {escape(paid)}<br/>"
            f"Reference: {escape(payment_intent.provider_intent_id)}</p>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Care Plus receipt — Order #{order.pk}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; color: #111; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
    th {{ font-size: 0.75rem; text-transform: uppercase; color: #555; }}
    .total {{ font-weight: 700; font-size: 1.1rem; }}
  </style>
</head>
<body>
  <h1>Care Plus receipt</h1>
  <p>Order #{order.pk} · {escape(order.status)} · {order.days} day(s)</p>
  {meta}
  <table>
    <thead><tr><th>Item</th><th>Detail</th><th>Amount</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="total">Total ({escape(order.currency)}): {escape(format_lkr(order.total_lkr))}</p>
  <p>Thank you for choosing Care Plus.</p>
</body>
</html>
"""


def send_order_receipt(*, order: Order, payment_intent=None, source: str = "") -> bool:
    """Email LKR breakdown to the patient; write RECEIPT_SENT audit. Idempotent."""
    if order.status != OrderStatus.PAID:
        return False
    if order.receipt_email_sent:
        return False
    if not getattr(settings, "RECEIPT_EMAIL_ENABLED", True):
        return False

    order = Order.objects.prefetch_related("lines").select_related("patient").get(pk=order.pk)
    patient_email = (order.patient.email or "").strip()
    if not patient_email:
        logger.warning("Order %s has no patient email; skipping receipt.", order.pk)
        return False

    from apps.accounts.notification_preferences import is_notification_enabled

    if not is_notification_enabled(
        order.patient, channel="email", event_key="payment_receipt"
    ):
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@careplus.local")
    subject = f"Care Plus receipt — Order #{order.pk}"
    body = format_receipt_text(order=order, payment_intent=payment_intent, source=source)
    sent = send_mail(
        subject,
        body,
        from_email,
        [patient_email],
        fail_silently=False,
    )
    if not sent:
        return False

    now = timezone.now()
    order.receipt_email_sent = True
    order.receipt_sent_at = now
    order.save(update_fields=["receipt_email_sent", "receipt_sent_at", "updated_at"])

    record_audit(
        actor=order.patient,
        action=AuditAction.RECEIPT_SENT,
        request=None,
        target_type="order",
        target_id=order.pk,
        metadata={
            "patient_email": patient_email,
            "total_lkr": str(order.total_lkr),
            "payment_intent_id": getattr(payment_intent, "pk", None),
            "source": source or "",
        },
        async_=False,
    )
    return True
