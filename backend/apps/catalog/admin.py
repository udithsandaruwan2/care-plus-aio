from django.contrib import admin

from .models import AddOn, CarePackage, Order, OrderLineItem


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
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = ("patient__email",)
    readonly_fields = (
        "care_request",
        "patient",
        "status",
        "days",
        "currency",
        "subtotal_lkr",
        "total_lkr",
        "created_at",
        "updated_at",
    )
    inlines = [OrderLineItemInline]
