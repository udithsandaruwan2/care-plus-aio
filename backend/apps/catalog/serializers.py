from rest_framework import serializers

from .models import AddOn, CarePackage


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
