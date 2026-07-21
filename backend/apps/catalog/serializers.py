from rest_framework import serializers

from .models import AddOn, CarePackage, Order, OrderLineItem, PaymentIntent


class CarePackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarePackage
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "care_level",
            "price_lkr",
            "default_days",
            "is_active",
            "sort_order",
        )
        read_only_fields = fields


class AddOnSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddOn
        fields = (
            "id",
            "slug",
            "name",
            "description",
            "category",
            "price_lkr",
            "is_active",
            "sort_order",
        )
        read_only_fields = fields


class OrderLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLineItem
        fields = (
            "id",
            "kind",
            "catalog_id",
            "slug",
            "name",
            "unit_price_lkr",
            "quantity",
            "line_total_lkr",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "care_request_id",
            "patient_id",
            "status",
            "days",
            "currency",
            "subtotal_lkr",
            "total_lkr",
            "receipt_email_sent",
            "receipt_sent_at",
            "lines",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CheckoutCreateSerializer(serializers.Serializer):
    care_request_id = serializers.IntegerField(min_value=1)
    package_id = serializers.IntegerField(min_value=1)
    addon_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        default=list,
    )
    days = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class PaymentIntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentIntent
        fields = (
            "id",
            "order_id",
            "patient_id",
            "provider",
            "status",
            "amount_lkr",
            "currency",
            "provider_intent_id",
            "idempotency_key",
            "client_payload",
            "failure_code",
            "failure_message",
            "confirmed_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
