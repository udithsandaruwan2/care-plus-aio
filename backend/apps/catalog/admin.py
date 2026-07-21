from django.contrib import admin

from .models import AddOn, CarePackage, Order, OrderLineItem, PaymentIntent


class OrderLineItemInline(admin.TabularInline):
    model = OrderLineItem
    extra = 0
    readonly_fields = (
        "kind",
        "catalog_id",
        "slug",
        "name",
        "unit_price_lkr",
        "quantity",
        "line_total_lkr",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CarePackage)
class CarePackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "care_level",
        "price_lkr",
        "default_days",
        "is_active",
        "sort_order",
    )
    list_filter = ("care_level", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(AddOn)
class AddOnAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "price_lkr", "is_active", "sort_order")
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "care_request",
        "status",
        "days",
        "total_lkr",
        "currency",
        "receipt_email_sent",
        "created_at",
    )
    list_filter = ("status", "currency", "receipt_email_sent")
    search_fields = ("patient__email",)
    readonly_fields = (
        "care_request",
        "patient",
        "status",
        "days",
        "currency",
        "subtotal_lkr",
        "total_lkr",
        "receipt_email_sent",
        "receipt_sent_at",
        "created_at",
        "updated_at",
    )
    inlines = [OrderLineItemInline]


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "patient",
        "provider",
        "status",
        "amount_lkr",
        "provider_intent_id",
        "confirmed_at",
        "created_at",
    )
    list_filter = ("provider", "status")
    search_fields = ("provider_intent_id", "patient__email", "idempotency_key")
    readonly_fields = (
        "order",
        "patient",
        "provider",
        "status",
        "amount_lkr",
        "currency",
        "provider_intent_id",
        "idempotency_key",
        "client_payload",
        "provider_response",
        "webhook_payload",
        "failure_code",
        "failure_message",
        "confirmed_at",
        "created_at",
        "updated_at",
    )
