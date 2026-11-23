from rest_framework import serializers

from apps.pricing.services import money_str

from .models import Address, Order, OrderEvent, OrderItem, Shipment, ShipmentEvent


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "id",
            "label",
            "line1",
            "line2",
            "suburb",
            "city",
            "province",
            "postal_code",
            "country",
            "recipient_name",
            "recipient_phone",
            "is_default_shipping",
            "is_default_billing",
        )
        read_only_fields = ("id",)


class OrderItemSerializer(serializers.ModelSerializer):
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_name_snapshot",
            "sku_snapshot",
            "unit_price",
            "quantity",
            "line_total",
        )

    def get_unit_price(self, obj):
        return money_str(obj.unit_price)

    def get_line_total(self, obj):
        return money_str(obj.line_total)


class OrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderEvent
        fields = ("from_status", "to_status", "note", "created_at")


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ("status", "note", "created_at")


class ShipmentSerializer(serializers.ModelSerializer):
    events = ShipmentEventSerializer(many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = (
            "carrier",
            "tracking_number",
            "status",
            "dispatched_at",
            "delivered_at",
            "events",
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    events = OrderEventSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()
    discount_total = serializers.SerializerMethodField()
    shipping_total = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    tracking_stage = serializers.IntegerField(read_only=True)
    item_count = serializers.SerializerMethodField()
    cooling_off = serializers.SerializerMethodField()
    shipment = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "reference",
            "status",
            "currency",
            "subtotal",
            "discount_total",
            "shipping_total",
            "grand_total",
            "shipping_method",
            "payment_method",
            "shipping_address_text",
            "tracking_stage",
            "item_count",
            "items",
            "events",
            "shipment",
            "placed_at",
            "cooling_off",
        )

    def get_subtotal(self, obj):
        return money_str(obj.subtotal)

    def get_discount_total(self, obj):
        return money_str(obj.discount_total)

    def get_shipping_total(self, obj):
        return money_str(obj.shipping_total)

    def get_grand_total(self, obj):
        return money_str(obj.grand_total)

    def get_item_count(self, obj):
        return sum(i.quantity for i in obj.items.all())

    def get_shipment(self, obj):
        shipment = next(iter(obj.shipments.all()), None)
        if shipment is None:
            return None
        return ShipmentSerializer(shipment).data

    def get_cooling_off(self, obj):
        from .cooling_off import cooling_off_status

        s = cooling_off_status(obj)
        return {
            "eligible": s.eligible,
            "reason": s.reason,
            "deadline": s.deadline,
            "days_remaining": s.days_remaining,
            "excluded_items": s.excluded_items,
        }


class PlaceOrderSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(
        choices=["card", "eft", "cod"], default="card"
    )
    address = serializers.CharField(required=False, allow_blank=True)
    address_id = serializers.IntegerField(required=False, allow_null=True)
    return_url = serializers.CharField(required=False, allow_blank=True)
