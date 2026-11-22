from __future__ import annotations

from rest_framework import serializers

from apps.catalogue.models import Product, ProductVariant
from apps.pricing.services import money_str

from .models import Cart, CartDiscount, CartItem, SavedForLater, ShippingEstimate
from .services import assert_stock, cart_totals, ensure_shipping_estimates


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    variant_id = serializers.IntegerField(source="variant.id", read_only=True, allow_null=True)
    variant_label = serializers.CharField(source="variant.label", read_only=True, default="")
    brand = serializers.CharField(source="product.brand.name", read_only=True, default="")
    hue = serializers.IntegerField(source="product.hue", read_only=True)
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product_id",
            "product_name",
            "variant_id",
            "variant_label",
            "brand",
            "hue",
            "quantity",
            "unit_price",
            "line_total",
            "added_at",
        )

    def get_unit_price(self, obj):
        return money_str(obj.unit_price_snapshot)

    def get_line_total(self, obj):
        return money_str(obj.line_total)


class ShippingEstimateSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()

    class Meta:
        model = ShippingEstimate
        fields = ("id", "method_name", "price", "estimated_days", "is_selected")

    def get_price(self, obj):
        return money_str(obj.price)


class CartDiscountSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = CartDiscount
        fields = ("id", "code", "discount_type", "amount", "applied_at")

    def get_amount(self, obj):
        return money_str(obj.amount)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    discounts = CartDiscountSerializer(many=True, read_only=True)
    shipping_estimates = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = (
            "id",
            "is_active",
            "items",
            "discounts",
            "shipping_estimates",
            "totals",
            "total_items",
            "updated_at",
        )

    def get_shipping_estimates(self, obj):
        estimates = ensure_shipping_estimates(obj)
        return ShippingEstimateSerializer(estimates, many=True).data

    def get_totals(self, obj):
        return cart_totals(obj).as_dict()

    def get_total_items(self, obj):
        return sum(i.quantity for i in obj.items.all())


class AddItemSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    variant = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        try:
            product = Product.objects.get(pk=attrs["product"], is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError({"product": "Product not found."})
        variant = None
        vid = attrs.get("variant")
        if vid:
            try:
                variant = ProductVariant.objects.select_related("inventory").get(
                    pk=vid, product=product, is_active=True
                )
            except ProductVariant.DoesNotExist:
                raise serializers.ValidationError({"variant": "Variant not found."})
        attrs["product_obj"] = product
        attrs["variant_obj"] = variant
        return attrs


class UpdateItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class ApplyDiscountSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)


class SelectShippingSerializer(serializers.Serializer):
    shipping_method_id = serializers.IntegerField()


class TransferCartSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()


class SavedForLaterSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    variant_id = serializers.IntegerField(source="variant.id", read_only=True, allow_null=True)
    variant_label = serializers.CharField(source="variant.label", read_only=True, default="")
    hue = serializers.IntegerField(source="product.hue", read_only=True)
    unit_price = serializers.SerializerMethodField()

    class Meta:
        model = SavedForLater
        fields = (
            "id",
            "product_id",
            "product_name",
            "variant_id",
            "variant_label",
            "hue",
            "unit_price",
            "created_at",
        )

    def get_unit_price(self, obj):
        return money_str(obj.unit_price_snapshot)
