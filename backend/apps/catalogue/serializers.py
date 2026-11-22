from __future__ import annotations

from django.conf import settings
from django.db.models import Avg, Count
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import Brand, Category, Inventory, Product, ProductAttribute, ProductVariant, Review


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "sort_order")


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ("id", "name", "slug")


class InventorySerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = ("quantity", "reserved_quantity", "available", "reorder_level", "low_stock")

    def get_low_stock(self, obj):
        return obj.available <= settings.LOW_STOCK_THRESHOLD and obj.available > 0


class VariantSerializer(serializers.ModelSerializer):
    stock = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "label",
            "price_delta",
            "unit_price",
            "stock",
            "low_stock",
            "is_active",
        )

    def get_stock(self, obj):
        inv = getattr(obj, "inventory", None)
        return inv.available if inv else 0

    def get_unit_price(self, obj):
        return f"{obj.unit_price:.2f}"

    def get_low_stock(self, obj):
        inv = getattr(obj, "inventory", None)
        if not inv:
            return False
        return inv.available <= settings.LOW_STOCK_THRESHOLD and inv.available > 0


class AttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ("key", "value")


class ReviewSerializer(serializers.ModelSerializer):
    who = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ("id", "rating", "title", "body", "who", "created_at")

    def get_who(self, obj):
        if obj.author_display:
            return obj.author_display
        if obj.user and hasattr(obj.user, "profile"):
            return obj.user.profile.display_name
        return "Customer"


class ProductListSerializer(serializers.ModelSerializer):
    brand = serializers.CharField(source="brand.name", default="")
    category = serializers.CharField(source="category.slug", default="")
    price = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    sold_out = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "name",
            "slug",
            "brand",
            "category",
            "price",
            "currency",
            "rating",
            "reviews",
            "hue",
            "sold_out",
            "image_url",
        )

    def get_price(self, obj):
        return f"{obj.base_price:.2f}"

    def get_rating(self, obj):
        agg = getattr(obj, "avg_rating", None)
        if agg is not None:
            return round(float(agg), 1)
        return 0.0

    def get_reviews(self, obj):
        return getattr(obj, "review_count", 0) or 0

    def get_image_url(self, obj):
        request = self.context.get("request")
        return reverse("product-image", kwargs={"pk": obj.pk}, request=request)

    def get_sold_out(self, obj):
        variants = obj.variants.all()
        if not variants:
            return True
        return all(
            (getattr(v, "inventory", None) is None or v.inventory.available == 0)
            for v in variants
        )


class ProductDetailSerializer(ProductListSerializer):
    description = serializers.CharField()
    variants = VariantSerializer(many=True, read_only=True)
    specs = AttributeSerializer(source="attributes", many=True, read_only=True)
    review_list = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description",
            "variants",
            "specs",
            "review_list",
        )

    def get_review_list(self, obj):
        qs = obj.reviews.filter(is_approved=True)[:10]
        return ReviewSerializer(qs, many=True).data
