"""Checkout session — create priced Order bound to CareRequest (Step 30)."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.matching.models import (
    CareRelationship,
    CareRelationshipStatus,
    CareRequest,
    CareRequestStatus,
)

from .models import AddOn, CarePackage, Order, OrderLineItem, OrderLineKind, OrderStatus


@transaction.atomic
def create_checkout_order(
    *,
    patient,
    care_request_id: int,
    package_id: int,
    addon_ids: list[int] | None = None,
    days: int | None = None,
) -> Order:
    """Select package + add-ons + days; persist priced line items."""
    if getattr(patient, "role", None) != Role.PATIENT:
        raise ValidationError("Only patients can create checkout orders.")

    try:
        care_request = CareRequest.objects.select_for_update().get(pk=care_request_id)
    except CareRequest.DoesNotExist as exc:
        raise ValidationError("Care request not found.") from exc

    if care_request.patient_id != patient.pk:
        raise ValidationError("Care request does not belong to this patient.")

    if care_request.status != CareRequestStatus.ACCEPTED:
        raise ValidationError(
            "Checkout requires an accepted care request.",
            code="care_request_not_accepted",
        )

    try:
        rel = care_request.relationship
    except CareRelationship.DoesNotExist:
        rel = None
    if rel is None or rel.status != CareRelationshipStatus.PENDING_PAYMENT:
        raise ValidationError(
            "Care relationship must be pending payment before checkout.",
            code="relationship_not_pending_payment",
        )

    if Order.objects.filter(
        care_request=care_request,
        status=OrderStatus.AWAITING_PAYMENT,
    ).exists():
        raise ValidationError(
            "An open checkout order already exists for this care request.",
            code="duplicate_open_order",
        )

    try:
        package = CarePackage.objects.get(pk=package_id, is_active=True)
    except CarePackage.DoesNotExist as exc:
        raise ValidationError("Active care package not found.") from exc

    billed_days = int(days) if days is not None else int(package.default_days)
    if billed_days < 1:
        raise ValidationError("days must be at least 1.")

    addon_ids = list(dict.fromkeys(addon_ids or []))
    addons: list[AddOn] = []
    if addon_ids:
        addons = list(AddOn.objects.filter(pk__in=addon_ids, is_active=True))
        found = {a.pk for a in addons}
        missing = [aid for aid in addon_ids if aid not in found]
        if missing:
            raise ValidationError(f"Active add-ons not found: {missing}.")

    package_line_total = (package.price_lkr * billed_days).quantize(Decimal("0.01"))
    lines: list[dict] = [
        {
            "kind": OrderLineKind.PACKAGE,
            "catalog_id": package.pk,
            "slug": package.slug,
            "name": package.name,
            "unit_price_lkr": package.price_lkr,
            "quantity": billed_days,
            "line_total_lkr": package_line_total,
        }
    ]
    addon_total = Decimal("0.00")
    for addon in addons:
        lines.append(
            {
                "kind": OrderLineKind.ADDON,
                "catalog_id": addon.pk,
                "slug": addon.slug,
                "name": addon.name,
                "unit_price_lkr": addon.price_lkr,
                "quantity": 1,
                "line_total_lkr": addon.price_lkr,
            }
        )
        addon_total += addon.price_lkr

    total = (package_line_total + addon_total).quantize(Decimal("0.01"))

    order = Order.objects.create(
        care_request=care_request,
        patient=patient,
        status=OrderStatus.AWAITING_PAYMENT,
        days=billed_days,
        currency="LKR",
        subtotal_lkr=total,
        total_lkr=total,
    )
    OrderLineItem.objects.bulk_create(
        [OrderLineItem(order=order, **line) for line in lines]
    )
    return order
