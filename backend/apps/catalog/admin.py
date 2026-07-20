from django.contrib import admin

from .models import AddOn, CarePackage


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
